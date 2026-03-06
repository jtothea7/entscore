"""
Main orchestrator: runs the full analysis pipeline.

Calls DataForSEO -> scraper -> entity extractor -> BERT -> style -> heading
-> computes health score -> writes to SQLite in single transaction.

ALL database writes happen here, NEVER from scraper threads.
"""
import time
import json
from typing import Dict, Optional, Callable
from urllib.parse import urlparse
from collections import Counter

import yaml
from dotenv import load_dotenv
import os

from core.dataforseo_client import DataForSEOClient
from core.scraper import fetch_page, fetch_multiple_pages
from core.entity_extractor import EntityExtractor
from core.bert_analyzer import BERTAnalyzer
from core.style_analyzer import analyze_style, detect_brand_phrases
from core.heading_analyzer import compare_headings
from core.cache import Cache
from core.api_tracker import APITracker
from db.database import (
    get_connection,
    init_database,
    get_or_create_project,
    save_analysis,
    save_competitors,
    save_entities,
    get_previous_analysis,
)
from core.logger import setup_logger

logger = setup_logger(__name__)


def load_config() -> Dict:
    """Load config.yaml."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_analysis(
    url: str,
    keyword: str,
    location_code: int = 2840,
    location_name: str = "United States",
    page_type: str = "any",
    progress_callback: Optional[Callable] = None,
) -> Dict:
    """
    Run the full analysis pipeline.

    Args:
        url: Client page URL
        keyword: Target keyword
        location_code: DataForSEO location code (2840 = US national, or city-level)
        location_name: Human-readable location name for display
        page_type: "service" (commercial/transactional), "blog" (informational), or "any"
        progress_callback: Optional callable(step: str, progress: float) for UI updates

    Returns:
        Dict with analysis_id and summary data
    """
    start_time = time.time()
    config = load_config()

    def update_progress(step: str, progress: float):
        if progress_callback:
            progress_callback(step, progress)

    # Load environment
    load_dotenv()
    login = os.getenv("DATAFORSEO_LOGIN")
    password = os.getenv("DATAFORSEO_PASSWORD")

    if not login or not password:
        raise ValueError(
            "DataForSEO credentials not found. Add them to .env file."
        )

    # Initialize services
    update_progress("Initializing analysis engine...", 0.05)
    init_database()

    dfs_client = DataForSEOClient(login, password)
    cache = Cache(
        serp_ttl_hours=config["cache"]["serp_ttl_hours"],
        scrape_ttl_days=config["cache"]["scrape_ttl_days"],
    )
    api_tracker = APITracker()
    entity_extractor = EntityExtractor(config["models"]["spacy_model"])
    bert_analyzer = BERTAnalyzer(config["models"]["bert_model"])

    # Append city/state to keyword for local searches
    # e.g., "pest control" + "Miami,Florida,United States" -> "pest control Miami Florida"
    search_keyword = keyword
    if location_code != 2840 and location_name and location_name != "United States":
        # Extract city and state from location_name (format: "City,State,Country")
        parts = [p.strip() for p in location_name.split(",")]
        local_suffix = " ".join(parts[:2]) if len(parts) >= 2 else parts[0]
        # Only append if the keyword doesn't already contain the location
        if local_suffix.lower() not in keyword.lower():
            search_keyword = f"{keyword} {local_suffix}"
            logger.info(f"Localized keyword: '{keyword}' -> '{search_keyword}'")

    # Step 1: Get SERP results
    update_progress(f"Fetching SERP results for '{search_keyword}'...", 0.10)

    cache_key = f"serp:{search_keyword}:{location_code}"
    cached_serp = cache.get_api_cache(cache_key)

    if cached_serp:
        serp_results = cached_serp["results"]
        serp_cost = 0.0
        logger.info(f"Using cached SERP results for '{search_keyword}' (location: {location_code})")
    else:
        serp_response = dfs_client.get_serp_results(search_keyword, location_code=location_code)
        serp_results = serp_response["results"]
        serp_cost = serp_response["cost"]
        cache.set_api_cache(cache_key, serp_response)
        api_tracker.log_call(None, "serp/google/organic/live/advanced", serp_cost)

    if not serp_results:
        raise ValueError(f"No SERP results found for: {search_keyword}")

    # Page type filtering: use heuristics to filter SERP results by intent
    if page_type in ("service", "blog"):
        update_progress("Filtering competitors by page type...", 0.15)
        serp_results = _filter_by_page_type(serp_results, page_type)
        if not serp_results:
            raise ValueError(
                f"No {page_type} pages found in SERP results. Try 'Any' page type."
            )
        logger.info(
            f"Filtered to {len(serp_results)} {page_type} pages from SERP"
        )

    competitor_urls = [r["url"] for r in serp_results[:config["analysis"]["default_competitor_count"]]]
    serp_data = {r["url"]: r for r in serp_results}

    # Step 2: Scrape client page
    update_progress("Scraping your page...", 0.20)
    client_page = fetch_page(
        url,
        timeout=config["scraping"]["timeout"],
        max_retries=config["scraping"]["max_retries"],
        user_agent=config["scraping"]["user_agent"],
    )

    if not client_page.get("scrape_success"):
        raise ValueError(
            f"Could not scrape client page: {client_page.get('scrape_error', 'Unknown error')}"
        )

    # Step 3: Scrape competitor pages (parallel, in-memory only)
    update_progress("Scraping competitor pages...", 0.30)

    # Check cache first
    competitor_pages = []
    urls_to_fetch = []
    for comp_url in competitor_urls:
        cached = cache.get_scrape_cache(comp_url)
        if cached:
            competitor_pages.append({
                "url": comp_url,
                "html": cached["html"],
                "clean_text": cached["clean_text"],
                "headings": cached["metadata"].get("headings", []),
                "word_count": len(cached["clean_text"].split()),
                "internal_links": cached["metadata"].get("internal_links", []),
                "external_links": cached["metadata"].get("external_links", []),
                "schema_types": cached["metadata"].get("schema_types", []),
                "images_count": cached["metadata"].get("images_count", 0),
                "images_with_alt": cached["metadata"].get("images_with_alt", 0),
                "title": cached["metadata"].get("title", ""),
                "meta_description": cached["metadata"].get("meta_description", ""),
                "scrape_success": True,
                "scrape_method": "cache",
            })
        else:
            urls_to_fetch.append(comp_url)

    if urls_to_fetch:
        fetched = fetch_multiple_pages(
            urls_to_fetch,
            max_workers=config["scraping"]["max_concurrent_threads"],
            timeout=config["scraping"]["timeout"],
            max_retries=config["scraping"]["max_retries"],
            user_agent=config["scraping"]["user_agent"],
        )

        # Cache successful scrapes
        for page in fetched:
            if page.get("scrape_success"):
                cache.set_scrape_cache(
                    page["url"],
                    page.get("html", ""),
                    page.get("clean_text", ""),
                    {
                        "headings": page.get("headings", []),
                        "internal_links": page.get("internal_links", []),
                        "external_links": page.get("external_links", []),
                        "schema_types": page.get("schema_types", []),
                        "images_count": page.get("images_count", 0),
                        "images_with_alt": page.get("images_with_alt", 0),
                        "title": page.get("title", ""),
                        "meta_description": page.get("meta_description", ""),
                    },
                )
            competitor_pages.append(page)

    successful_competitors = [p for p in competitor_pages if p.get("scrape_success")]
    failed_competitors = len(competitor_pages) - len(successful_competitors)

    min_viable = config["app"]["minimum_viable_competitors"]
    if len(successful_competitors) < min_viable:
        logger.warning(
            f"Only {len(successful_competitors)} competitors scraped "
            f"(minimum: {min_viable}). Results may be unreliable."
        )

    # Step 4: Entity extraction
    update_progress("Extracting entities...", 0.45)

    client_entities = entity_extractor.extract_entities(
        client_page["clean_text"],
        html=client_page.get("html"),
        title=client_page.get("title", ""),
        meta_description=client_page.get("meta_description", ""),
        headings=client_page.get("headings", []),
    )

    competitor_entities_by_page = []
    for comp in successful_competitors:
        comp_ents = entity_extractor.extract_entities(
            comp.get("clean_text", ""),
            html=comp.get("html"),
            title=comp.get("title", ""),
            meta_description=comp.get("meta_description", ""),
            headings=comp.get("headings", []),
        )
        competitor_entities_by_page.append(comp_ents)

    # Step 5: Entity gap analysis
    update_progress("Analyzing entity gaps...", 0.55)

    # Count how many competitors mention each entity
    all_comp_entities = {}
    for page_entities in competitor_entities_by_page:
        seen_in_page = set()
        for ent in page_entities:
            key = ent["text"]
            if key not in seen_in_page:
                if key not in all_comp_entities:
                    all_comp_entities[key] = {
                        "type": ent["type"],
                        "frequency": 0,
                        "saliences": [],
                    }
                all_comp_entities[key]["frequency"] += 1
                all_comp_entities[key]["saliences"].append(ent["salience"])
                seen_in_page.add(key)

    # Deduplicate client entities
    client_entities = entity_extractor.deduplicate_entities(
        client_entities,
        similarity_threshold=config["analysis"]["entity_similarity_threshold"],
    )

    client_entity_map = {ent["text"]: ent for ent in client_entities}

    # Build entity gap table
    entity_records = []
    min_freq = config["analysis"]["min_entity_frequency"]

    for entity_text, comp_data in all_comp_entities.items():
        if comp_data["frequency"] < min_freq:
            continue

        client_ent = client_entity_map.get(entity_text)
        avg_salience = (
            sum(comp_data["saliences"]) / len(comp_data["saliences"])
            if comp_data["saliences"]
            else 0.0
        )

        if client_ent:
            if client_ent["salience"] >= avg_salience * 0.8:
                gap_status = "strong"
            else:
                gap_status = "weak"
        else:
            gap_status = "missing"

        entity_records.append({
            "entity_text": entity_text,
            "entity_type": comp_data["type"],
            "client_count": client_ent["count"] if client_ent else 0,
            "client_salience": client_ent["salience"] if client_ent else 0.0,
            "competitor_frequency": comp_data["frequency"],
            "competitor_avg_salience": round(avg_salience, 3),
            "gap_status": gap_status,
        })

    # Sort: missing first, then weak, then strong; within each by frequency desc
    gap_order = {"missing": 0, "weak": 1, "strong": 2}
    entity_records.sort(
        key=lambda e: (gap_order.get(e["gap_status"], 3), -e["competitor_frequency"])
    )

    # Step 6: Heading analysis
    update_progress("Analyzing heading structure...", 0.65)
    heading_result = compare_headings(
        client_page.get("headings", []), successful_competitors
    )

    # Step 7: Style analysis
    update_progress("Analyzing writing style...", 0.70)
    client_style = analyze_style(client_page["clean_text"])

    comp_styles = []
    for comp in successful_competitors:
        if comp.get("clean_text"):
            comp_styles.append(analyze_style(comp["clean_text"]))

    # Average competitor style
    if comp_styles:
        competitor_style = {
            "formality": round(
                sum(s["formality"] for s in comp_styles) / len(comp_styles), 2
            ),
            "readability_grade": round(
                sum(s["readability_grade"] for s in comp_styles) / len(comp_styles), 1
            ),
            "flesch_reading_ease": round(
                sum(s["flesch_reading_ease"] for s in comp_styles) / len(comp_styles), 1
            ),
            "avg_sentence_length": round(
                sum(s["avg_sentence_length"] for s in comp_styles) / len(comp_styles), 1
            ),
        }
    else:
        competitor_style = {}

    # Brand phrase detection
    competitor_texts = [c.get("clean_text", "") for c in successful_competitors]
    brand_phrases = detect_brand_phrases(client_page["clean_text"], competitor_texts)

    # Step 8: Calculate scores
    update_progress("Calculating health score...", 0.80)

    weights = config["health_score"]["weights"]

    # Entity coverage score
    total_important = len([e for e in entity_records if e["competitor_frequency"] >= min_freq])
    covered = len([e for e in entity_records if e["gap_status"] in ("strong", "weak")])
    entity_coverage_score = covered / total_important if total_important > 0 else 1.0

    # Word count comparison
    client_wc = client_page["word_count"]
    comp_word_counts = [c["word_count"] for c in successful_competitors if c.get("word_count", 0) > 0]
    comp_avg_wc = sum(comp_word_counts) / len(comp_word_counts) if comp_word_counts else client_wc

    if comp_avg_wc > 0:
        word_count_score = min(1.0, client_wc / comp_avg_wc)
    else:
        word_count_score = 1.0

    # Recommended word count
    recommended_min = int(comp_avg_wc * 0.9)
    recommended_max = int(comp_avg_wc * 1.15)
    if recommended_min < client_wc:
        recommended_min = client_wc
    if recommended_max > client_wc * 2:
        recommended_max = client_wc * 2

    # Readability score (normalized)
    readability_score = min(1.0, max(0.0, client_style["flesch_reading_ease"] / 100))

    # Internal links score
    client_internal_count = len(client_page.get("internal_links", []))
    comp_link_counts = [
        len(c.get("internal_links", []))
        for c in successful_competitors
        if c.get("scrape_success")
    ]
    comp_avg_links = (
        sum(comp_link_counts) / len(comp_link_counts) if comp_link_counts else client_internal_count
    )
    link_score = min(1.0, client_internal_count / comp_avg_links) if comp_avg_links > 0 else 1.0

    # Heading score from heading analyzer
    heading_score = heading_result["score"]

    # Overall health score
    health_score = round(
        (entity_coverage_score * weights["entity_coverage"])
        + (heading_score * weights["heading_structure"])
        + (word_count_score * weights["word_count"])
        + (readability_score * weights["readability"])
        + (link_score * weights["internal_links"]),
        2,
    ) * 100

    health_score = min(100, max(0, health_score))

    # Step 9: Schema analysis
    client_schema = client_page.get("schema_types", [])
    comp_schema_counter = Counter()
    for comp in successful_competitors:
        for schema_type in comp.get("schema_types", []):
            comp_schema_counter[schema_type] += 1

    # Step 10: Write everything to SQLite in one transaction
    update_progress("Saving results...", 0.90)

    duration = time.time() - start_time
    domain = urlparse(url).netloc

    conn = get_connection()
    try:
        project_id = get_or_create_project(conn, domain)

        # Extra data for the results page
        extra_data = {
            "client_headings": client_page.get("headings", []),
            "client_internal_links": client_internal_count,
            "client_external_links": len(client_page.get("external_links", [])),
            "client_images_count": client_page.get("images_count", 0),
            "client_images_with_alt": client_page.get("images_with_alt", 0),
            "client_schema_types": client_schema,
            "client_style": client_style,
            "competitor_avg_h2_count": heading_result["competitor_avg"].get("h2", 0),
            "competitor_avg_internal_links": comp_avg_links,
            "competitor_schema_frequency": dict(comp_schema_counter),
            "competitor_style": competitor_style,
            "heading_result": {
                "client": heading_result["client"],
                "competitor_avg": heading_result["competitor_avg"],
                "score": heading_result["score"],
                "issues": heading_result["issues"],
            },
            "brand_phrases": brand_phrases,
        }

        analysis_id = save_analysis(conn, {
            "project_id": project_id,
            "url": url,
            "keyword": keyword,
            "health_score": health_score,
            "entity_coverage_score": round(entity_coverage_score * 100, 1),
            "heading_score": round(heading_score * 100, 1),
            "word_count_score": round(word_count_score * 100, 1),
            "readability_score": round(readability_score * 100, 1),
            "link_score": round(link_score * 100, 1),
            "client_word_count": client_wc,
            "competitor_avg_word_count": round(comp_avg_wc, 1),
            "recommended_word_count_min": recommended_min,
            "recommended_word_count_max": recommended_max,
            "analysis_duration_seconds": round(duration, 1),
            "competitors_analyzed": len(successful_competitors),
            "competitors_failed": failed_competitors,
            "extra_data": extra_data,
        })

        # Save competitors
        comp_records = []
        for comp in competitor_pages:
            position = serp_data.get(comp["url"], {}).get("position")
            comp_entities_count = 0
            for page_ents in competitor_entities_by_page:
                # Rough match by position in list
                pass

            comp_records.append({
                "url": comp["url"],
                "position": position,
                "word_count": comp.get("word_count", 0),
                "heading_count": len(comp.get("headings", [])),
                "entity_count": 0,
                "scrape_success": comp.get("scrape_success", False),
                "scrape_method": comp.get("scrape_method", ""),
            })

        save_competitors(conn, analysis_id, comp_records)
        save_entities(conn, analysis_id, entity_records)

        # Log API costs
        if serp_cost > 0:
            from db.database import save_api_usage
            save_api_usage(conn, analysis_id, "serp/google/organic/live/advanced", serp_cost)

    finally:
        conn.close()

    update_progress("Analysis complete!", 1.0)

    logger.info(
        f"Analysis complete for {url} / '{keyword}': "
        f"health={health_score:.0f}, entities={len(entity_records)}, "
        f"duration={duration:.1f}s, cost=${dfs_client.total_cost:.4f}"
    )

    return {
        "analysis_id": analysis_id,
        "health_score": health_score,
        "entity_count": len(entity_records),
        "missing_entities": len([e for e in entity_records if e["gap_status"] == "missing"]),
        "competitors_analyzed": len(successful_competitors),
        "competitors_failed": failed_competitors,
        "duration": round(duration, 1),
        "cost": dfs_client.total_cost,
    }


# URL patterns that indicate page type
_BLOG_PATTERNS = [
    "/blog/", "/article/", "/post/", "/news/", "/guides/", "/guide/",
    "/learn/", "/resources/", "/how-to", "/what-is", "/tips/",
    "/wiki/", "/magazine/", "/journal/",
]

_SERVICE_PATTERNS = [
    "/services/", "/service/", "/solutions/", "/products/", "/product/",
    "/pricing/", "/plans/", "/hire/", "/contact/", "/get-",
    "/locations/", "/areas-served/", "/near-me",
]


def _filter_by_page_type(serp_results: list, page_type: str) -> list:
    """
    Filter SERP results by page type using URL pattern heuristics.

    Args:
        serp_results: List of SERP result dicts with 'url', 'title', 'description'
        page_type: "service" or "blog"

    Returns:
        Filtered list keeping only results matching the page type.
        Falls back to all results if filtering removes too many.
    """
    if page_type == "any":
        return serp_results

    scored = []
    for result in serp_results:
        url_lower = result.get("url", "").lower()
        title_lower = result.get("title", "").lower()
        desc_lower = result.get("description", "").lower()

        blog_score = 0
        service_score = 0

        # URL pattern matching
        for pattern in _BLOG_PATTERNS:
            if pattern in url_lower:
                blog_score += 2

        for pattern in _SERVICE_PATTERNS:
            if pattern in url_lower:
                service_score += 2

        # Title/description heuristics for blog/informational
        blog_signals = ["how to", "what is", "guide", "tips", "best ", "top ",
                        "vs ", "review", "explained", "complete guide"]
        for signal in blog_signals:
            if signal in title_lower or signal in desc_lower:
                blog_score += 1

        # Title/description heuristics for service/commercial
        service_signals = ["services", "near me", "call today", "free quote",
                          "get a quote", "contact us", "hire", "pricing",
                          "affordable", "professional"]
        for signal in service_signals:
            if signal in title_lower or signal in desc_lower:
                service_score += 1

        # Classify
        if page_type == "blog":
            is_match = blog_score > service_score or (blog_score > 0 and service_score == 0)
        else:  # service
            is_match = service_score > blog_score or (service_score > 0 and blog_score == 0)

        # Neutral pages (no strong signals) are included as they could be either
        is_neutral = blog_score == 0 and service_score == 0

        scored.append({
            **result,
            "_is_match": is_match,
            "_is_neutral": is_neutral,
        })

    # Keep matching pages first, then neutrals as fallback
    matched = [r for r in scored if r["_is_match"]]
    neutrals = [r for r in scored if r["_is_neutral"]]

    # If we have at least 3 strong matches, use those + neutrals
    if len(matched) >= 3:
        filtered = matched + neutrals
    else:
        # Not enough signal — return all results rather than filtering poorly
        filtered = scored
        logger.info(
            f"Page type filter for '{page_type}' found only {len(matched)} matches, "
            f"using all {len(filtered)} results"
        )

    # Clean up internal keys
    for r in filtered:
        r.pop("_is_match", None)
        r.pop("_is_neutral", None)

    return filtered

"""
Web scraping with fallback chain.

CRITICAL: fetch_multiple_pages returns results in memory. Database writes happen
ONLY in gap_analyzer.py AFTER all scraping completes. Never write to SQLite from
scraper threads.
"""
from typing import Dict, List
import trafilatura
from bs4 import BeautifulSoup
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import json
from core.logger import setup_logger

logger = setup_logger(__name__)


def fetch_page(
    url: str,
    timeout: int = 15,
    max_retries: int = 2,
    user_agent: str = "EntScore/1.0 (SEO Analysis Tool)",
) -> Dict:
    """
    Fetch and parse a single web page.

    Returns dict with:
        url, html, clean_text, title, meta_description, headings,
        word_count, internal_links, external_links, schema_types,
        images_count, images_with_alt, scrape_success, scrape_method
    """
    headers = {"User-Agent": user_agent}

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            html = response.text

            # Extract clean text with trafilatura
            clean_text = trafilatura.extract(html) or ""

            # Parse with BeautifulSoup for structure
            soup = BeautifulSoup(html, "html.parser")

            # Title and meta
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else ""

            meta_desc = soup.find("meta", attrs={"name": "description"})
            meta_description = (
                meta_desc.get("content", "").strip() if meta_desc else ""
            )

            # Headings
            headings = []
            for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                for tag in soup.find_all(level):
                    headings.append(
                        {"level": level, "text": tag.get_text().strip()}
                    )

            # Links
            internal_links = []
            external_links = []
            page_domain = urlparse(url).netloc

            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("/") or page_domain in href:
                    internal_links.append(href)
                elif href.startswith("http"):
                    external_links.append(href)

            # Images
            images = soup.find_all("img")
            images_count = len(images)
            images_with_alt = len([img for img in images if img.get("alt")])

            # Schema markup
            schema_types = []
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    schema_data = json.loads(script.string or "")
                    if isinstance(schema_data, dict) and "@type" in schema_data:
                        schema_types.append(schema_data["@type"])
                    elif isinstance(schema_data, list):
                        for item in schema_data:
                            if isinstance(item, dict) and "@type" in item:
                                schema_types.append(item["@type"])
                except (json.JSONDecodeError, TypeError):
                    pass

            # Word count
            word_count = len(clean_text.split())

            logger.info(
                f"Successfully scraped {url} - {word_count} words, {len(headings)} headings"
            )

            return {
                "url": url,
                "html": html,
                "clean_text": clean_text,
                "title": title,
                "meta_description": meta_description,
                "headings": headings,
                "word_count": word_count,
                "internal_links": list(set(internal_links)),
                "external_links": list(set(external_links)),
                "schema_types": list(set(schema_types)),
                "images_count": images_count,
                "images_with_alt": images_with_alt,
                "scrape_success": True,
                "scrape_method": "trafilatura",
            }

        except requests.RequestException as e:
            if attempt < max_retries:
                logger.warning(
                    f"Scraping {url} failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}"
                )
                continue
            else:
                logger.error(
                    f"Failed to scrape {url} after {max_retries + 1} attempts: {str(e)}"
                )
                return {
                    "url": url,
                    "scrape_success": False,
                    "scrape_error": str(e),
                    "scrape_method": "failed",
                }


def fetch_multiple_pages(
    urls: List[str], max_workers: int = 5, **kwargs
) -> List[Dict]:
    """
    Fetch multiple pages in parallel using ThreadPoolExecutor.

    Returns results in memory. Database writes happen ONLY in gap_analyzer.py
    AFTER all scraping completes. Never write to SQLite from scraper threads.

    Returns:
        List of page dicts (from fetch_page)
    """
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(fetch_page, url, **kwargs): url for url in urls
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Exception scraping {url}: {str(e)}")
                results.append(
                    {
                        "url": url,
                        "scrape_success": False,
                        "scrape_error": str(e),
                        "scrape_method": "exception",
                    }
                )

    successful = len([r for r in results if r.get("scrape_success")])
    logger.info(f"Scraping complete: {successful}/{len(urls)} pages successful")

    return results

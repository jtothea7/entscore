"""
DataForSEO API wrapper with retry logic and cost tracking
"""
from typing import Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth
import time
from core.logger import setup_logger

logger = setup_logger(__name__)


class DataForSEOClient:
    def __init__(
        self,
        login: str,
        password: str,
        base_url: str = "https://api.dataforseo.com/v3",
    ):
        self.auth = HTTPBasicAuth(login, password)
        self.base_url = base_url
        self.max_retries = 3
        self.retry_backoff = [1, 3, 10]
        self._total_cost = 0.0

    def _request(self, endpoint: str, data) -> Dict:
        """
        Make API request with retry logic.

        Retry policy:
            - 429 (Too Many Requests): Retry with backoff
            - 500 (Server Error): Retry with backoff
            - 402 (Payment Required): STOP immediately, no retry
            - 401 (Unauthorized): STOP immediately, no retry
            - Timeout: Retry once
        """
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url, json=data, auth=self.auth, timeout=30
                )

                if response.status_code == 402:
                    logger.error("DataForSEO credits exhausted (402)")
                    raise Exception(
                        "DataForSEO credits exhausted. Please add funds to your account."
                    )

                if response.status_code == 401:
                    logger.error("Invalid DataForSEO credentials (401)")
                    raise Exception(
                        "Invalid DataForSEO credentials. Check your login/password."
                    )

                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_backoff[attempt]
                        logger.warning(f"Rate limited (429). Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Rate limit exceeded. Try again later.")

                if response.status_code == 500:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_backoff[attempt]
                        logger.warning(
                            f"Server error (500). Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception("DataForSEO server error. Try again later.")

                response.raise_for_status()

                result = response.json()

                # Extract cost if available
                cost = 0.0
                if "cost" in result:
                    cost = result["cost"]
                elif "tasks" in result and len(result["tasks"]) > 0:
                    cost = result["tasks"][0].get("cost", 0.0)

                self._total_cost += cost
                logger.info(f"API call to {endpoint} successful. Cost: ${cost:.4f}")

                return {"data": result, "cost": cost, "endpoint": endpoint}

            except requests.Timeout:
                if attempt < 1:
                    logger.warning("Request timeout. Retrying...")
                    time.sleep(2)
                    continue
                else:
                    raise Exception("Request timeout. DataForSEO API is slow.")

            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Request failed: {str(e)}. Retrying...")
                    time.sleep(self.retry_backoff[attempt])
                    continue
                else:
                    raise Exception(f"DataForSEO API error: {str(e)}")

        raise Exception("Max retries exceeded")

    def get_serp_results(
        self, keyword: str, location_code: int = 2840
    ) -> Dict:
        """
        Get organic SERP results for keyword.

        Args:
            keyword: Search query
            location_code: DataForSEO location code (2840 = United States)

        Returns:
            Dict with 'results' list and 'cost' float
        """
        endpoint = "serp/google/organic/live/advanced"

        data = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": "en",
                "device": "desktop",
                "os": "windows",
                "depth": 10,
            }
        ]

        response = self._request(endpoint, data)

        results = []
        tasks = response["data"].get("tasks", [])

        if tasks and len(tasks) > 0:
            task = tasks[0]
            if task.get("status_code") == 20000 and task.get("result"):
                items = task["result"][0].get("items", [])
                for item in items:
                    if item.get("type") == "organic":
                        results.append(
                            {
                                "url": item.get("url"),
                                "title": item.get("title"),
                                "description": item.get("description"),
                                "position": item.get("rank_absolute"),
                            }
                        )

        logger.info(f"Retrieved {len(results)} SERP results for '{keyword}'")

        return {"results": results, "cost": response["cost"]}

    def get_onpage_content(self, url: str) -> Dict:
        """
        Fallback scraper: use DataForSEO On-Page API to get page content.

        Returns:
            Dict with 'content', 'title', 'meta_description', 'cost'
        """
        endpoint = "on_page/instant_pages"

        data = [
            {
                "url": url,
                "load_resources": False,
                "enable_javascript": True,
            }
        ]

        try:
            response = self._request(endpoint, data)
            tasks = response["data"].get("tasks", [])

            if tasks and len(tasks) > 0:
                task = tasks[0]
                if task.get("status_code") == 20000 and task.get("result"):
                    items = task["result"]
                    if items:
                        page = items[0]
                        return {
                            "content": page.get("plain_text_content", ""),
                            "title": page.get("meta", {}).get("title", ""),
                            "meta_description": page.get("meta", {}).get(
                                "description", ""
                            ),
                            "cost": response["cost"],
                            "success": True,
                        }

            return {"content": "", "success": False, "cost": response["cost"]}

        except Exception as e:
            logger.warning(f"DataForSEO on-page fallback failed for {url}: {e}")
            return {"content": "", "success": False, "cost": 0.0}

    def search_locations(self, query: str, country: str = "US") -> List[Dict]:
        """
        Search for DataForSEO location codes by city/state name.

        Args:
            query: Search term (e.g., "Austin, Texas" or "Miami")
            country: ISO country code filter

        Returns:
            List of matching locations with location_code, location_name, location_type
        """
        endpoint = f"serp/google/locations/{country.lower()}"

        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, auth=self.auth, timeout=15)
            response.raise_for_status()
            data = response.json()

            locations = []
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                query_lower = query.lower()
                for loc in tasks[0]["result"]:
                    loc_name = loc.get("location_name", "").lower()
                    if query_lower in loc_name:
                        locations.append({
                            "location_code": loc["location_code"],
                            "location_name": loc["location_name"],
                            "location_type": loc.get("location_type", ""),
                        })

            # Sort: prefer City matches first, then by name length (shorter = more relevant)
            locations.sort(key=lambda x: (
                0 if x["location_type"] == "City" else 1,
                len(x["location_name"]),
            ))

            logger.info(f"Found {len(locations)} locations matching '{query}'")
            return locations[:20]  # Cap at 20

        except Exception as e:
            logger.warning(f"Location search failed: {e}")
            return []

    def get_search_intent(self, keywords: List[str]) -> Dict[str, Dict]:
        """
        Classify search intent for one or more keywords.

        Uses DataForSEO Labs Search Intent endpoint.

        Args:
            keywords: List of keywords to classify

        Returns:
            Dict mapping keyword -> {intent, probability, secondary_intents}
        """
        endpoint = "dataforseo_labs/google/search_intent/live"

        data = [{
            "keywords": keywords[:1000],  # API max 1000 per request
            "language_code": "en",
        }]

        try:
            response = self._request(endpoint, data)
            tasks = response["data"].get("tasks", [])

            result = {}
            if tasks and tasks[0].get("result"):
                for item in tasks[0]["result"]:
                    kw = item.get("keyword", "")
                    intent_info = item.get("keyword_intent", {})
                    result[kw] = {
                        "intent": intent_info.get("label", "unknown"),
                        "probability": intent_info.get("probability", 0.0),
                        "secondary_intents": [
                            si.get("label", "")
                            for si in item.get("secondary_keyword_intents", [])
                        ],
                    }

            logger.info(f"Classified intent for {len(result)} keywords")
            return result

        except Exception as e:
            logger.warning(f"Search intent classification failed: {e}")
            return {}

    @property
    def total_cost(self) -> float:
        """Total API cost for this session."""
        return self._total_cost

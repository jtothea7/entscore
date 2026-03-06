"""
3-tier cache: API responses, scrape results, model cache
"""
import json
from typing import Optional, Dict
from datetime import datetime, timedelta

from db.database import get_connection
from core.logger import setup_logger

logger = setup_logger(__name__)


class Cache:
    def __init__(
        self,
        serp_ttl_hours: int = 24,
        scrape_ttl_days: int = 7,
        keyword_metrics_ttl_days: int = 7,
    ):
        self.serp_ttl_hours = serp_ttl_hours
        self.scrape_ttl_days = scrape_ttl_days
        self.keyword_metrics_ttl_days = keyword_metrics_ttl_days

    def get_api_cache(self, cache_key: str) -> Optional[Dict]:
        """Get cached API response if not expired."""
        conn = get_connection()
        try:
            cursor = conn.execute(
                "SELECT response_data FROM api_cache WHERE cache_key = ? AND expires_at > datetime('now')",
                (cache_key,),
            )
            row = cursor.fetchone()
            if row:
                logger.info(f"Cache hit: {cache_key}")
                return json.loads(row["response_data"])
            return None
        finally:
            conn.close()

    def set_api_cache(self, cache_key: str, data: Dict, ttl_hours: Optional[int] = None):
        """Cache an API response."""
        ttl = ttl_hours or self.serp_ttl_hours
        expires_at = (datetime.utcnow() + timedelta(hours=ttl)).isoformat()

        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO api_cache (cache_key, response_data, expires_at)
                   VALUES (?, ?, ?)""",
                (cache_key, json.dumps(data), expires_at),
            )
            conn.commit()
            logger.info(f"Cached: {cache_key} (TTL: {ttl}h)")
        finally:
            conn.close()

    def get_scrape_cache(self, url: str) -> Optional[Dict]:
        """Get cached scrape result if not expired."""
        conn = get_connection()
        try:
            cursor = conn.execute(
                "SELECT html, clean_text, metadata FROM scrape_cache WHERE url = ? AND expires_at > datetime('now')",
                (url,),
            )
            row = cursor.fetchone()
            if row:
                logger.info(f"Scrape cache hit: {url}")
                metadata = {}
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                return {
                    "html": row["html"],
                    "clean_text": row["clean_text"],
                    "metadata": metadata,
                }
            return None
        finally:
            conn.close()

    def set_scrape_cache(self, url: str, html: str, clean_text: str, metadata: Optional[Dict] = None):
        """Cache a scrape result."""
        expires_at = (
            datetime.utcnow() + timedelta(days=self.scrape_ttl_days)
        ).isoformat()

        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO scrape_cache (url, html, clean_text, metadata, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    url,
                    html,
                    clean_text,
                    json.dumps(metadata) if metadata else None,
                    expires_at,
                ),
            )
            conn.commit()
            logger.info(f"Scrape cached: {url}")
        finally:
            conn.close()

    def clear_expired(self):
        """Remove expired cache entries."""
        conn = get_connection()
        try:
            from db.database import clear_expired_cache
            clear_expired_cache(conn)
            logger.info("Expired cache entries cleared")
        finally:
            conn.close()

    def clear_all(self):
        """Clear all cache entries."""
        conn = get_connection()
        try:
            from db.database import clear_all_cache
            clear_all_cache(conn)
            logger.info("All cache cleared")
        finally:
            conn.close()

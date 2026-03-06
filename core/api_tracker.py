"""
DataForSEO API cost tracking
"""
from typing import Optional, Dict
from db.database import get_connection, save_api_usage, get_api_usage_total
from core.logger import setup_logger

logger = setup_logger(__name__)


class APITracker:
    def __init__(self):
        self._session_cost = 0.0
        self._session_calls = 0

    def log_call(self, analysis_id: Optional[int], endpoint: str, cost: float):
        """Log an API call and its cost to the database."""
        self._session_cost += cost
        self._session_calls += 1

        conn = get_connection()
        try:
            save_api_usage(conn, analysis_id, endpoint, cost)
            logger.info(
                f"API call logged: {endpoint} cost=${cost:.4f} "
                f"(session total: ${self._session_cost:.4f})"
            )
        finally:
            conn.close()

    def get_monthly_summary(self) -> Dict:
        """Get API usage summary for the current month (last 30 days)."""
        conn = get_connection()
        try:
            return get_api_usage_total(conn, days=30)
        finally:
            conn.close()

    @property
    def session_cost(self) -> float:
        return self._session_cost

    @property
    def session_calls(self) -> int:
        return self._session_calls

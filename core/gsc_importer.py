"""
Google Search Console CSV parser and opportunity scoring.

Handles two GSC export formats:
  - Queries CSV: columns [Top queries, Clicks, Impressions, CTR, Position]
  - Pages CSV:   columns [Top pages, Clicks, Impressions, CTR, Position]
"""
from typing import List, Dict, Tuple
import pandas as pd
from core.logger import setup_logger

logger = setup_logger(__name__)


def detect_csv_type(df: pd.DataFrame) -> str:
    """Detect whether this is a Queries or Pages CSV."""
    if "Top queries" in df.columns or "Query" in df.columns:
        return "queries"
    elif "Top pages" in df.columns or "Page" in df.columns or "Landing page" in df.columns:
        return "pages"
    else:
        raise ValueError(
            "Unrecognized CSV format. Expected GSC export with "
            "'Top queries' or 'Top pages' column."
        )


def parse_gsc_csv(file_path_or_buffer) -> Tuple[List[Dict], List[str], str]:
    """
    Parse a GSC CSV export into structured records with opportunity scores.

    Opportunity Score = Impressions * (1 - CTR) * (1 / Position)

    Returns:
        (records, warnings, csv_type) — list of dicts, warnings, and "queries" or "pages"
    """
    df = pd.read_csv(file_path_or_buffer)
    warnings = []

    if len(df) == 0:
        raise ValueError("CSV file is empty")

    csv_type = detect_csv_type(df)

    # Normalize columns based on type
    if csv_type == "queries":
        column_map = {
            "Top queries": "keyword",
            "Query": "keyword",
            "Average position": "position",
            "Position": "position",
        }
        df = df.rename(columns=column_map)

        if "keyword" not in df.columns:
            raise ValueError("Missing keyword column (Top queries or Query)")

        df["url"] = ""  # Queries CSV doesn't have URLs

    else:  # pages
        column_map = {
            "Top pages": "url",
            "Page": "url",
            "Landing page": "url",
            "Average position": "position",
            "Position": "position",
        }
        df = df.rename(columns=column_map)

        if "url" not in df.columns:
            raise ValueError("Missing page column (Top pages or Page)")

        df["keyword"] = ""  # Pages CSV doesn't have keywords

    # Validate required metric columns
    for col in ["Clicks", "Impressions", "CTR", "position"]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # Clean CTR (may be percentage string like "1.97%")
    if df["CTR"].dtype == object:
        df["CTR"] = df["CTR"].str.rstrip("%").astype(float) / 100

    # Calculate opportunity score
    df["opportunity_score"] = df.apply(
        lambda row: _calc_opportunity(
            row["Impressions"], row["CTR"], row["position"]
        ),
        axis=1,
    )

    # Sort by opportunity score
    df = df.sort_values("opportunity_score", ascending=False)

    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "url": str(row.get("url", "")),
                "keyword": str(row.get("keyword", "")),
                "clicks": int(row["Clicks"]),
                "impressions": int(row["Impressions"]),
                "ctr": float(row["CTR"]),
                "position": float(row["position"]),
                "opportunity_score": round(float(row["opportunity_score"]), 2),
            }
        )

    logger.info(
        f"Parsed {len(records)} GSC {csv_type} records. "
        f"Top opportunity score: {records[0]['opportunity_score'] if records else 0}"
    )

    return records, warnings, csv_type


def _calc_opportunity(impressions: int, ctr: float, position: float) -> float:
    """
    Calculate opportunity score.

    Formula: Impressions * (1 - CTR) * (1 / Position)

    Higher score = bigger opportunity for optimization.
    """
    if position <= 0:
        position = 100
    return impressions * (1 - ctr) * (1 / position)

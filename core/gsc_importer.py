"""
Google Search Console CSV parser and opportunity scoring
"""
from typing import List, Dict, Tuple
import pandas as pd
from core.validators import validate_gsc_csv
from core.logger import setup_logger

logger = setup_logger(__name__)


def parse_gsc_csv(file_path_or_buffer) -> Tuple[List[Dict], List[str]]:
    """
    Parse a GSC CSV export into structured records with opportunity scores.

    Opportunity Score = Impressions * (1 - CTR) * (1 / Position)

    Pages with high impressions, low CTR, and poor position are the biggest opportunities.

    Args:
        file_path_or_buffer: File path string or file-like object

    Returns:
        (records, warnings) — list of dicts and list of warning strings
    """
    df = pd.read_csv(file_path_or_buffer)

    is_valid, error, warnings = validate_gsc_csv(df)
    if not is_valid:
        raise ValueError(f"Invalid GSC CSV: {error}")

    # Normalize column names
    column_map = {
        "Top queries": "keyword",
        "Query": "keyword",
        "Average position": "position",
        "Position": "position",
    }

    df = df.rename(columns=column_map)

    # Ensure required columns exist
    for col in ["keyword", "Clicks", "Impressions", "CTR", "position"]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # Clean CTR (may be percentage string)
    if df["CTR"].dtype == object:
        df["CTR"] = df["CTR"].str.rstrip("%").astype(float) / 100

    # Handle URL column — GSC "Pages" export has it, "Queries" export doesn't
    if "Landing page" in df.columns:
        df = df.rename(columns={"Landing page": "url"})
    elif "Page" in df.columns:
        df = df.rename(columns={"Page": "url"})
    elif "url" not in df.columns:
        df["url"] = ""

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
                "keyword": str(row["keyword"]),
                "clicks": int(row["Clicks"]),
                "impressions": int(row["Impressions"]),
                "ctr": float(row["CTR"]),
                "position": float(row["position"]),
                "opportunity_score": round(float(row["opportunity_score"]), 2),
            }
        )

    logger.info(
        f"Parsed {len(records)} GSC records. Top opportunity score: "
        f"{records[0]['opportunity_score'] if records else 0}"
    )

    return records, warnings


def _calc_opportunity(impressions: int, ctr: float, position: float) -> float:
    """
    Calculate opportunity score.

    Formula: Impressions * (1 - CTR) * (1 / Position)

    Higher score = bigger opportunity for optimization.
    """
    if position <= 0:
        position = 100  # Default for missing position
    return impressions * (1 - ctr) * (1 / position)

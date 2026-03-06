"""
Input validation functions
"""
from typing import Tuple, List
import re
from urllib.parse import urlparse

import pandas as pd
import requests


def validate_url(url: str, check_reachable: bool = False) -> Tuple[bool, str]:
    """
    Validate URL format and optionally check if reachable.

    Returns:
        (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    parsed = urlparse(url)
    if not parsed.netloc:
        return False, "Invalid URL format - no domain found"

    # SSRF protection: block localhost and private IPs
    blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
    if parsed.netloc.lower() in blocked_hosts:
        return False, "Localhost URLs are not allowed"

    # Block private IP ranges
    if re.match(
        r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)", parsed.netloc
    ):
        return False, "Private IP addresses are not allowed"

    if check_reachable:
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code >= 400:
                return False, f"URL returned {response.status_code} status"
        except requests.RequestException as e:
            return False, f"URL is not reachable: {str(e)}"

    return True, ""


def validate_keyword(keyword: str) -> Tuple[bool, str]:
    """
    Validate keyword format.

    Returns:
        (is_valid, error_message)
    """
    if not keyword or not keyword.strip():
        return False, "Keyword cannot be empty"

    word_count = len(keyword.strip().split())
    if word_count > 10:
        return False, "Keyword should be 10 words or less"

    if not re.match(r"^[a-zA-Z0-9\s\-']+$", keyword):
        return False, "Keyword contains invalid characters"

    return True, ""


def validate_gsc_csv(df: pd.DataFrame) -> Tuple[bool, str, List[str]]:
    """
    Validate GSC CSV format.

    Returns:
        (is_valid, error_message, warnings_list)
    """
    warnings: List[str] = []

    # Check required columns (handle both GSC export formats)
    required_cols_v1 = ["Top queries", "Clicks", "Impressions", "CTR", "Position"]
    required_cols_v2 = ["Query", "Clicks", "Impressions", "CTR", "Average position"]

    has_v1 = all(col in df.columns for col in required_cols_v1)
    has_v2 = all(col in df.columns for col in required_cols_v2)

    if not (has_v1 or has_v2):
        return (
            False,
            "CSV missing required columns. Expected: Query, Clicks, Impressions, CTR, Position",
            [],
        )

    if len(df) == 0:
        return False, "CSV file is empty", []

    # Check numeric columns
    numeric_cols = ["Clicks", "Impressions"]
    for col in numeric_cols:
        if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
            warnings.append(f"Column '{col}' should be numeric")

    if "Clicks" in df.columns and df["Clicks"].max() > 1000000:
        warnings.append("Unusually high click counts (>1M) detected")

    return True, "", warnings


def validate_dataforseo_credentials(login: str, password: str) -> Tuple[bool, str]:
    """
    Test DataForSEO API credentials.

    Returns:
        (is_valid, error_message)
    """
    try:
        response = requests.get(
            "https://api.dataforseo.com/v3/appendix/user_data",
            auth=(login, password),
            timeout=10,
        )

        if response.status_code == 401:
            return False, "Invalid DataForSEO credentials"

        if response.status_code == 200:
            data = response.json()
            if "tasks" in data:
                return True, ""

        return False, f"Unexpected API response (status {response.status_code})"

    except requests.RequestException as e:
        return False, f"Could not connect to DataForSEO API: {str(e)}"

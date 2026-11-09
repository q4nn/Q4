from __future__ import annotations

from typing import Any

import requests

BASE = "https://api.rugcheck.xyz/v1"
HEADERS = {
    "User-Agent": "fomo-bot/0.1 (+paper-trading; research)",
    "Accept": "application/json",
}


def fetch_summary(mint: str, timeout: float = 12.0) -> dict[str, Any] | None:
    """Return RugCheck summary or None if unavailable."""
    url = f"{BASE}/tokens/{mint}/report/summary"
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        return data
    except requests.RequestException:
        return None

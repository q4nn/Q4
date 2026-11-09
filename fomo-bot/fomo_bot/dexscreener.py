from __future__ import annotations

import time
from typing import Any

import requests

BASE = "https://api.dexscreener.com"
HEADERS = {
    "User-Agent": "fomo-bot/0.1 (+paper-trading; research)",
    "Accept": "application/json",
}


class DexScreener:
    def __init__(self, timeout: float = 20.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.timeout = timeout
        self._last_call = 0.0

    def _get(self, path: str, params: dict | None = None) -> Any:
        # Soft rate limit: ~1 req / 200ms
        elapsed = time.time() - self._last_call
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        url = f"{BASE}{path}"
        r = self.session.get(url, params=params, timeout=self.timeout)
        self._last_call = time.time()
        r.raise_for_status()
        return r.json()

    def latest_profiles(self, limit: int = 40) -> list[dict]:
        data = self._get("/token-profiles/latest/v1")
        if not isinstance(data, list):
            return []
        return data[:limit]

    def latest_boosts(self, limit: int = 30) -> list[dict]:
        data = self._get("/token-boosts/latest/v1")
        if not isinstance(data, list):
            return []
        return data[:limit]

    def tokens(self, addresses: list[str]) -> list[dict]:
        if not addresses:
            return []
        # DexScreener accepts comma-separated mints
        joined = ",".join(addresses)
        data = self._get(f"/latest/dex/tokens/{joined}")
        return data.get("pairs") or []


def pick_best_solana_pair(pairs: list[dict], mint: str) -> dict | None:
    """Pick the highest-liquidity Solana pair for a given base mint."""
    candidates = []
    for p in pairs:
        if p.get("chainId") != "solana":
            continue
        base = (p.get("baseToken") or {}).get("address") or ""
        quote = (p.get("quoteToken") or {}).get("address") or ""
        if base.lower() != mint.lower() and quote.lower() != mint.lower():
            continue
        # Prefer pairs where mint is the base token
        if base.lower() != mint.lower():
            continue
        liq = ((p.get("liquidity") or {}).get("usd")) or 0
        candidates.append((liq, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def pair_age_minutes(pair: dict, now_ms: int | None = None) -> float | None:
    created = pair.get("pairCreatedAt")
    if not created:
        return None
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    return max(0.0, (now - int(created)) / 60000.0)

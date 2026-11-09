from __future__ import annotations

import time
from typing import Any

from fomo_bot.alerts import alert_candidate
from fomo_bot.dexscreener import DexScreener, pick_best_solana_pair
from fomo_bot.paper import PaperTrader
from fomo_bot.rugcheck import fetch_summary
from fomo_bot.scorer import build_candidate, passes_filters, score_candidate


def collect_solana_mints(dex: DexScreener, limit: int) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in dex.latest_profiles(limit=limit) + dex.latest_boosts(limit=limit):
        if item.get("chainId") != "solana":
            continue
        mint = item.get("tokenAddress")
        if not mint or mint in seen:
            continue
        seen.add(mint)
        ordered.append(mint)
    return ordered


def scan_once(cfg: dict[str, Any], paper: PaperTrader | None = None) -> list:
    scan_cfg = cfg.get("scan", {})
    filters = cfg.get("filters", {})
    scoring = cfg.get("scoring", {})
    alerts_cfg = cfg.get("alerts", {})

    dex = DexScreener()
    mints = collect_solana_mints(dex, limit=int(scan_cfg.get("profile_limit", 40)))
    print(f"[scan] {len(mints)} unique Solana mints from profiles/boosts")

    batch_size = int(scan_cfg.get("batch_size", 20))
    pairs_all: list[dict] = []
    for i in range(0, len(mints), batch_size):
        chunk = mints[i : i + batch_size]
        try:
            pairs_all.extend(dex.tokens(chunk))
        except Exception as e:  # noqa: BLE001
            print(f"[scan] token batch error: {e}")

    # Manage existing paper positions every pass
    if paper is not None:
        try:
            paper.mark_and_manage(dex)
        except Exception as e:  # noqa: BLE001
            print(f"[paper] manage error: {e}")

    hits = []
    checked = 0
    for mint in mints:
        pair = pick_best_solana_pair(pairs_all, mint)
        if not pair:
            continue
        checked += 1
        rug = None
        if filters.get("use_rugcheck", True):
            rug = fetch_summary(mint)
        cand = build_candidate(mint, pair, rug=rug)
        if not passes_filters(cand, filters):
            continue
        score_candidate(cand, scoring)
        if cand.score < float(scoring.get("min_score", 55)):
            continue
        hits.append(cand)
        alert_candidate(cand, alerts_cfg)
        if paper is not None:
            paper.maybe_buy(cand)

    hits.sort(key=lambda c: c.score, reverse=True)
    print(f"[scan] checked {checked} pairs with data; {len(hits)} passed filters+score")
    if not hits:
        # Show a few near-misses for visibility
        print("[scan] no alerts this pass (filters may be strict — see config.yaml)")
    return hits


def run_loop(cfg: dict[str, Any], paper: PaperTrader | None = None) -> None:
    poll = int(cfg.get("scan", {}).get("poll_seconds", 45))
    print(f"[run] polling every {poll}s — Ctrl+C to stop")
    while True:
        try:
            scan_once(cfg, paper=paper)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"[run] error: {e}")
        time.sleep(poll)

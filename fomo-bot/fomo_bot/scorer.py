from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fomo_bot.dexscreener import pair_age_minutes


@dataclass
class Candidate:
    mint: str
    symbol: str
    name: str
    pair: dict
    age_min: float | None
    liquidity_usd: float
    volume_h1: float
    buys_m5: int
    sells_m5: int
    buy_sell_ratio: float
    price_usd: float | None
    fdv: float | None
    price_change_h1: float | None
    rug: dict | None = None
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)
    url: str = ""

    def to_alert_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "mint": self.mint,
            "score": round(self.score, 1),
            "price_usd": self.price_usd,
            "liquidity_usd": round(self.liquidity_usd, 2),
            "volume_h1": round(self.volume_h1, 2),
            "buys_m5": self.buys_m5,
            "sells_m5": self.sells_m5,
            "buy_sell_ratio": round(self.buy_sell_ratio, 2),
            "age_min": None if self.age_min is None else round(self.age_min, 1),
            "fdv": self.fdv,
            "price_change_h1": self.price_change_h1,
            "rug_score": None if not self.rug else self.rug.get("score"),
            "lp_locked_pct": None if not self.rug else self.rug.get("lpLockedPct"),
            "reasons": self.reasons,
            "url": self.url,
        }


def build_candidate(mint: str, pair: dict, rug: dict | None = None) -> Candidate:
    base = pair.get("baseToken") or {}
    liq = float(((pair.get("liquidity") or {}).get("usd")) or 0)
    vol = float(((pair.get("volume") or {}).get("h1")) or 0)
    tx_m5 = ((pair.get("txns") or {}).get("m5")) or {}
    buys = int(tx_m5.get("buys") or 0)
    sells = int(tx_m5.get("sells") or 0)
    ratio = (buys / sells) if sells > 0 else float(buys)
    price = pair.get("priceUsd")
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None
    fdv = pair.get("fdv")
    try:
        fdv_f = float(fdv) if fdv is not None else None
    except (TypeError, ValueError):
        fdv_f = None
    pc = (pair.get("priceChange") or {}).get("h1")
    try:
        pc_f = float(pc) if pc is not None else None
    except (TypeError, ValueError):
        pc_f = None

    return Candidate(
        mint=mint,
        symbol=base.get("symbol") or "?",
        name=base.get("name") or "?",
        pair=pair,
        age_min=pair_age_minutes(pair),
        liquidity_usd=liq,
        volume_h1=vol,
        buys_m5=buys,
        sells_m5=sells,
        buy_sell_ratio=ratio,
        price_usd=price_f,
        fdv=fdv_f,
        price_change_h1=pc_f,
        rug=rug,
        url=pair.get("url") or f"https://dexscreener.com/solana/{mint}",
    )


def passes_filters(c: Candidate, filters: dict) -> bool:
    fails: list[str] = []
    min_liq = float(filters.get("min_liquidity_usd", 0))
    max_liq = float(filters.get("max_liquidity_usd", 1e18))
    if c.liquidity_usd < min_liq:
        fails.append(f"liq<{min_liq}")
    if c.liquidity_usd > max_liq:
        fails.append(f"liq>{max_liq}")
    if c.age_min is None:
        fails.append("no_age")
    else:
        if c.age_min < float(filters.get("min_pair_age_minutes", 0)):
            fails.append("too_new")
        if c.age_min > float(filters.get("max_pair_age_minutes", 1e9)):
            fails.append("too_old")
    if c.buys_m5 < int(filters.get("min_buys_m5", 0)):
        fails.append("few_buys")
    if c.buy_sell_ratio < float(filters.get("min_buy_sell_ratio_m5", 0)):
        fails.append("weak_buy_pressure")
    if c.volume_h1 < float(filters.get("min_volume_h1_usd", 0)):
        fails.append("low_vol")
    max_fdv = filters.get("max_fdv_usd")
    if max_fdv is not None and c.fdv is not None and c.fdv > float(max_fdv):
        fails.append("fdv_high")
    if c.price_usd is None or c.price_usd <= 0:
        fails.append("no_price")

    if filters.get("use_rugcheck") and c.rug is not None:
        score = c.rug.get("score")
        max_score = filters.get("max_rugcheck_score")
        if score is not None and max_score is not None and float(score) > float(max_score):
            fails.append(f"rug_score>{max_score}")
        if filters.get("require_lp_locked"):
            locked = float(c.rug.get("lpLockedPct") or 0)
            if locked < 50:
                fails.append("lp_unlocked")

    c.failed_filters = fails
    return not fails


def score_candidate(c: Candidate, scoring: dict) -> float:
    """Heuristic 0-100 score from liquidity, momentum, buy pressure, safety."""
    reasons: list[str] = []

    # Liquidity component (sweet spot ~10k-100k)
    w_liq = float(scoring.get("weight_liquidity", 20))
    if c.liquidity_usd <= 0:
        liq_s = 0.0
    elif c.liquidity_usd < 10_000:
        liq_s = 40 + 40 * (c.liquidity_usd / 10_000)
    elif c.liquidity_usd <= 100_000:
        liq_s = 80 + 20 * ((c.liquidity_usd - 10_000) / 90_000)
    else:
        liq_s = max(40.0, 100 - (c.liquidity_usd - 100_000) / 20_000)
    if c.liquidity_usd >= 10_000:
        reasons.append("solid_liq")

    # Momentum: volume vs liquidity + price change
    w_mom = float(scoring.get("weight_momentum", 35))
    turn = (c.volume_h1 / c.liquidity_usd) if c.liquidity_usd > 0 else 0
    mom_s = min(100.0, turn * 40)
    if c.price_change_h1 is not None:
        if c.price_change_h1 > 20:
            mom_s = min(100.0, mom_s + 25)
            reasons.append("hot_price")
        elif c.price_change_h1 > 5:
            mom_s = min(100.0, mom_s + 10)
    if turn >= 1.0:
        reasons.append("high_turnover")

    # Buy pressure
    w_buy = float(scoring.get("weight_buy_pressure", 25))
    ratio = c.buy_sell_ratio
    if ratio >= 3:
        buy_s = 100.0
        reasons.append("strong_buys")
    elif ratio >= 2:
        buy_s = 80.0
        reasons.append("buy_heavy")
    elif ratio >= 1.2:
        buy_s = 55.0
    else:
        buy_s = max(0.0, ratio * 40)
    # Extra for raw buy count
    buy_s = min(100.0, buy_s + min(20.0, c.buys_m5 / 5))

    # Safety from RugCheck (missing rug => neutral 50)
    w_safe = float(scoring.get("weight_safety", 20))
    if c.rug is None:
        safe_s = 50.0
    else:
        rscore = float(c.rug.get("score") or 0)
        # RugCheck raw scores: lower better; map roughly
        if rscore <= 1:
            safe_s = 95.0
            reasons.append("rug_clean")
        elif rscore <= 100:
            safe_s = 80.0
        elif rscore <= 500:
            safe_s = 55.0
        else:
            safe_s = max(0.0, 40 - rscore / 50)
        locked = float(c.rug.get("lpLockedPct") or 0)
        if locked >= 90:
            safe_s = min(100.0, safe_s + 10)
            reasons.append("lp_locked")
        risks = c.rug.get("risks") or []
        if risks:
            safe_s = max(0.0, safe_s - 10 * len(risks))
            reasons.append(f"risks:{len(risks)}")

    total_w = w_liq + w_mom + w_buy + w_safe
    score = (liq_s * w_liq + mom_s * w_mom + buy_s * w_buy + safe_s * w_safe) / total_w
    # Freshness bonus for young pairs that still pass filters
    if c.age_min is not None and c.age_min <= 60:
        score = min(100.0, score + 5)
        reasons.append("fresh")

    c.score = score
    c.reasons = reasons
    return score

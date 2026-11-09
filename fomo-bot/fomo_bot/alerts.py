from __future__ import annotations

import os
from typing import Any

import requests

from fomo_bot.scorer import Candidate


def format_candidate(c: Candidate) -> str:
    d = c.to_alert_dict()
    lines = [
        f"[{d['score']}] ${d['symbol']} ({d['name']})",
        f"  mint: {d['mint']}",
        f"  price: ${d['price_usd']} | liq: ${d['liquidity_usd']:,.0f} | vol1h: ${d['volume_h1']:,.0f}",
        f"  m5 buys/sells: {d['buys_m5']}/{d['sells_m5']} (ratio {d['buy_sell_ratio']})",
        f"  age: {d['age_min']} min | fdv: {d['fdv']} | Δ1h: {d['price_change_h1']}%",
        f"  rug score: {d['rug_score']} | lp locked: {d['lp_locked_pct']}%",
        f"  reasons: {', '.join(d['reasons']) or '-'}",
        f"  {d['url']}",
    ]
    return "\n".join(lines)


def console_alert(c: Candidate) -> None:
    print("\n=== ALERT ===")
    print(format_candidate(c))
    print("=============\n")


def telegram_alert(c: Candidate, enabled: bool = True) -> bool:
    if not enabled:
        return False
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    text = format_candidate(c)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=15,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def alert_candidate(c: Candidate, alerts_cfg: dict[str, Any]) -> None:
    if alerts_cfg.get("console", True):
        console_alert(c)
    if alerts_cfg.get("telegram", True):
        telegram_alert(c, enabled=True)

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fomo_bot.dexscreener import DexScreener, pick_best_solana_pair
from fomo_bot.scorer import Candidate


def _now() -> float:
    return time.time()


class PaperTrader:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.path = Path(cfg.get("positions_file", "data/positions.json"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            with self.path.open() as f:
                return json.load(f)
        return {"cash_spent": 0.0, "cash_realized": 0.0, "positions": [], "closed": []}

    def save(self) -> None:
        with self.path.open("w") as f:
            json.dump(self.state, f, indent=2)

    def open_positions(self) -> list[dict]:
        return [p for p in self.state["positions"] if p.get("status") == "open"]

    def already_holding(self, mint: str) -> bool:
        return any(p["mint"] == mint and p.get("status") == "open" for p in self.state["positions"])

    def maybe_buy(self, c: Candidate) -> dict | None:
        if not self.cfg.get("enabled", True):
            return None
        if self.already_holding(c.mint):
            return None
        if c.price_usd is None or c.price_usd <= 0:
            return None
        if len(self.open_positions()) >= int(self.cfg.get("max_open_positions", 10)):
            return None

        buy_usd = float(self.cfg.get("buy_usd", 50))
        qty = buy_usd / c.price_usd
        pos = {
            "id": f"{c.mint[:8]}-{int(_now())}",
            "mint": c.mint,
            "symbol": c.symbol,
            "entry_price": c.price_usd,
            "qty": qty,
            "qty_remaining": qty,
            "cost_usd": buy_usd,
            "opened_at": _now(),
            "status": "open",
            "tp_hits": [],
            "url": c.url,
            "entry_score": round(c.score, 1),
        }
        self.state["positions"].append(pos)
        self.state["cash_spent"] = float(self.state.get("cash_spent", 0)) + buy_usd
        self.save()
        print(f"[paper] BUY ${buy_usd:.2f} of {c.symbol} @ ${c.price_usd} (score {c.score:.1f})")
        return pos

    def mark_and_manage(self, dex: DexScreener) -> None:
        opens = self.open_positions()
        if not opens:
            return
        # Batch price refresh
        mints = list({p["mint"] for p in opens})
        pairs = dex.tokens(mints)
        price_map: dict[str, float] = {}
        for mint in mints:
            best = pick_best_solana_pair(pairs, mint)
            if best and best.get("priceUsd"):
                try:
                    price_map[mint] = float(best["priceUsd"])
                except (TypeError, ValueError):
                    pass

        tps = [float(x) for x in self.cfg.get("take_profit_multiples", [2.0, 5.0])]
        stop = float(self.cfg.get("stop_loss_pct", 0.4))

        for pos in opens:
            price = price_map.get(pos["mint"])
            if price is None:
                continue
            entry = float(pos["entry_price"])
            mult = price / entry if entry > 0 else 0
            # Stop loss: full exit
            if mult <= (1.0 - stop):
                self._close(pos, price, reason=f"stop_loss ({mult:.2f}x)")
                continue
            # Take profits: first TP sells half remaining, last TP closes rest
            for i, tp in enumerate(tps):
                key = f"tp_{tp}"
                if key in pos.get("tp_hits", []):
                    continue
                if mult < tp:
                    continue
                is_last = i == len(tps) - 1
                frac = 1.0 if is_last else 0.5
                self._partial_sell(pos, price, frac=frac, reason=f"take_profit {tp}x")
                pos.setdefault("tp_hits", []).append(key)
                if pos["qty_remaining"] <= 0:
                    break
        self.save()

    def _partial_sell(self, pos: dict, price: float, frac: float, reason: str) -> None:
        qty = float(pos["qty_remaining"]) * frac
        if qty <= 0:
            return
        proceeds = qty * price
        pos["qty_remaining"] = float(pos["qty_remaining"]) - qty
        self.state["cash_realized"] = float(self.state.get("cash_realized", 0)) + proceeds
        print(
            f"[paper] SELL {pos['symbol']} qty={qty:.4f} @ ${price} -> ${proceeds:.2f} ({reason})"
        )
        if pos["qty_remaining"] <= 1e-12:
            self._finalize(pos, reason)

    def _close(self, pos: dict, price: float, reason: str) -> None:
        self._partial_sell(pos, price, frac=1.0, reason=reason)

    def _finalize(self, pos: dict, reason: str) -> None:
        pos["status"] = "closed"
        pos["closed_at"] = _now()
        pos["close_reason"] = reason
        pos["qty_remaining"] = 0.0
        self.state.setdefault("closed", []).append(pos)

    def report(self, dex: DexScreener | None = None) -> str:
        opens = self.open_positions()
        price_map: dict[str, float] = {}
        if dex and opens:
            mints = list({p["mint"] for p in opens})
            pairs = dex.tokens(mints)
            for mint in mints:
                best = pick_best_solana_pair(pairs, mint)
                if best and best.get("priceUsd"):
                    try:
                        price_map[mint] = float(best["priceUsd"])
                    except (TypeError, ValueError):
                        pass

        unrealized = 0.0
        lines = ["=== Paper trading report ==="]
        lines.append(f"Cash spent:    ${float(self.state.get('cash_spent', 0)):.2f}")
        lines.append(f"Cash realized: ${float(self.state.get('cash_realized', 0)):.2f}")
        lines.append(f"Open positions: {len(opens)}")
        for pos in opens:
            px = price_map.get(pos["mint"], pos["entry_price"])
            value = float(pos["qty_remaining"]) * float(px)
            cost_left = float(pos["cost_usd"]) * (
                float(pos["qty_remaining"]) / float(pos["qty"]) if pos["qty"] else 0
            )
            pnl = value - cost_left
            unrealized += pnl
            mult = float(px) / float(pos["entry_price"]) if pos["entry_price"] else 0
            lines.append(
                f"  {pos['symbol']:10} entry ${pos['entry_price']} now ${px} "
                f"({mult:.2f}x) uPnL ${pnl:.2f} [{pos['mint'][:8]}…]"
            )
        closed = self.state.get("closed") or []
        lines.append(f"Closed trades: {len(closed)}")
        realized_pnl = float(self.state.get("cash_realized", 0)) - float(
            self.state.get("cash_spent", 0)
        )
        # More accurate: spent on closed + remaining cost basis
        open_cost = sum(
            float(p["cost_usd"]) * (float(p["qty_remaining"]) / float(p["qty"]) if p["qty"] else 0)
            for p in opens
        )
        closed_cost = float(self.state.get("cash_spent", 0)) - open_cost
        closed_pnl = float(self.state.get("cash_realized", 0)) - closed_cost
        lines.append(f"Unrealized PnL: ${unrealized:.2f}")
        lines.append(f"Realized PnL (approx): ${closed_pnl:.2f}")
        lines.append(f"Equity mark (realized cash + open value): "
                     f"${float(self.state.get('cash_realized', 0)) + sum(float(p['qty_remaining']) * float(price_map.get(p['mint'], p['entry_price'])) for p in opens):.2f}")
        lines.append(f"Positions file: {self.path}")
        return "\n".join(lines)

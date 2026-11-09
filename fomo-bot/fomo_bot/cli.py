from __future__ import annotations

import argparse
import sys

from fomo_bot.config import load_config
from fomo_bot.dexscreener import DexScreener
from fomo_bot.paper import PaperTrader
from fomo_bot.scanner import run_loop, scan_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fomo_bot",
        description="Solana memecoin launch scanner + paper trader (no real trades).",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config.yaml (default: project config.yaml)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="Single scan pass + optional paper buys")
    sub.add_parser("run", help="Loop scan forever")
    sub.add_parser("report", help="Print paper trading PnL")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    paper = PaperTrader(cfg.get("paper", {}))

    if args.cmd == "scan":
        scan_once(cfg, paper=paper)
        return 0
    if args.cmd == "run":
        try:
            run_loop(cfg, paper=paper)
        except KeyboardInterrupt:
            print("\n[run] stopped")
        return 0
    if args.cmd == "report":
        print(paper.report(DexScreener()))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

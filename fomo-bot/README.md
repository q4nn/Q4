# FOMO Bot

Solana memecoin **launch scanner + alerts + paper trader**.

This does **not** guarantee profit. Memecoins are extremely high risk; most go to zero. There is **no real trading** and **no private keys**. Paper trades are simulated locally so you can test filters without putting money on the line.

## What it does

1. Pulls latest Solana token profiles / boosts from the public [DexScreener](https://dexscreener.com) API.
2. Fetches pair stats (liquidity, volume, buys/sells, age, FDV, price change).
3. Optionally checks [RugCheck](https://rugcheck.xyz) summary scores (no API key).
4. Applies configurable filters and a 0–100 risk/momentum score.
5. Alerts on console (and Telegram if env vars are set).
6. Paper-buys a fixed USD size, tracks positions in JSON, applies take-profit / stop-loss.

## Setup

```bash
cd fomo-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional Telegram alerts:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

If those are unset, Telegram is skipped automatically.

## Usage

```bash
# One scan pass (alerts + paper buys for hits)
python -m fomo_bot scan

# Continuous loop (poll interval from config.yaml)
python -m fomo_bot run

# Paper PnL report
python -m fomo_bot report
```

Custom config:

```bash
python -m fomo_bot -c /path/to/config.yaml scan
```

## Config (`config.yaml`)

| Section | Purpose |
|--------|---------|
| `scan` | Poll interval, how many latest profiles to pull, batch size |
| `filters` | Min/max liquidity, pair age, buys, buy/sell ratio, volume, FDV, RugCheck |
| `scoring` | Min score to alert/trade; weights for liquidity / momentum / buys / safety |
| `paper` | Buy size USD, take-profit multiples, stop-loss %, max open positions, file path |
| `alerts` | Console on/off; Telegram on/off (still needs env vars) |

Tune filters stricter if you get too many alerts; looser if you get none.

## Data

Paper state defaults to `data/positions.json` under the project root.

## APIs used (no keys)

- `GET https://api.dexscreener.com/token-profiles/latest/v1`
- `GET https://api.dexscreener.com/token-boosts/latest/v1`
- `GET https://api.dexscreener.com/latest/dex/tokens/{mint,...}`
- `GET https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary`

DexScreener may rate-limit or return empty liquidity/price for brand-new pump.fun pairs. RugCheck may 404 or omit fields for very new mints — the bot treats missing rug data as neutral, not a hard fail.

## Risk disclaimer

- **No bot can promise 100x** (or any return).
- Past filters or paper PnL say nothing about future results.
- Do not paste seed phrases or private keys into this project.
- If you later wire real trading, you can lose everything. This repo intentionally does not do that.

## License

MIT — use at your own risk.

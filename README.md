# Q4
for i in {1..20}
do
  mkdir repo-$i
  cd repo-$i

  echo "# Repo $i" > README.md
  echo "print('Hello from repo $i')" > app.py

  git init
  git add .
  git commit -m "init repo $i"

  gh repo create repo-$i --public --source=. --push

  cd ..
done

## FOMO Bot

A Solana memecoin launch scanner (DexScreener + RugCheck, scoring, console/Telegram alerts, and paper trading) lives in [`fomo-bot/`](fomo-bot/). See [fomo-bot/README.md](fomo-bot/README.md).

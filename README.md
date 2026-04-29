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

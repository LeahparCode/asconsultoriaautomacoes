#!/usr/bin/env bash
# Commita e envia status/hoje.json (atualizado por atualizar_status.py) de
# volta pro repositório. Usado pelos 4 workflows diários depois de rodar.
# Best-effort: se não conseguir enviar (ex: conflito persistente), avisa
# mas não derruba o workflow — o resumo diário só fica sem esse dado.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add status/hoje.json

if git diff --cached --quiet; then
  echo "Status sem mudança, nada pra commitar."
  exit 0
fi

git commit -m "status: atualiza resumo do dia" --quiet

for tentativa in 1 2 3; do
  if git push origin HEAD:Nomain --quiet; then
    echo "Status enviado."
    exit 0
  fi
  echo "Push falhou (provável conflito com outro workflow), tentando de novo (${tentativa}/3)..."
  git pull --rebase origin Nomain --quiet
  sleep 5
done

echo "Aviso: não consegui enviar o status depois de 3 tentativas (não interrompe o workflow)."
exit 0

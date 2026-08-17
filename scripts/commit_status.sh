#!/usr/bin/env bash
# Grava o resultado de uma automação em status/hoje.json na branch Nomain.
#
# Uso: bash scripts/commit_status.sh <chave> <sucesso|falha> [--contagens <arquivo.json>]
#
# SEGURANÇA: o commit é montado numa worktree separada, criada a partir do
# origin/Nomain recém-baixado, e o push é sempre "essa worktree -> Nomain".
# Assim ele NUNCA carrega junto os commits da branch em que o workflow está
# rodando. A versão anterior fazia "git push origin HEAD:Nomain" direto da
# branch atual — rodando numa branch de teste, isso tentou empurrar código de
# diagnóstico pra produção (só não foi porque deu conflito).
#
# Best-effort: se não der pra enviar, avisa e sai com 0 — registrar status é
# informativo e não pode derrubar uma automação que funcionou.
set -uo pipefail

if [ "$#" -lt 2 ]; then
  echo "Uso: commit_status.sh <chave> <sucesso|falha> [--contagens <arquivo.json>]"
  exit 0
fi

RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"

CHAVE="$1"
VALOR="$2"
shift 2

# --contagens vem relativo ao repo; resolve pra caminho absoluto porque o
# script vai rodar de dentro da worktree temporária.
ARGS_EXTRA=()
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--contagens" ] && [ "$#" -ge 2 ]; then
    CAMINHO_CONTAGENS="$2"
    [ -f "$CAMINHO_CONTAGENS" ] && CAMINHO_CONTAGENS="$(cd "$(dirname "$CAMINHO_CONTAGENS")" && pwd)/$(basename "$CAMINHO_CONTAGENS")"
    ARGS_EXTRA+=("--contagens" "$CAMINHO_CONTAGENS")
    shift 2
  else
    ARGS_EXTRA+=("$1")
    shift
  fi
done

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

WORKTREE="$(mktemp -d)"
limpar() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || rm -rf "$WORKTREE"
}
trap limpar EXIT

for tentativa in 1 2 3; do
  git fetch origin Nomain --quiet || true

  limpar
  WORKTREE="$(mktemp -d)"
  rmdir "$WORKTREE"
  if ! git worktree add --detach "$WORKTREE" origin/Nomain --quiet 2>/dev/null; then
    echo "Aviso: não consegui preparar a worktree do status (não interrompe o workflow)."
    exit 0
  fi

  # Reaplica a chave por cima do status que já está em Nomain, pra não
  # sobrescrever o que outra automação gravou hoje.
  ( cd "$WORKTREE" && python3 "$RAIZ/scripts/atualizar_status.py" "$CHAVE" "$VALOR" "${ARGS_EXTRA[@]+"${ARGS_EXTRA[@]}"}" )

  ( cd "$WORKTREE" && git add status/hoje.json )
  if ( cd "$WORKTREE" && git diff --cached --quiet ); then
    echo "Status sem mudança, nada pra commitar."
    exit 0
  fi

  ( cd "$WORKTREE" && git commit -m "status: ${CHAVE}=${VALOR}" --quiet )

  if ( cd "$WORKTREE" && git push origin HEAD:Nomain --quiet ); then
    echo "Status enviado."
    exit 0
  fi

  echo "Push do status falhou (provável concorrência com outro workflow), tentando de novo (${tentativa}/3)..."
  sleep 5
done

echo "Aviso: não consegui enviar o status depois de 3 tentativas (não interrompe o workflow)."
exit 0

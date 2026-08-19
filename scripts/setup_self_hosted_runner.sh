#!/usr/bin/env bash
# Prepara uma VM Ubuntu nova (ex: Oracle Cloud Always Free) pra rodar como
# runner self-hosted do GitHub Actions, com tudo que os 4 scripts de
# automação (Selenium/Playwright + Chrome headless) precisam.
#
# Rode como o usuário normal (ex: "ubuntu"), NÃO como root — o script usa
# sudo internamente quando precisa.
#
# Uso:
#   chmod +x setup_self_hosted_runner.sh
#   ./setup_self_hosted_runner.sh <URL_DO_REPO> <TOKEN_DE_REGISTRO> [nome-do-runner]
#
# Onde pegar a URL e o token:
#   GitHub → repositório → Settings → Actions → Runners →
#   "New self-hosted runner" → Linux → o token aparece no comando
#   "./config.sh --url ... --token XXXX" que a página mostra.
#   Esse token expira em ~1 hora, então gere ele pouco antes de rodar
#   este script.
#
# O que este script faz:
#   1. Atualiza o sistema
#   2. Cria um arquivo de swap de 4GB (a VM gratuita tem só 1GB de RAM,
#      e o Chrome headless precisa de folga pra não travar)
#   3. Instala as bibliotecas do sistema que o Chrome headless exige
#      (a etapa "Instalar Google Chrome" dos workflows só baixa o
#      binário do Chrome; sem essas libs ele não abre)
#   4. Baixa e configura o runner do GitHub Actions
#   5. Instala o runner como serviço do systemd, pra sobreviver a reboot
#      e ficar sempre ouvindo por novos jobs
set -euo pipefail

REPO_URL="${1:?Uso: ./setup_self_hosted_runner.sh <URL_DO_REPO> <TOKEN_DE_REGISTRO> [nome-do-runner]}"
RUNNER_TOKEN="${2:?Uso: ./setup_self_hosted_runner.sh <URL_DO_REPO> <TOKEN_DE_REGISTRO> [nome-do-runner]}"
RUNNER_NAME="${3:-vm-automacoes}"
RUNNER_DIR="$HOME/actions-runner"

echo "==> [1/5] Atualizando pacotes do sistema..."
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> [2/5] Configurando swap de 4GB (se ainda não existir)..."
if [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
  echo "    Swap criado e ativado."
else
  echo "    Swap já existe, pulando."
fi

echo "==> [3/5] Instalando dependências do Chrome headless e do Python..."
sudo apt-get install -y \
  curl wget git unzip jq \
  python3 python3-pip python3-venv \
  fonts-liberation libnss3 libatk-bridge2.0-0 libatk1.0-0 \
  libcups2 libdrm2 libgbm1 libasound2t64 libpangocairo-1.0-0 \
  libxss1 libxtst6 libxrandr2 libu2f-udev libvulkan1 \
  xdg-utils libgtk-3-0 libx11-xcb1

echo "==> [4/5] Baixando e configurando o runner do GitHub Actions..."
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

ARCH="$(dpkg --print-architecture)"  # amd64 ou arm64
LATEST_VERSION="$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//')"
echo "    Versão mais recente do runner: ${LATEST_VERSION} (arquitetura: ${ARCH})"

curl -fsSL -o actions-runner.tar.gz \
  "https://github.com/actions/runner/releases/download/v${LATEST_VERSION}/actions-runner-linux-${ARCH}-${LATEST_VERSION}.tar.gz"
tar xzf actions-runner.tar.gz
rm actions-runner.tar.gz

./config.sh --url "$REPO_URL" --token "$RUNNER_TOKEN" --name "$RUNNER_NAME" \
  --labels self-hosted --work _work --unattended --replace

echo "==> [5/5] Instalando o runner como serviço (fica ouvindo mesmo após reboot)..."
sudo ./svc.sh install
sudo ./svc.sh start

echo
echo "=================================================================="
echo " Pronto! O runner '${RUNNER_NAME}' está rodando como serviço."
echo " Confira em: GitHub → repositório → Settings → Actions → Runners"
echo " (deve aparecer com uma bolinha verde 'Idle')."
echo
echo " Comandos úteis (dentro de $RUNNER_DIR):"
echo "   sudo ./svc.sh status   -> ver se está rodando"
echo "   sudo ./svc.sh stop     -> parar"
echo "   sudo ./svc.sh start    -> iniciar de novo"
echo "=================================================================="
sudo ./svc.sh status

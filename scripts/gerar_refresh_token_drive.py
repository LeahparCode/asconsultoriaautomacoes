#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ferramenta local — rodar UMA ÚNICA VEZ, no seu computador (não faz parte
de nenhum workflow do GitHub Actions).

Gera o "refresh token" que as automações usam para enviar arquivos ao
Google Drive como se fossem você mesmo (sua conta Google normal), sem
precisar de conta de serviço nem de admin do Google Workspace.

Pré-requisitos:
    1. No Google Cloud Console (mesmo projeto da API do Drive já ativada):
       APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth
       → tipo de aplicativo "Aplicativo para computador" (Desktop app).
       Se pedir pra configurar a "Tela de consentimento OAuth" antes, escolha
       tipo "Externo", preencha nome/e-mail, e adicione seu próprio e-mail
       como "usuário de teste" — não precisa publicar o app.
    2. Copie o "Client ID" e o "Client secret" gerados e cole abaixo (ou
       exporte como variáveis de ambiente GDRIVE_OAUTH_CLIENT_ID /
       GDRIVE_OAUTH_CLIENT_SECRET antes de rodar).

Como rodar:
    pip install google-auth-oauthlib google-api-python-client
    python gerar_refresh_token_drive.py

Vai abrir o navegador pedindo pra você logar com a conta Google que tem
acesso às pastas de destino (Relatórios EVO, PBI, Agendamentos) e
autorizar o acesso ao Drive. No final, o refresh token aparece aqui no
terminal — copie e cole no Secret GDRIVE_OAUTH_REFRESH_TOKEN do GitHub.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]

CLIENT_ID = os.environ.get("GDRIVE_OAUTH_CLIENT_ID") or "COLE_AQUI_O_CLIENT_ID"
CLIENT_SECRET = os.environ.get("GDRIVE_OAUTH_CLIENT_SECRET") or "COLE_AQUI_O_CLIENT_SECRET"


def main():
    if "COLE_AQUI" in CLIENT_ID or "COLE_AQUI" in CLIENT_SECRET:
        raise SystemExit(
            "Preencha CLIENT_ID e CLIENT_SECRET no topo deste arquivo (ou exporte "
            "GDRIVE_OAUTH_CLIENT_ID / GDRIVE_OAUTH_CLIENT_SECRET) antes de rodar."
        )

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print("Autorização concluída!")
    print("=" * 60)
    print("\nCadastre estes 3 Secrets no GitHub (Settings → Secrets and")
    print("variables → Actions):\n")
    print(f"GDRIVE_OAUTH_CLIENT_ID={CLIENT_ID}")
    print(f"GDRIVE_OAUTH_CLIENT_SECRET={CLIENT_SECRET}")
    print(f"GDRIVE_OAUTH_REFRESH_TOKEN={credentials.refresh_token}")


if __name__ == "__main__":
    main()

"""
Utilitário de upload para o Google Drive.

O upload é "best-effort": se a credencial não estiver configurada ou o upload
falhar por qualquer motivo, apenas um aviso é impresso e o script principal
continua rodando (o arquivo já está salvo localmente e também sobe como
artefato do GitHub Actions).

Três formas de autenticar, tentadas nesta ordem:

1. OAuth como usuário real (GDRIVE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN) —
   a automação age como se fosse você mesmo, usando sua própria cota. Não
   exige Google Workspace nem conta de serviço. Veja
   scripts/gerar_refresh_token_drive.py para gerar o refresh token.
2. Conta de serviço com Delegação em todo o domínio (GDRIVE_IMPERSONATE_USER)
   — a conta de serviço age como um usuário Workspace real. Exige que um
   admin do Workspace autorize no Admin Console.
3. Conta de serviço "pura" — só funciona se a pasta de destino estiver
   dentro de uma Drive Compartilhada (Shared Drive), já que contas de
   serviço não têm cota de armazenamento própria no Meu Drive de ninguém.
"""

import json
import os

GDRIVE_OAUTH_CLIENT_ID = os.environ.get("GDRIVE_OAUTH_CLIENT_ID")
GDRIVE_OAUTH_CLIENT_SECRET = os.environ.get("GDRIVE_OAUTH_CLIENT_SECRET")
GDRIVE_OAUTH_REFRESH_TOKEN = os.environ.get("GDRIVE_OAUTH_REFRESH_TOKEN")
GDRIVE_IMPERSONATE_USER = os.environ.get("GDRIVE_IMPERSONATE_USER")

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    from googleapiclient.discovery import build

    if GDRIVE_OAUTH_REFRESH_TOKEN and GDRIVE_OAUTH_CLIENT_ID and GDRIVE_OAUTH_CLIENT_SECRET:
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=None,
            refresh_token=GDRIVE_OAUTH_REFRESH_TOKEN,
            client_id=GDRIVE_OAUTH_CLIENT_ID,
            client_secret=GDRIVE_OAUTH_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    creds_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("Aviso: nenhuma credencial do Google Drive configurada — pulando upload.")
        return None

    from google.oauth2 import service_account

    info = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if GDRIVE_IMPERSONATE_USER:
        credentials = credentials.with_subject(GDRIVE_IMPERSONATE_USER)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def find_file(service, name, parent_id):
    escaped = name.replace("'", "\\'")
    query = f"name = '{escaped}' and '{parent_id}' in parents and trashed = false"
    resp = service.files().list(
        q=query,
        fields="files(id, name)",
        spaces="drive",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def find_or_create_folder(service, name, parent_id):
    query = (
        f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    resp = service.files().list(
        q=query,
        fields="files(id, name)",
        spaces="drive",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    folder = service.files().create(body=metadata, fields="id", supportsAllDrives=True).execute()
    return folder["id"]


def upload_file(local_path, parent_folder_id, filename=None, subfolder_name=None):
    """Envia local_path direto para dentro de parent_folder_id (sem subpasta por
    data). Se já existir um arquivo com o mesmo nome nessa pasta, o conteúdo
    dele é substituído (mesmo ID do arquivo) em vez de criar uma cópia nova —
    assim, rodar de novo no mesmo dia atualiza o arquivo já baixado."""
    if not parent_folder_id:
        print("Aviso: ID da pasta do Google Drive não configurado — pulando upload.")
        return None

    service = _get_service()
    if service is None:
        return None

    try:
        from googleapiclient.http import MediaFileUpload

        target_parent = parent_folder_id
        if subfolder_name:
            target_parent = find_or_create_folder(service, subfolder_name, parent_folder_id)

        nome = filename or os.path.basename(local_path)
        media = MediaFileUpload(local_path, resumable=True)

        existente_id = find_file(service, nome, target_parent)
        if existente_id:
            uploaded = service.files().update(
                fileId=existente_id, media_body=media, fields="id, webViewLink", supportsAllDrives=True
            ).execute()
            print(f"✅ Arquivo existente substituído no Google Drive: {uploaded.get('webViewLink', uploaded.get('id'))}")
        else:
            metadata = {"name": nome, "parents": [target_parent]}
            uploaded = service.files().create(
                body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True
            ).execute()
            print(f"✅ Upload para o Google Drive concluído: {uploaded.get('webViewLink', uploaded.get('id'))}")
        return uploaded
    except Exception as e:
        print(f"⚠️  Aviso: falha ao enviar '{local_path}' para o Google Drive: {e}")
        return None

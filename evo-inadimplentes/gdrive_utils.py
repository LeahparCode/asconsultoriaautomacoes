"""
Utilitário de upload para o Google Drive via Conta de Serviço (Service Account).

O upload é "best-effort": se a credencial não estiver configurada ou o upload
falhar por qualquer motivo, apenas um aviso é impresso e o script principal
continua rodando (o arquivo já está salvo localmente e também sobe como
artefato do GitHub Actions).
"""

import json
import os


def _get_service():
    creds_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print("Aviso: GDRIVE_SERVICE_ACCOUNT_JSON não configurado — pulando upload para o Drive.")
        return None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


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
    """Envia local_path para o Drive, dentro de parent_folder_id (opcionalmente em uma subpasta)."""
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

        metadata = {"name": filename or os.path.basename(local_path), "parents": [target_parent]}
        media = MediaFileUpload(local_path, resumable=True)
        uploaded = service.files().create(
            body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True
        ).execute()
        print(f"✅ Upload para o Google Drive concluído: {uploaded.get('webViewLink', uploaded.get('id'))}")
        return uploaded
    except Exception as e:
        print(f"⚠️  Aviso: falha ao enviar '{local_path}' para o Google Drive: {e}")
        return None

import io
import os
import time

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive']

# Escopo 'drive' completo (não 'drive.file') porque a pasta raiz é criada e
# compartilhada manualmente por um humano, não pelo service account -- com
# drive.file o app só enxergaria arquivos que ele mesmo criou.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_service = None


class DriveNotConfiguredError(Exception):
    """Levantado quando GOOGLE_DRIVE_ROOT_FOLDER_ID não foi definido."""


def _get_service():
    global _service
    if _service is not None:
        return _service
    creds_path = os.path.join(settings.BASE_DIR, 'credentials.json')
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado em {creds_path}. "
            "Coloque seu credentials.json na raiz do projeto Qluz_hub."
        )
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    _service = build('drive', 'v3', credentials=creds)
    return _service


def _execute_with_retry(request, max_retries=3, base_delay=1):
    attempt = 0
    while True:
        try:
            return request.execute()
        except HttpError as e:
            status = getattr(e.resp, 'status', None)
            attempt += 1
            if status not in _RETRYABLE_STATUS_CODES or attempt > max_retries:
                raise
            time.sleep(base_delay * (2 ** (attempt - 1)))


def _root_folder_id():
    folder_id = getattr(settings, 'GOOGLE_DRIVE_ROOT_FOLDER_ID', '')
    if not folder_id:
        raise DriveNotConfiguredError(
            'GOOGLE_DRIVE_ROOT_FOLDER_ID não configurado. Crie a pasta raiz no Drive, '
            'compartilhe com o email do service account (permissão Editor) e defina a variável de ambiente.'
        )
    return folder_id


def _escape_query_value(value):
    return value.replace('\\', '\\\\').replace("'", "\\'")


def get_or_create_client_folder(cliente_id, nome_cliente):
    """Retorna o id da pasta do cliente no Drive, criando dentro da pasta raiz
    se ainda não existir. Idempotente por nome -- protege contra criar pasta
    duplicada se duas requisições chegarem quase juntas antes do id ser salvo
    de volta na planilha."""
    service = _get_service()
    root_id = _root_folder_id()
    folder_name = f"{cliente_id} - {nome_cliente}".strip(' -')

    query = (
        f"'{root_id}' in parents and name = '{_escape_query_value(folder_name)}' "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    existing = _execute_with_retry(service.files().list(
        q=query, fields='files(id)', supportsAllDrives=True, includeItemsFromAllDrives=True,
    ))
    files = existing.get('files', [])
    if files:
        return files[0]['id']

    created = _execute_with_retry(service.files().create(
        body={
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [root_id],
        },
        fields='id',
        supportsAllDrives=True,
    ))
    return created['id']


def upload_file(folder_id, filename, content, mimetype):
    """Envia bytes pro Drive dentro de folder_id. Retorna {'id', 'webViewLink'}."""
    service = _get_service()
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mimetype, resumable=False)
    return _execute_with_retry(service.files().create(
        body={'name': filename, 'parents': [folder_id]},
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True,
    ))


def download_file(file_id):
    """Baixa os bytes do arquivo. Uso interno do proxy de download do app --
    nunca expor o link do Drive direto, pra manter a checagem de permissão
    do lado do QluzCert (ver comentário em views.download_documento)."""
    service = _get_service()
    return _execute_with_retry(service.files().get_media(fileId=file_id, supportsAllDrives=True))


def delete_file(file_id):
    """Remove um arquivo ou pasta (e todo o conteúdo dela) do Drive."""
    service = _get_service()
    _execute_with_retry(service.files().delete(fileId=file_id, supportsAllDrives=True))

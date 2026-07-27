import os
import time
import uuid
from datetime import datetime, timezone

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

_TAB_PREFIXES = {
    'Clientes': 'CLI',
    'Parceiros': 'PAR',
    'Precos': 'PRC',
}

_service = None
_cache = {}  # tab -> (rows, fetched_at_monotonic)


class ConcurrencyError(Exception):
    """Levantado quando a linha foi alterada por outra pessoa desde a última leitura."""


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
    _service = build('sheets', 'v4', credentials=creds)
    return _service


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _new_id(tab):
    prefix = _TAB_PREFIXES.get(tab, 'ROW')
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _col_letter(index):
    """Índice de coluna 0-based -> letra da planilha (0->A, 25->Z, 26->AA, ...)."""
    index += 1
    letters = ''
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _cache_ttl():
    return getattr(settings, 'GOOGLE_SHEETS_CACHE_TTL_SECONDS', 20)


def _invalidate(tab):
    _cache.pop(tab, None)


def _read_tab(tab):
    """Leitura sempre fresca (sem cache) da aba inteira. Retorna (header, rows)."""
    service = _get_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=settings.GOOGLE_SHEET_ID,
        range=tab,
    ).execute()
    values = result.get('values', [])
    if not values:
        return [], []
    header = values[0]
    rows = []
    for raw_row in values[1:]:
        padded = raw_row + [''] * (len(header) - len(raw_row))
        rows.append(dict(zip(header, padded)))
    return header, rows


def _find_row(tab, row_id):
    """Localiza a linha por id com leitura fresca. Retorna (header, num_linha_1based, row_dict)."""
    header, rows = _read_tab(tab)
    for offset, row in enumerate(rows):
        if row.get('id') == row_id:
            return header, offset + 2, row  # +1 cabeçalho, +1 índice 1-based
    return header, None, None


def list_rows(tab):
    cached = _cache.get(tab)
    if cached is not None:
        rows, fetched_at = cached
        if time.monotonic() - fetched_at < _cache_ttl():
            return rows
    _, rows = _read_tab(tab)
    _cache[tab] = (rows, time.monotonic())
    return rows


def get_row(tab, row_id):
    for row in list_rows(tab):
        if row.get('id') == row_id:
            return row
    return None


def create_row(tab, fields):
    header, _ = _read_tab(tab)
    if not header:
        raise ValueError(f"Aba '{tab}' não tem cabeçalho configurado na planilha.")

    row_id = _new_id(tab)
    full = {**fields, 'id': row_id, 'atualizado_em': _now_iso()}
    values = [full.get(col, '') for col in header]

    service = _get_service()
    service.spreadsheets().values().append(
        spreadsheetId=settings.GOOGLE_SHEET_ID,
        range=tab,
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': [values]},
    ).execute()
    _invalidate(tab)
    return full


def update_row(tab, row_id, fields, expected_atualizado_em=None):
    header, sheet_row, current = _find_row(tab, row_id)
    if sheet_row is None:
        raise LookupError(f"Registro '{row_id}' não encontrado na aba '{tab}'.")

    if expected_atualizado_em is not None and current.get('atualizado_em') != expected_atualizado_em:
        raise ConcurrencyError(
            f"Registro '{row_id}' foi alterado por outra pessoa desde a última leitura."
        )

    merged = {**current, **fields, 'id': row_id, 'atualizado_em': _now_iso()}
    values = [merged.get(col, '') for col in header]
    last_col = _col_letter(len(header) - 1)

    service = _get_service()
    service.spreadsheets().values().update(
        spreadsheetId=settings.GOOGLE_SHEET_ID,
        range=f"{tab}!A{sheet_row}:{last_col}{sheet_row}",
        valueInputOption='USER_ENTERED',
        body={'values': [values]},
    ).execute()
    _invalidate(tab)
    return merged


def _get_sheet_id_by_title(tab):
    service = _get_service()
    meta = service.spreadsheets().get(spreadsheetId=settings.GOOGLE_SHEET_ID).execute()
    for sheet in meta.get('sheets', []):
        props = sheet.get('properties', {})
        if props.get('title') == tab:
            return props.get('sheetId')
    raise LookupError(f"Aba '{tab}' não encontrada na planilha.")


def delete_row(tab, row_id):
    _, sheet_row, _ = _find_row(tab, row_id)
    if sheet_row is None:
        raise LookupError(f"Registro '{row_id}' não encontrado na aba '{tab}'.")

    sheet_id = _get_sheet_id_by_title(tab)
    service = _get_service()
    service.spreadsheets().batchUpdate(
        spreadsheetId=settings.GOOGLE_SHEET_ID,
        body={
            'requests': [{
                'deleteDimension': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': sheet_row - 1,
                        'endIndex': sheet_row,
                    }
                }
            }]
        },
    ).execute()
    _invalidate(tab)

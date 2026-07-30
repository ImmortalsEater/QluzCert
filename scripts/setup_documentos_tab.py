import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from core.app_Gestor import sheets_repository as repo

DOCUMENTOS_HEADER = [
    'id', 'cliente_ref', 'nome_cliente', 'nome_original', 'tipo_documento',
    'tamanho_bytes', 'observacao', 'drive_file_id', 'drive_view_url',
    'local_path', 'atualizado_em',
]

service = repo._get_service()
sheet_id = settings.GOOGLE_SHEET_ID

meta = repo._execute_with_retry(service.spreadsheets().get(spreadsheetId=sheet_id))
titles = [s['properties']['title'] for s in meta.get('sheets', [])]
print('Abas existentes:', titles)

if 'Documentos' not in titles:
    print('Criando aba Documentos...')
    repo._execute_with_retry(service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={'requests': [{'addSheet': {'properties': {'title': 'Documentos'}}}]},
    ))
    repo._execute_with_retry(service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='Documentos!A1',
        valueInputOption='RAW',
        body={'values': [DOCUMENTOS_HEADER]},
    ))
    print('Aba Documentos criada com cabecalho:', DOCUMENTOS_HEADER)
else:
    result = repo._execute_with_retry(service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range='Documentos!1:1',
    ))
    current_header = result.get('values', [[]])[0] if result.get('values') else []
    print('Cabecalho atual da aba Documentos:', current_header)
    missing = [c for c in DOCUMENTOS_HEADER if c not in current_header]
    if missing:
        new_header = current_header + missing
        repo._execute_with_retry(service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='Documentos!A1',
            valueInputOption='RAW',
            body={'values': [new_header]},
        ))
        print('Colunas adicionadas:', missing)
        print('Novo cabecalho:', new_header)
    else:
        print('Cabecalho ja tem todas as colunas necessarias, nada a fazer.')

# Clientes precisa de drive_folder_id pra cachear a pasta do Drive de cada cliente.
result = repo._execute_with_retry(service.spreadsheets().values().get(
    spreadsheetId=sheet_id, range='Clientes!1:1',
))
clientes_header = result.get('values', [[]])[0] if result.get('values') else []
print('Cabecalho atual da aba Clientes:', clientes_header)
if 'drive_folder_id' not in clientes_header:
    new_clientes_header = clientes_header + ['drive_folder_id']
    repo._execute_with_retry(service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='Clientes!A1',
        valueInputOption='RAW',
        body={'values': [new_clientes_header]},
    ))
    print('Coluna drive_folder_id adicionada a Clientes.')
else:
    print('Clientes ja tem drive_folder_id, nada a fazer.')

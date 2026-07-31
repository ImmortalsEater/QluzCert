import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from core.app_Gestor import sheets_repository as repo

service = repo._get_service()
sheet_id = settings.GOOGLE_SHEET_ID

result = repo._execute_with_retry(service.spreadsheets().values().get(
    spreadsheetId=sheet_id, range='Usuarios!1:1',
))
current_header = result.get('values', [[]])[0] if result.get('values') else []
print('Cabecalho atual da aba Usuarios:', current_header)

if 'perm_financeiro' not in current_header:
    new_header = current_header + ['perm_financeiro']
    repo._execute_with_retry(service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range='Usuarios!A1',
        valueInputOption='RAW',
        body={'values': [new_header]},
    ))
    print('Coluna perm_financeiro adicionada.')
    print('Novo cabecalho:', new_header)
else:
    print('Usuarios ja tem perm_financeiro, nada a fazer.')

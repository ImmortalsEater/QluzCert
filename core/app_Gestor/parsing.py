from datetime import datetime

import pandas as pd

# Chaves de permissão granular pra vendedor (coluna 'perm_<chave>' na aba
# Usuarios). Compartilhada entre auth_backends.py (monta a sessão no login)
# e views.py (decorator permission_required) pra não duplicar a lista.
PERM_KEYS = ['parceiros', 'precos', 'pagamentos', 'excluir_cliente', 'excluir_documento']


def parse_date(val):
    if val is None or val == '':
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.date()
    try:
        parsed = pd.to_datetime(val)
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def parse_decimal(val):
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        try:
            s = str(val).replace('R$', '').replace('.', '').replace(',', '.')
            return float(s)
        except Exception:
            return None


def bool_from(val):
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ['sim', 'true', '1', 'pago', 'yes', 'ok', 's']

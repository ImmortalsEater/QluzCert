import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password

from . import sheets_repository as repo
from .parsing import PERM_KEYS, bool_from

logger = logging.getLogger(__name__)


class SheetsBackend(BaseBackend):
    """Autentica contra a aba 'Usuarios' da planilha (mesma fonte de verdade
    de Clientes/Parceiros/Preços/Contatos) em vez da tabela local `auth_user`
    -- não há servidor com disco persistente, então login/senha não podem
    depender do SQLite local sobrevivendo entre execuções.

    Ainda usamos o model `auth.User` local como espelho descartável: só serve
    pra satisfazer o contrato que o Django exige de request.user/sessão. Ele
    é recriado a qualquer momento a partir da planilha (get_or_create) e sua
    senha local fica sempre inutilizável -- login real só acontece via
    authenticate() aqui, nunca por ModelBackend.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            rows = repo.list_rows('Usuarios')
        except Exception:
            logger.exception("Falha ao ler a aba 'Usuarios' da planilha durante login")
            return None
        row = next((r for r in rows if r.get('username') == username), None)
        if not row or not row.get('password'):
            return None
        if not check_password(password, row['password']):
            return None

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_unusable_password()

        # 'tipo' na planilha é a fonte de verdade do papel -- resincroniza
        # is_staff/is_superuser a cada login, não só na criação, pra uma
        # mudança de admin->vendedor (ou vice-versa) na planilha valer já no
        # próximo login, sem precisar mexer no espelho local manualmente.
        is_admin = (row.get('tipo') or '').strip().lower() == 'admin'
        if created or user.is_superuser != is_admin or user.is_staff != is_admin:
            user.is_superuser = is_admin
            user.is_staff = is_admin
            user.save()

        # Permissões granulares (colunas 'perm_<chave>') só valem pra
        # vendedor -- admin já tem acesso total via is_superuser, não
        # precisa marcar nada individualmente. Guardadas na sessão (cookie
        # assinado) em vez do User local, seguindo o mesmo raciocínio de
        # "sem disco persistente" já aplicado ao resto da autenticação.
        if request is not None:
            if is_admin:
                request.session['perms'] = {}
            else:
                request.session['perms'] = {
                    key: bool_from(row.get(f'perm_{key}')) for key in PERM_KEYS
                }

        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

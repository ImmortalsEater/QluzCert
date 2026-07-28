from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from core.app_Gestor import sheets_repository as repo


class Command(BaseCommand):
    help = (
        "Cria um usuario de login na aba 'Usuarios' da planilha (fonte de "
        "verdade das credenciais -- nao usa o banco local). Peca pra alguem "
        "criar a aba 'Usuarios' com as colunas 'username' e 'password' antes "
        "de rodar este comando pela primeira vez."
    )

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('password')
        parser.add_argument(
            '--admin', action='store_true',
            help="Cria como admin (tipo=admin) em vez de vendedor (padrao).",
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        tipo = 'admin' if options['admin'] else 'vendedor'

        existing = [r for r in repo.list_rows('Usuarios') if r.get('username') == username]
        if existing:
            raise CommandError(f"Usuario '{username}' ja existe na aba Usuarios.")

        repo.create_row('Usuarios', {'username': username, 'password': make_password(password), 'tipo': tipo})
        self.stdout.write(self.style.SUCCESS(f"Usuario '{username}' ({tipo}) criado na aba Usuarios."))

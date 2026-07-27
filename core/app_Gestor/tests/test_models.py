from django.test import TestCase

from core.app.models import Colaborador as ColaboradorApp
from core.app_Gestor.models import AppState, Colaborador as ColaboradorGestor, DocumentoCliente, PagamentoCliente


class ColaboradorStrTests(TestCase):
    """Os dois models Colaborador (core.app e core.app_Gestor) sao duplicados
    nao usados, preservados apenas para uma eventual migracao futura -- ambos
    tem a mesma implementacao de __str__, testada aqui uma vez para cada."""

    def test_app_colaborador_str_returns_nome(self):
        colaborador = ColaboradorApp(nome='Ana Silva', email='ana@example.com')
        self.assertEqual(str(colaborador), 'Ana Silva')

    def test_gestor_colaborador_str_returns_nome(self):
        colaborador = ColaboradorGestor(nome='Ana Silva', email='ana@example.com')
        self.assertEqual(str(colaborador), 'Ana Silva')


class AppStateStrTests(TestCase):

    def test_str_includes_key(self):
        state = AppState(key='main')
        self.assertEqual(str(state), 'AppState(main)')


class DocumentoClienteStrTests(TestCase):

    def test_str_prefers_nome_original(self):
        doc = DocumentoCliente(nome_original='contrato.pdf', nome_cliente='Ana', cliente_ref='CLI-1')
        self.assertEqual(str(doc), 'Documento(contrato.pdf)')

    def test_str_falls_back_to_cliente_ref_when_no_names(self):
        doc = DocumentoCliente(cliente_ref='CLI-1')
        self.assertEqual(str(doc), 'Documento(CLI-1)')


class PagamentoClienteStrTests(TestCase):

    def test_str_includes_gateway_id_and_status(self):
        pagamento = PagamentoCliente(
            gateway_payment_id='PAY-123', status=PagamentoCliente.STATUS_APPROVED,
            valor=10, descricao='Certificado',
        )
        self.assertEqual(str(pagamento), 'Pagamento(PAY-123, approved)')

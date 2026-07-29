import json
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from core.app_Gestor import sheets_repository as repo
from core.app_Gestor import views
from core.app_Gestor.models import AppState, DocumentoCliente, PagamentoCliente
from core.app_Gestor.parsing import PERM_KEYS

_MEDIA_ROOT = tempfile.mkdtemp(prefix='qcert_test_media_')

_TEST_USER_USERNAME = 'qcert-test-user'
_TEST_USER_PASSWORD = 'qcert-test-pass-123'


class TestCase(DjangoTestCase):
    """`TestCase` com login automático -- todas as views exigem login desde
    que o `LoginRequiredMiddleware` foi ligado; sem isso, todo teste que usa
    `self.client` cairia num redirect pra /login/ em vez de exercitar a view.

    O usuário é admin (is_superuser=True) por padrão: estes testes cobrem
    lógica de negócio, não a fronteira de permissão em si (ver
    PermissionRequiredTests para os testes de vendedor sendo bloqueado)."""

    def _pre_setup(self):
        super()._pre_setup()
        User = get_user_model()
        user = User.objects.create_user(
            username=_TEST_USER_USERNAME, password=_TEST_USER_PASSWORD,
            is_superuser=True, is_staff=True,
        )
        self.client.force_login(user)


CLIENTE_ROW = {
    'id': 'CLI-aaaaaaaa',
    'atualizado_em': '2024-01-01T00:00:00+00:00',
    'data_venda': '2024-01-01',
    'contador_parceiro': 'Escritorio A',
    'contador_contabilidade': '',
    'telefone1': '(11) 99999-0000',
    'cliente': 'Ana Silva',
    'status': 'Novo Lead',
    'cpf_cnpj': '111.222.333-44',
    'email': 'ana@example.com',
    'telefone2': '',
    'tipo_certificado': 'e-CPF A1',
    'valor_venda': '150.00',
    'percentual_comissao': '10',
    'valor_comissao': '15.00',
    'pago_comissao': 'Não',
    'chave_pix': '',
    'data_vencimento': '2024-06-01',
    'pago_venda': 'Sim',
    'forma_pagamento': 'Pix',
    'banco': '',
    'certificado_feito': '',
    'venda': '',
    'custo_certificado': '',
    'valor_liquido': '',
}


def _clientes_fixture(**overrides):
    return {**CLIENTE_ROW, **overrides}


class ListRowsPatchMixin:
    """Substitui sheets_repository.list_rows por um dict {tab: [rows]} controlado pelo teste."""

    def patch_list_rows(self, by_tab):
        def side_effect(tab):
            return by_tab.get(tab, [])
        patcher = patch.object(repo, 'list_rows', side_effect=side_effect)
        patcher.start()
        self.addCleanup(patcher.stop)


class FormatSheetCellValueTests(SimpleTestCase):

    def test_empty_value_renders_as_dash(self):
        self.assertEqual(views._format_sheet_cell_value('cliente', ''), '—')
        self.assertEqual(views._format_sheet_cell_value('cliente', None), '—')

    def test_date_field_formats_as_br_date(self):
        self.assertEqual(views._format_sheet_cell_value('data_venda', '2024-03-15'), '15/03/2024')

    def test_unparseable_date_falls_back_to_raw(self):
        self.assertEqual(views._format_sheet_cell_value('data_venda', 'não é data'), 'não é data')

    def test_decimal_field_formats_with_comma(self):
        self.assertEqual(views._format_sheet_cell_value('valor_venda', '1234.5'), '1234,50')

    def test_bool_field_renders_sim_nao(self):
        self.assertEqual(views._format_sheet_cell_value('pago_venda', 'Sim'), 'Sim')
        self.assertEqual(views._format_sheet_cell_value('pago_venda', ''), '—')
        self.assertEqual(views._format_sheet_cell_value('pago_venda', 'qualquer coisa'), 'Não')

    def test_unknown_field_passes_through(self):
        self.assertEqual(views._format_sheet_cell_value('cliente', 'Ana Silva'), 'Ana Silva')

    def test_status_field_passes_through(self):
        self.assertEqual(views._format_sheet_cell_value('status', 'Emitido'), 'Emitido')


class BuildDashboardFromSheetsTests(ListRowsPatchMixin, SimpleTestCase):

    def test_builds_one_row_per_sheet_row_with_formatted_cells(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture()]})

        cols, rows = views._build_dashboard_from_sheets()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'CLI-aaaaaaaa')
        self.assertEqual(len(rows[0]['cells']), len(cols))
        cliente_cell = rows[0]['cells'][cols.index(next(c for c in cols if c['field'] == 'cliente'))]
        self.assertEqual(cliente_cell['value'], 'Ana Silva')
        status_cell = rows[0]['cells'][cols.index(next(c for c in cols if c['field'] == 'status'))]
        self.assertEqual(status_cell['value'], 'Novo Lead')

    def test_row_without_id_is_skipped(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture(id='')]})

        _, rows = views._build_dashboard_from_sheets()

        self.assertEqual(rows, [])

    def test_empty_sheet_returns_no_rows(self):
        self.patch_list_rows({'Clientes': []})

        _, rows = views._build_dashboard_from_sheets()

        self.assertEqual(rows, [])


class BuildClientesLeadsFromSheetsTests(ListRowsPatchMixin, SimpleTestCase):

    def test_maps_sheet_row_to_lead_dict(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture()]})

        leads = views._build_clientes_leads_from_sheets()

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]['id'], 'CLI-aaaaaaaa')
        self.assertEqual(leads[0]['nome'], 'Ana Silva')
        self.assertEqual(leads[0]['status'], 'Novo Lead')
        self.assertEqual(leads[0]['dataVencimento'], '2024-06-01')

    def test_status_falls_back_to_novo_lead_when_blank(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture(status='')]})

        leads = views._build_clientes_leads_from_sheets()

        self.assertEqual(leads[0]['status'], 'Novo Lead')

    def test_row_without_id_is_skipped(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture(id='')]})

        leads = views._build_clientes_leads_from_sheets()

        self.assertEqual(leads, [])


class BuildAlertPayloadTests(ListRowsPatchMixin, SimpleTestCase):

    def test_row_without_vencimento_is_ignored(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento='')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['alertas_totais'], 0)

    def test_counts_total_and_emitidos_reflect_the_sheet(self):
        # "Emitidos" reflete o status do funil (o que o Kanban realmente
        # atualiza), não o campo certificado_feito -- ver _build_alert_payload.
        self.patch_list_rows({'Clientes': [
            _clientes_fixture(id='CLI-1', status='Emitido'),
            _clientes_fixture(id='CLI-2', status='Aguardando Pagamento'),
            _clientes_fixture(id='CLI-3', status='Novo Lead'),
        ]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['total_registros'], 3)
        self.assertEqual(payload['counts']['emitidos'], 1)

    def test_vencendo_60_dias_counts_rows_within_threshold_regardless_of_pagamento(self):
        dentro_do_prazo = (date.today() + timedelta(days=60)).isoformat()
        fora_do_prazo = (date.today() + timedelta(days=61)).isoformat()
        vencido = (date.today() - timedelta(days=5)).isoformat()
        self.patch_list_rows({'Clientes': [
            _clientes_fixture(id='CLI-1', data_vencimento=dentro_do_prazo, pago_venda='Sim', pago_comissao='Sim'),
            _clientes_fixture(id='CLI-2', data_vencimento=fora_do_prazo, pago_venda='Sim', pago_comissao='Sim'),
            _clientes_fixture(id='CLI-3', data_vencimento=vencido, pago_venda='Sim', pago_comissao='Sim'),
        ]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['vencendo_60_dias'], 2)

    def test_vencimento_within_30_days_is_urgent_renovacao(self):
        vencimento = (date.today() + timedelta(days=10)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Sim', pago_comissao='Sim')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['renovacoes_urgentes'], 1)
        self.assertEqual(payload['counts']['renovacoes_normais'], 0)
        self.assertEqual(payload['renovacoes']['urgentes'][0]['nome'], 'Ana Silva')

    def test_vencimento_between_31_and_90_days_is_normal_renovacao(self):
        vencimento = (date.today() + timedelta(days=60)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Sim', pago_comissao='Sim')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['renovacoes_normais'], 1)
        self.assertEqual(payload['counts']['renovacoes_urgentes'], 0)

    def test_unpaid_venda_overdue_is_urgent_pagamento(self):
        vencimento = (date.today() - timedelta(days=5)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Não', pago_comissao='Sim')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['pagamentos_urgentes'], 1)
        self.assertEqual(payload['pagamentos']['urgentes'][0]['tipoPagamento'], 'Venda')

    def test_unpaid_venda_due_soon_is_normal_pagamento(self):
        vencimento = (date.today() + timedelta(days=15)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Não', pago_comissao='Sim')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['pagamentos_normais'], 1)
        self.assertEqual(payload['counts']['pagamentos_urgentes'], 0)
        self.assertEqual(payload['pagamentos']['normais'][0]['tipoPagamento'], 'Venda')

    def test_unpaid_comissao_due_soon_is_normal_pagamento(self):
        vencimento = (date.today() + timedelta(days=15)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Sim', pago_comissao='Não')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['pagamentos_normais'], 1)
        self.assertEqual(payload['pagamentos']['normais'][0]['tipoPagamento'], 'Comissão')

    def test_paid_venda_and_comissao_generate_no_pagamento_alert(self):
        vencimento = (date.today() + timedelta(days=5)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Sim', pago_comissao='Sim')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['pagamentos_urgentes'], 0)
        self.assertEqual(payload['counts']['pagamentos_normais'], 0)


class BuildParceirosFromSourceTests(ListRowsPatchMixin, SimpleTestCase):

    def test_maps_sheet_rows_to_parceiro_dicts(self):
        self.patch_list_rows({'Parceiros': [{
            'id': 'PAR-aaaaaaaa', 'atualizado_em': '', 'nome': 'Escritorio A', 'tipo': 'Contador',
            'telefone': '(11) 90000-0000', 'email': 'a@x.com', 'comissao': '10,5', 'contato': 'Fulano',
        }]})

        parceiros = views._build_parceiros_from_source()

        self.assertEqual(parceiros, [{
            'id': 'PAR-aaaaaaaa', 'nome': 'Escritorio A', 'tipo': 'Contador',
            'telefone': '(11) 90000-0000', 'email': 'a@x.com', 'comissao': 10.5, 'contato': 'Fulano',
            'atualizadoEm': '',
        }])


class BuildPrecosFromSourceTests(ListRowsPatchMixin, SimpleTestCase):

    def test_maps_sheet_rows_to_preco_dicts(self):
        self.patch_list_rows({'Precos': [{
            'id': 'PRC-aaaaaaaa', 'atualizado_em': '', 'tipo': 'e-CPF A1', 'validade': '1 ano', 'preco': '150',
        }]})

        precos = views._build_precos_from_source()

        self.assertEqual(precos, [{'id': 'PRC-aaaaaaaa', 'tipo': 'e-CPF A1', 'validade': '1 ano', 'preco': 150.0, 'atualizadoEm': ''}])


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class SafeJsonDumpsTests(SimpleTestCase):

    def test_escapes_angle_brackets_and_ampersand(self):
        result = views._safe_json_dumps({'nome': '</script><script>alert(1)</script>&'})

        self.assertNotIn('<', result)
        self.assertNotIn('>', result)
        self.assertNotIn('&', result)
        self.assertEqual(json.loads(result), {'nome': '</script><script>alert(1)</script>&'})

    def test_still_valid_json_for_plain_values(self):
        result = views._safe_json_dumps({'a': 1, 'b': 'texto normal'})

        self.assertEqual(json.loads(result), {'a': 1, 'b': 'texto normal'})


class DashboardViewTests(ListRowsPatchMixin, TestCase):

    def test_renders_ok_with_data_from_sheets(self):
        self.patch_list_rows({
            'Clientes': [_clientes_fixture()],
            'Parceiros': [],
            'Precos': [],
        })

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['google_rows']), 1)

    def test_malicious_client_name_cannot_break_out_of_script_tag(self):
        payload = '</script><script>window.__xss=1</script>'
        self.patch_list_rows({
            'Clientes': [_clientes_fixture(cliente=payload)],
            'Parceiros': [],
            'Precos': [],
        })

        response = self.client.get(reverse('dashboard'))

        content = response.content.decode('utf-8')
        self.assertNotIn('</script><script>window.__xss', content)
        self.assertIn('\\u003c/script\\u003e', content)

    def test_degrades_gracefully_when_sheets_repository_fails(self):
        patcher = patch.object(repo, 'list_rows', side_effect=Exception('planilha indisponivel'))
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['google_rows'], [])


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class AlertasDashboardViewTests(ListRowsPatchMixin, TestCase):

    def test_returns_alert_payload_as_json(self):
        vencimento = (date.today() + timedelta(days=5)).isoformat()
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento=vencimento, pago_venda='Sim', pago_comissao='Sim')]})

        response = self.client.get(reverse('alertas_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['counts']['renovacoes_urgentes'], 1)


class AtualizarPlanilhaViewTests(TestCase):

    def setUp(self):
        self.addCleanup(repo._cache.clear)

    def test_requires_post(self):
        response = self.client.get(reverse('atualizar_planilha'))
        self.assertEqual(response.status_code, 405)

    def test_post_invalidates_cache_for_all_tabs(self):
        repo._cache['Clientes'] = ([{'id': 'CLI-1'}], 0)
        repo._cache['Parceiros'] = ([{'id': 'PAR-1'}], 0)

        response = self.client.post(reverse('atualizar_planilha'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True})
        self.assertEqual(repo._cache, {})


class AtualizarStatusClienteTests(TestCase):

    def test_requires_post(self):
        response = self.client.get(reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}))
        self.assertEqual(response.status_code, 405)

    def test_post_without_status_returns_400(self):
        response = self.client.post(reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), {})
        self.assertEqual(response.status_code, 400)

    def test_post_success_updates_row(self):
        with patch.object(repo, 'update_row', return_value=_clientes_fixture(status='Emitido', atualizado_em='2024-02-01T00:00:00+00:00')) as mock_update:
            response = self.client.post(
                reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'status': 'Emitido', 'expected_atualizado_em': '2024-01-01T00:00:00+00:00'},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['atualizado_em'], '2024-02-01T00:00:00+00:00')
        mock_update.assert_called_once_with(
            'Clientes', 'CLI-aaaaaaaa', {'status': 'Emitido'},
            expected_atualizado_em='2024-01-01T00:00:00+00:00',
        )

    def test_post_not_found_returns_404(self):
        with patch.object(repo, 'update_row', side_effect=LookupError('sumiu')):
            response = self.client.post(
                reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-nope'}),
                {'status': 'Emitido'},
            )

        self.assertEqual(response.status_code, 404)

    def test_post_concurrency_conflict_returns_409(self):
        with patch.object(repo, 'update_row', side_effect=repo.ConcurrencyError('conflito')):
            response = self.client.post(
                reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'status': 'Emitido'},
            )

        self.assertEqual(response.status_code, 409)

    def test_post_generic_failure_returns_500(self):
        with patch.object(repo, 'update_row', side_effect=Exception('planilha fora do ar')):
            response = self.client.post(
                reverse('atualizar_status_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'status': 'Emitido'},
            )

        self.assertEqual(response.status_code, 500)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class EditarGoogleRowViewTests(TestCase):

    def test_get_404_when_row_missing(self):
        with patch.object(repo, 'get_row', return_value=None):
            response = self.client.get(reverse('editar_google_row', kwargs={'pk': 'CLI-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_get_renders_form_with_bool_pago_comissao(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture(pago_comissao='Sim')):
            response = self.client.get(reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context['registro']['pago_comissao'], True)

    def test_post_updates_row_and_redirects(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva Atualizada', 'email': 'nova@example.com', 'pago_comissao': 'Sim'},
            )

        self.assertRedirects(response, reverse('dashboard') + '#clientes', fetch_redirect_response=False)
        mock_update.assert_called_once()
        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(tab, 'Clientes')
        self.assertEqual(pk, 'CLI-aaaaaaaa')
        self.assertEqual(fields['cliente'], 'Ana Silva Atualizada')
        self.assertEqual(fields['pago_comissao'], 'Sim')

    def test_post_status_is_sent_when_provided(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'status': 'Emitido', 'pago_comissao': 'Não'},
            )

        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(fields['status'], 'Emitido')

    def test_post_without_status_sends_empty_string(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'pago_comissao': 'Não'},
            )

        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(fields['status'], '')

    def test_post_without_cliente_shows_error_and_does_not_update(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': '', 'pago_comissao': 'Não'},
                follow=True,
            )

        mock_update.assert_not_called()
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('nome do cliente' in m for m in messages))

    def test_post_sends_full_field_set_including_new_fields(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {
                    'cliente': 'Ana Silva', 'cpf_cnpj': '111.222.333-44', 'telefone1': '(11) 90000-0000',
                    'tipo_certificado': 'e-CPF A1', 'custo_certificado': '50.00', 'valor_liquido': '100.00',
                    'certificado_feito': 'Sim', 'pago_venda': 'Sim', 'pago_comissao': 'Não',
                },
            )

        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(fields['cpf_cnpj'], '111.222.333-44')
        self.assertEqual(fields['custo_certificado'], '50.00')
        self.assertEqual(fields['certificado_feito'], 'Sim')
        self.assertEqual(fields['pago_venda'], 'Sim')

    def test_post_generic_failure_shows_error_message(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row', side_effect=Exception('planilha fora do ar')), \
             patch.object(repo, 'list_rows', return_value=[]):
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'pago_comissao': 'Sim'},
                follow=True,
            )

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Falha ao salvar' in m for m in messages))

    def test_post_stale_expected_atualizado_em_shows_concurrency_message(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row', side_effect=repo.ConcurrencyError('conflito')), \
             patch.object(repo, 'list_rows', return_value=[]):
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'pago_comissao': 'Sim', 'expected_atualizado_em': 'stale'},
                follow=True,
            )

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('alterado por outra pessoa' in m for m in messages))

    def test_post_row_deleted_meanwhile_raises_404(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row', side_effect=LookupError('sumiu')):
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'pago_comissao': 'Sim'},
            )

        self.assertEqual(response.status_code, 404)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class CriarGoogleRowViewTests(TestCase):

    def test_get_renders_empty_form(self):
        response = self.client.get(reverse('criar_google_row'))
        self.assertEqual(response.status_code, 200)

    def test_post_without_nome_is_rejected(self):
        response = self.client.post(reverse('criar_google_row'), {})
        self.assertEqual(response.status_code, 200)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('nome do cliente' in m for m in messages))

    def test_post_without_nome_ajax_returns_400(self):
        response = self.client.post(
            reverse('criar_google_row'), {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)

    def test_post_success_creates_row_and_redirects(self):
        with patch.object(repo, 'create_row') as mock_create:
            response = self.client.post(reverse('criar_google_row'), {
                'cliente': 'Novo Cliente', 'email': 'novo@example.com',
            })

        self.assertRedirects(response, reverse('dashboard') + '#clientes', fetch_redirect_response=False)
        mock_create.assert_called_once()
        tab, fields = mock_create.call_args.args
        self.assertEqual(tab, 'Clientes')
        self.assertEqual(fields['cliente'], 'Novo Cliente')
        self.assertEqual(fields['email'], 'novo@example.com')
        self.assertEqual(fields['status'], 'Novo Lead')

    def test_post_status_default_is_overridden_when_provided(self):
        with patch.object(repo, 'create_row') as mock_create:
            self.client.post(reverse('criar_google_row'), {
                'cliente': 'Novo Cliente', 'status': 'Emitido',
            })

        tab, fields = mock_create.call_args.args
        self.assertEqual(fields['status'], 'Emitido')

    def test_post_success_ajax_returns_json(self):
        with patch.object(repo, 'create_row'):
            response = self.client.post(
                reverse('criar_google_row'), {'cliente': 'Novo Cliente'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)

    def test_post_failure_ajax_returns_success_false(self):
        with patch.object(repo, 'create_row', side_effect=Exception('sem credenciais')):
            response = self.client.post(
                reverse('criar_google_row'), {'cliente': 'Novo Cliente'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        data = response.json()
        self.assertEqual(data['success'], False)
        self.assertIn('sem credenciais', data['drive_error'])

    def test_post_failure_non_ajax_shows_error_message(self):
        with patch.object(repo, 'create_row', side_effect=Exception('sem credenciais')), \
             patch.object(repo, 'list_rows', return_value=[]):
            response = self.client.post(
                reverse('criar_google_row'), {'cliente': 'Novo Cliente'}, follow=True,
            )

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('sem credenciais' in m for m in messages))


class ClienteExcluirViewTests(TestCase):

    def test_requires_post(self):
        response = self.client.get(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))
        self.assertEqual(response.status_code, 405)

    def test_success(self):
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once_with('Clientes', 'CLI-aaaaaaaa')

    def test_not_found_returns_404(self):
        with patch.object(repo, 'delete_row', side_effect=LookupError('nao existe')):
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_failure_returns_500(self):
        with patch.object(repo, 'delete_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 500)

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_success_also_deletes_associated_documentos_and_pagamentos(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', arquivo=arquivo, nome_original='doc.pdf', tamanho_bytes=8)
        PagamentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', nome_cliente='Ana Silva', email_cliente='ana@example.com',
            valor=100, descricao='Certificado',
        )
        outro_doc = DocumentoCliente.objects.create(cliente_ref='CLI-outrocliente', nome_original='outro.pdf', tamanho_bytes=1)

        with patch.object(repo, 'delete_row'):
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(DocumentoCliente.objects.filter(pk=doc.pk).exists())
        self.assertEqual(PagamentoCliente.objects.filter(cliente_ref='CLI-aaaaaaaa').count(), 0)
        self.assertTrue(DocumentoCliente.objects.filter(pk=outro_doc.pk).exists())

    def test_cleanup_failure_does_not_fail_the_request(self):
        with patch.object(repo, 'delete_row'), \
             patch.object(DocumentoCliente.objects, 'filter', side_effect=Exception('erro de banco')):
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)


class ContatosClienteRegistroTests(TestCase):

    def test_get_404_when_cliente_missing(self):
        with patch.object(repo, 'get_row', return_value=None):
            response = self.client.get(reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_get_lists_only_contatos_for_this_cliente(self):
        contatos = [
            {'id': 'CTT-1', 'cliente_id': 'CLI-aaaaaaaa', 'tipo': 'contato', 'atualizado_em': '2024-01-02'},
            {'id': 'CTT-2', 'cliente_id': 'CLI-outro', 'tipo': 'contato', 'atualizado_em': '2024-01-03'},
        ]
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'list_rows', return_value=contatos):
            response = self.client.get(reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([c['id'] for c in data['contatos']], ['CTT-1'])

    def test_post_creates_contato_row(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'create_row', return_value={'id': 'CTT-novo'}) as mock_create:
            response = self.client.post(
                reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'tipo': 'contato', 'canal': 'WhatsApp', 'texto': 'Cliente confirmou interesse'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'id': 'CTT-novo'})
        tab, fields = mock_create.call_args.args
        self.assertEqual(tab, 'Contatos')
        self.assertEqual(fields['cliente_id'], 'CLI-aaaaaaaa')
        self.assertEqual(fields['canal'], 'WhatsApp')

    def test_post_notificacao_does_not_touch_status_without_novo_status_funil(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'create_row', return_value={'id': 'CTT-novo'}), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'tipo': 'notificacao', 'titulo': 'Pagamento registrado', 'texto': 'Pagamento confirmado'},
            )

        mock_update.assert_not_called()

    def test_post_with_novo_status_funil_updates_cliente_status(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'create_row', return_value={'id': 'CTT-novo'}), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'tipo': 'contato', 'canal': 'Ligação', 'novo_status_funil': 'Emitido'},
            )

        mock_update.assert_called_once_with('Clientes', 'CLI-aaaaaaaa', {'status': 'Emitido'})

    def test_post_404_when_cliente_missing(self):
        with patch.object(repo, 'get_row', return_value=None):
            response = self.client.post(reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-nope'}), {})

        self.assertEqual(response.status_code, 404)

    def test_put_method_not_allowed(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.put(reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 400)

    def test_post_create_row_failure_returns_500(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'create_row', side_effect=Exception('planilha fora do ar')):
            response = self.client.post(
                reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'tipo': 'contato', 'texto': 'teste'},
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn('planilha fora do ar', response.json()['error'])

    def test_post_still_succeeds_when_status_update_fails(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'create_row', return_value={'id': 'CTT-novo'}), \
             patch.object(repo, 'update_row', side_effect=Exception('falhou')):
            response = self.client.post(
                reverse('contatos_cliente_registro', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'tipo': 'contato', 'novo_status_funil': 'Emitido'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'id': 'CTT-novo'})


class BuildNotificacoesRecentesTests(ListRowsPatchMixin, SimpleTestCase):

    def test_only_includes_tipo_notificacao_sorted_by_atualizado_em(self):
        self.patch_list_rows({
            'Clientes': [_clientes_fixture(id='CLI-aaaaaaaa', cliente='Ana Silva')],
            'Contatos': [
                {'id': 'CTT-1', 'cliente_id': 'CLI-aaaaaaaa', 'tipo': 'contato', 'atualizado_em': '2024-01-05'},
                {'id': 'CTT-2', 'cliente_id': 'CLI-aaaaaaaa', 'tipo': 'notificacao', 'titulo': 'Pagamento registrado', 'texto': 'Confirmado', 'data': '2024-01-01', 'atualizado_em': '2024-01-01'},
                {'id': 'CTT-3', 'cliente_id': 'CLI-aaaaaaaa', 'tipo': 'notificacao', 'titulo': 'Lembrete', 'texto': 'Renovação próxima', 'data': '2024-01-04', 'atualizado_em': '2024-01-04'},
            ],
        })

        result = views._build_notificacoes_recentes()

        self.assertEqual([r['id'] for r in result], ['CTT-3', 'CTT-2'])
        self.assertEqual(result[0]['nome'], 'Ana Silva')

    def test_limit_caps_number_of_results(self):
        self.patch_list_rows({
            'Clientes': [_clientes_fixture()],
            'Contatos': [
                {'id': f'CTT-{i}', 'cliente_id': 'CLI-aaaaaaaa', 'tipo': 'notificacao', 'atualizado_em': f'2024-01-{i:02d}'}
                for i in range(1, 10)
            ],
        })

        result = views._build_notificacoes_recentes(limit=3)

        self.assertEqual(len(result), 3)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class ParceiroViewsTests(TestCase):

    def test_criar_requires_post(self):
        response = self.client.get(reverse('parceiro_criar'))
        self.assertEqual(response.status_code, 400)

    def test_criar_without_nome_returns_400(self):
        response = self.client.post(reverse('parceiro_criar'), {})
        self.assertEqual(response.status_code, 400)

    def test_criar_success(self):
        with patch.object(repo, 'create_row', return_value={'id': 'PAR-xxxxxxxx'}) as mock_create:
            response = self.client.post(reverse('parceiro_criar'), {
                'nome': 'Escritorio B', 'tipo': 'Contador', 'comissao': '12',
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'id': 'PAR-xxxxxxxx'})
        tab, fields = mock_create.call_args.args
        self.assertEqual(tab, 'Parceiros')
        self.assertEqual(fields['nome'], 'Escritorio B')

    def test_criar_failure_returns_500(self):
        with patch.object(repo, 'create_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('parceiro_criar'), {'nome': 'Escritorio B'})

        self.assertEqual(response.status_code, 500)

    def test_editar_sends_only_provided_fields(self):
        with patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('parceiro_editar', kwargs={'id': 'PAR-aaaaaaaa'}),
                {'telefone': '(11) 98888-0000'},
            )

        self.assertEqual(response.status_code, 200)
        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(tab, 'Parceiros')
        self.assertEqual(pk, 'PAR-aaaaaaaa')
        self.assertEqual(fields, {'telefone': '(11) 98888-0000'})

    def test_editar_not_found_returns_404(self):
        with patch.object(repo, 'update_row', side_effect=LookupError('nao existe')):
            response = self.client.post(reverse('parceiro_editar', kwargs={'id': 'PAR-nope'}), {'nome': 'X'})

        self.assertEqual(response.status_code, 404)

    def test_editar_requires_post(self):
        response = self.client.get(reverse('parceiro_editar', kwargs={'id': 'PAR-aaaaaaaa'}))
        self.assertEqual(response.status_code, 400)

    def test_editar_failure_returns_500(self):
        with patch.object(repo, 'update_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('parceiro_editar', kwargs={'id': 'PAR-aaaaaaaa'}), {'nome': 'X'})

        self.assertEqual(response.status_code, 500)

    def test_editar_forwards_expected_atualizado_em(self):
        with patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('parceiro_editar', kwargs={'id': 'PAR-aaaaaaaa'}),
                {'nome': 'X', 'expected_atualizado_em': '2024-01-01T00:00:00+00:00'},
            )

        mock_update.assert_called_once_with('Parceiros', 'PAR-aaaaaaaa', {'nome': 'X'}, expected_atualizado_em='2024-01-01T00:00:00+00:00')

    def test_editar_concurrency_conflict_returns_409(self):
        with patch.object(repo, 'update_row', side_effect=repo.ConcurrencyError('conflito')):
            response = self.client.post(reverse('parceiro_editar', kwargs={'id': 'PAR-aaaaaaaa'}), {'nome': 'X'})

        self.assertEqual(response.status_code, 409)

    def test_excluir_requires_post(self):
        response = self.client.get(reverse('parceiro_excluir', kwargs={'id': 'PAR-aaaaaaaa'}))
        self.assertEqual(response.status_code, 405)

    def test_excluir_success(self):
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('parceiro_excluir', kwargs={'id': 'PAR-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once_with('Parceiros', 'PAR-aaaaaaaa')

    def test_excluir_not_found_returns_404(self):
        with patch.object(repo, 'delete_row', side_effect=LookupError('nao existe')):
            response = self.client.post(reverse('parceiro_excluir', kwargs={'id': 'PAR-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_excluir_failure_returns_500(self):
        with patch.object(repo, 'delete_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('parceiro_excluir', kwargs={'id': 'PAR-aaaaaaaa'}))

        self.assertEqual(response.status_code, 500)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class PrecoViewsTests(TestCase):

    def test_criar_requires_post(self):
        response = self.client.get(reverse('preco_criar'))
        self.assertEqual(response.status_code, 400)

    def test_criar_without_tipo_returns_400(self):
        response = self.client.post(reverse('preco_criar'), {})
        self.assertEqual(response.status_code, 400)

    def test_criar_failure_returns_500(self):
        with patch.object(repo, 'create_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('preco_criar'), {'tipo': 'e-CPF A1'})

        self.assertEqual(response.status_code, 500)

    def test_criar_success(self):
        with patch.object(repo, 'create_row', return_value={'id': 'PRC-xxxxxxxx'}) as mock_create:
            response = self.client.post(reverse('preco_criar'), {
                'tipo': 'e-CPF A1', 'validade': '1 ano', 'preco': '150',
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True, 'id': 'PRC-xxxxxxxx'})
        tab, fields = mock_create.call_args.args
        self.assertEqual(tab, 'Precos')
        self.assertEqual(fields['tipo'], 'e-CPF A1')

    def test_editar_success(self):
        with patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('preco_editar', kwargs={'id': 'PRC-aaaaaaaa'}), {'preco': '199'},
            )

        self.assertEqual(response.status_code, 200)
        tab, pk, fields = mock_update.call_args.args
        self.assertEqual(tab, 'Precos')
        self.assertEqual(fields, {'preco': '199'})

    def test_editar_requires_post(self):
        response = self.client.get(reverse('preco_editar', kwargs={'id': 'PRC-aaaaaaaa'}))
        self.assertEqual(response.status_code, 400)

    def test_editar_not_found_returns_404(self):
        with patch.object(repo, 'update_row', side_effect=LookupError('nao existe')):
            response = self.client.post(reverse('preco_editar', kwargs={'id': 'PRC-nope'}), {'preco': '1'})

        self.assertEqual(response.status_code, 404)

    def test_editar_failure_returns_500(self):
        with patch.object(repo, 'update_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('preco_editar', kwargs={'id': 'PRC-aaaaaaaa'}), {'preco': '1'})

        self.assertEqual(response.status_code, 500)

    def test_editar_forwards_expected_atualizado_em(self):
        with patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('preco_editar', kwargs={'id': 'PRC-aaaaaaaa'}),
                {'preco': '199', 'expected_atualizado_em': '2024-01-01T00:00:00+00:00'},
            )

        mock_update.assert_called_once_with('Precos', 'PRC-aaaaaaaa', {'preco': '199'}, expected_atualizado_em='2024-01-01T00:00:00+00:00')

    def test_editar_concurrency_conflict_returns_409(self):
        with patch.object(repo, 'update_row', side_effect=repo.ConcurrencyError('conflito')):
            response = self.client.post(reverse('preco_editar', kwargs={'id': 'PRC-aaaaaaaa'}), {'preco': '1'})

        self.assertEqual(response.status_code, 409)

    def test_excluir_requires_post(self):
        response = self.client.get(reverse('preco_excluir', kwargs={'id': 'PRC-aaaaaaaa'}))
        self.assertEqual(response.status_code, 405)

    def test_excluir_success(self):
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('preco_excluir', kwargs={'id': 'PRC-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once_with('Precos', 'PRC-aaaaaaaa')

    def test_excluir_not_found_returns_404(self):
        with patch.object(repo, 'delete_row', side_effect=LookupError('nao existe')):
            response = self.client.post(reverse('preco_excluir', kwargs={'id': 'PRC-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_excluir_failure_returns_500(self):
        with patch.object(repo, 'delete_row', side_effect=Exception('falhou')):
            response = self.client.post(reverse('preco_excluir', kwargs={'id': 'PRC-aaaaaaaa'}))

        self.assertEqual(response.status_code, 500)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class DocumentosClienteViewTests(TestCase):

    def test_404_when_cliente_not_found(self):
        with patch.object(repo, 'get_row', return_value=None):
            response = self.client.get(reverse('documentos_cliente', kwargs={'pk': 'CLI-nope'}))

        self.assertEqual(response.status_code, 404)

    def test_get_html_renders_registro_and_documentos(self):
        DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=10)

        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.get(reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['documentos']), 1)

    def test_get_json_lists_documentos_by_cliente_ref_only(self):
        DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='meu.pdf', tamanho_bytes=10)
        DocumentoCliente.objects.create(cliente_ref='CLI-outro', nome_original='naomeu.pdf', tamanho_bytes=10)

        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.get(
                reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), {'format': 'json'},
            )

        data = response.json()
        self.assertEqual(data['registro']['id'], 'CLI-aaaaaaaa')
        self.assertEqual(len(data['documentos']), 1)
        self.assertEqual(data['documentos'][0]['nome_original'], 'meu.pdf')

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_post_valid_file_creates_documento_with_cliente_ref(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')

        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.post(
                reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'arquivo': arquivo, 'tipo_documento': 'rg_cnh'},
            )

        self.assertRedirects(
            response, reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), fetch_redirect_response=False,
        )
        doc = DocumentoCliente.objects.get()
        self.assertEqual(doc.cliente_ref, 'CLI-aaaaaaaa')
        self.assertIsNone(doc.registro_id)
        self.assertEqual(doc.nome_cliente, 'Ana Silva')
        doc.arquivo.delete(save=False)

    def test_post_without_arquivo_shows_error(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.post(
                reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), {}, follow=True,
            )

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Selecione um arquivo' in m for m in messages))

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_post_disallowed_extension_is_rejected(self):
        arquivo = SimpleUploadedFile('doc.exe', b'conteudo', content_type='application/octet-stream')

        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.post(
                reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'arquivo': arquivo}, follow=True,
            )

        self.assertEqual(DocumentoCliente.objects.count(), 0)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('não permitido' in m for m in messages))

    @override_settings(UPLOAD_DOCUMENTO_TAMANHO_MAXIMO_MB=0)
    def test_post_oversized_file_is_rejected(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')

        with patch.object(repo, 'get_row', return_value=_clientes_fixture()):
            response = self.client.post(
                reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'arquivo': arquivo}, follow=True,
            )

        self.assertEqual(DocumentoCliente.objects.count(), 0)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('muito grande' in m for m in messages))


class UploadDocumentoViewTests(TestCase):

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_get_renders_recent_documentos(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
        DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', arquivo=arquivo, nome_original='doc.pdf', tamanho_bytes=1)

        response = self.client.get(reverse('upload_documento'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['documentos']), 1)

    def test_post_without_arquivo_redirects_with_error(self):
        response = self.client.post(reverse('upload_documento'), {}, follow=True)

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Selecione um arquivo' in m for m in messages))

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_post_success_creates_documento(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')

        response = self.client.post(reverse('upload_documento'), {
            'arquivo': arquivo, 'cliente_ref': 'CLI-aaaaaaaa', 'nome_cliente': 'Ana Silva', 'observacao': 'via balcao',
        })

        self.assertRedirects(response, reverse('upload_documento'), fetch_redirect_response=False)
        doc = DocumentoCliente.objects.get()
        self.assertEqual(doc.cliente_ref, 'CLI-aaaaaaaa')
        self.assertEqual(doc.nome_cliente, 'Ana Silva')
        self.assertEqual(doc.observacao, 'via balcao')

    def test_post_rejects_disallowed_extension(self):
        arquivo = SimpleUploadedFile('malware.exe', b'conteudo', content_type='application/octet-stream')

        response = self.client.post(reverse('upload_documento'), {'arquivo': arquivo}, follow=True)

        self.assertEqual(DocumentoCliente.objects.count(), 0)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('não permitido' in m for m in messages))

    def test_post_rejects_file_over_size_limit(self):
        conteudo_grande = b'x' * (11 * 1024 * 1024)
        arquivo = SimpleUploadedFile('doc.pdf', conteudo_grande, content_type='application/pdf')

        response = self.client.post(reverse('upload_documento'), {'arquivo': arquivo}, follow=True)

        self.assertEqual(DocumentoCliente.objects.count(), 0)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('muito grande' in m for m in messages))


class ValidarArquivoDocumentoTests(SimpleTestCase):

    def test_disallowed_extension_returns_error_message(self):
        arquivo = SimpleUploadedFile('script.js', b'x', content_type='text/javascript')

        erro = views._validar_arquivo_documento(arquivo)

        self.assertIsNotNone(erro)
        self.assertIn('não permitido', erro)

    def test_oversized_file_returns_error_message(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'x' * (11 * 1024 * 1024), content_type='application/pdf')

        erro = views._validar_arquivo_documento(arquivo)

        self.assertIsNotNone(erro)
        self.assertIn('muito grande', erro)

    def test_valid_file_returns_none(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo pequeno', content_type='application/pdf')

        self.assertIsNone(views._validar_arquivo_documento(arquivo))


class DownloadExcluirDocumentoViewTests(TestCase):

    def test_download_404_when_missing(self):
        response = self.client.get(reverse('download_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': 999999}))
        self.assertEqual(response.status_code, 404)

    def test_download_404_when_cliente_ref_does_not_match_pk_in_url(self):
        # IDOR: doc_id sozinho nao basta -- o pk na URL precisa bater com o
        # cliente_ref real do documento, senao 404 mesmo com doc_id valido.
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)

        response = self.client.get(reverse('download_documento', kwargs={'pk': 'CLI-outrocliente', 'doc_id': doc.id}))

        self.assertEqual(response.status_code, 404)

    def test_download_404_when_file_missing_from_disk(self):
        doc = DocumentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', nome_original='fake.pdf', tamanho_bytes=1,
        )
        doc.arquivo.name = 'documentos_clientes/nao-existe/fake.pdf'
        doc.save(update_fields=['arquivo'])

        response = self.client.get(reverse('download_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))

        self.assertEqual(response.status_code, 404)

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_download_success(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
        doc = DocumentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', arquivo=arquivo, nome_original='doc.pdf', tamanho_bytes=8,
        )

        response = self.client.get(reverse('download_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('doc.pdf', response['Content-Disposition'])
        response.close()

    def test_excluir_requires_post(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)
        response = self.client.get(reverse('excluir_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))
        self.assertEqual(response.status_code, 405)

    def test_excluir_404_when_cliente_ref_does_not_match_pk_in_url(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)

        response = self.client.post(reverse('excluir_documento', kwargs={'pk': 'CLI-outrocliente', 'doc_id': doc.id}))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(DocumentoCliente.objects.count(), 1)

    def test_excluir_redirects_using_pk_from_url(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)

        response = self.client.post(reverse('excluir_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))

        self.assertRedirects(
            response, reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), fetch_redirect_response=False,
        )
        self.assertEqual(DocumentoCliente.objects.count(), 0)


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class AppStateDownloadViewTests(ListRowsPatchMixin, TestCase):

    def test_get_without_data_returns_empty_xlsx(self):
        self.patch_list_rows({})

        response = self.client.get(reverse('app_state_download'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_get_exports_current_sheet_data(self):
        self.patch_list_rows({
            'Clientes': [{'cliente': 'Ana'}],
            'Parceiros': [{'nome': 'Escritorio A'}],
            'Precos': [{'tipo': 'e-CPF A1'}],
        })

        response = self.client.get(reverse('app_state_download'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_post_also_exports_current_sheet_data_ignoring_any_body(self):
        self.patch_list_rows({'Clientes': [{'cliente': 'Ana'}]})

        response = self.client.post(reverse('app_state_download'), data='isso nao e mais usado', content_type='text/plain')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_failure_returns_500(self):
        patcher = patch.object(repo, 'list_rows', side_effect=Exception('planilha indisponivel'))
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.client.get(reverse('app_state_download'))

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.json())


class MarcarPagamentoAprovadoTests(TestCase):

    def _make_pagamento(self, cliente_ref='CLI-aaaaaaaa'):
        return PagamentoCliente.objects.create(
            cliente_ref=cliente_ref, nome_cliente='Ana Silva', email_cliente='ana@example.com',
            valor=100, descricao='Certificado',
        )

    def test_updates_sheet_row_when_cliente_ref_present(self):
        pagamento = self._make_pagamento()

        with patch.object(repo, 'get_row', return_value={'id': 'CLI-aaaaaaaa', 'atualizado_em': '2024-01-01T00:00:00+00:00'}), \
             patch.object(repo, 'update_row') as mock_update:
            views._marcar_pagamento_aprovado(pagamento)

        mock_update.assert_called_once_with(
            'Clientes', 'CLI-aaaaaaaa', {'pago_venda': 'Sim'},
            expected_atualizado_em='2024-01-01T00:00:00+00:00',
        )

    def test_does_nothing_to_sheet_when_cliente_ref_blank(self):
        pagamento = self._make_pagamento(cliente_ref='')

        with patch.object(repo, 'update_row') as mock_update:
            views._marcar_pagamento_aprovado(pagamento)

        mock_update.assert_not_called()

    def test_swallows_lookup_error(self):
        pagamento = self._make_pagamento()

        with patch.object(repo, 'get_row', return_value=None), \
             patch.object(repo, 'update_row', side_effect=LookupError('sumiu')):
            views._marcar_pagamento_aprovado(pagamento)

    def test_swallows_generic_exception(self):
        pagamento = self._make_pagamento()

        with patch.object(repo, 'get_row', return_value=None), \
             patch.object(repo, 'update_row', side_effect=Exception('planilha fora do ar')):
            views._marcar_pagamento_aprovado(pagamento)

    def test_marks_matching_cliente_as_paid_in_app_state_blob(self):
        AppState.objects.create(key='main', data={'clientes': [{'id': 'CLI-aaaaaaaa', 'pago': False}]})
        pagamento = self._make_pagamento()

        with patch.object(repo, 'get_row', return_value=None), \
             patch.object(repo, 'update_row'):
            views._marcar_pagamento_aprovado(pagamento)

        state = AppState.objects.get(key='main')
        self.assertTrue(state.data['clientes'][0]['pago'])


# NOTA: criar_pagamento_pix e webhook_mercado_pago não têm nenhuma rota em
# core/urls.py hoje (import presente, sem path() correspondente) -- por isso
# são testadas aqui via RequestFactory chamando a view diretamente, não por
# reverse()/self.client. Além disso, ambas chamam gerar_pagamento_mercado_pago
# / consultar_pagamento_mercado_pago, que não existem em lugar nenhum do
# código (nem em services.py, mesmo antes da migração pra Sheets) -- o
# pagamento PIX real está quebrado hoje. Os testes abaixo travam o
# comportamento ATUAL (erro 500/400 nesse ponto), não o comportamento
# desejado -- servem para não deixar isso regredir silenciosamente até que
# alguém implemente as duas funções de verdade.
class CriarPagamentoPixViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_requires_post(self):
        request = self.factory.get('/criar-pagamento-pix/')
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_body_returns_400(self):
        request = self.factory.post('/criar-pagamento-pix/', data='not-json', content_type='application/json')
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 400)

    def test_valor_zero_or_negative_returns_400(self):
        request = self.factory.post('/criar-pagamento-pix/', {'valor': '0', 'email_cliente': 'ana@example.com'})
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Valor inválido', json.loads(response.content)['error'])

    def test_missing_email_returns_400(self):
        request = self.factory.post('/criar-pagamento-pix/', {'valor': '100'})
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('email_cliente', json.loads(response.content)['error'])

    def test_valid_payload_currently_fails_missing_helper(self):
        request = self.factory.post('/criar-pagamento-pix/', {'valor': '100', 'email_cliente': 'ana@example.com'})
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn('gerar_pagamento_mercado_pago', json.loads(response.content)['error'])

    def test_invalid_valor_string_defaults_to_zero_and_returns_400(self):
        request = self.factory.post('/criar-pagamento-pix/', {'valor': 'abc', 'email_cliente': 'ana@example.com'})
        response = views.criar_pagamento_pix(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Valor inválido', json.loads(response.content)['error'])

    def test_success_path_with_mocked_helper_creates_pagamento(self):
        # gerar_pagamento_mercado_pago não existe de verdade (ver nota da classe) --
        # este teste documenta o contrato esperado (shape do retorno) e confirma
        # que o resto da view (criação do PagamentoCliente, resposta JSON) já
        # funciona corretamente assumindo que a função venha a ser implementada.
        fake_payment = {
            'id': 123456,
            'status': 'pending',
            'point_of_interaction': {'transaction_data': {'qr_code_base64': 'ZmFrZQ==', 'qr_code': '00020126'}},
        }
        with patch.object(views, 'gerar_pagamento_mercado_pago', return_value=fake_payment, create=True):
            request = self.factory.post('/criar-pagamento-pix/', {
                'valor': '150', 'email_cliente': 'ana@example.com', 'nome_cliente': 'Ana Silva', 'cliente_ref': 'CLI-aaaaaaaa',
            })
            response = views.criar_pagamento_pix(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['gateway_payment_id'], '123456')
        self.assertEqual(data['qr_code_base64'], 'ZmFrZQ==')
        pagamento = PagamentoCliente.objects.get(pk=data['pagamento_id'])
        self.assertEqual(pagamento.cliente_ref, 'CLI-aaaaaaaa')
        self.assertEqual(pagamento.status, PagamentoCliente.STATUS_PENDING)


class WebhookMercadoPagoViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_requires_post(self):
        request = self.factory.get('/webhook-mercado-pago/')
        response = views.webhook_mercado_pago(request)
        self.assertEqual(response.status_code, 405)

    def test_ignores_non_payment_topic(self):
        request = self.factory.post('/webhook-mercado-pago/?topic=merchant_order&id=123')
        response = views.webhook_mercado_pago(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'ignored')

    def test_ignores_when_payment_id_missing(self):
        request = self.factory.post('/webhook-mercado-pago/?topic=payment')
        response = views.webhook_mercado_pago(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'ignored')

    def test_payment_topic_currently_fails_missing_helper(self):
        request = self.factory.post('/webhook-mercado-pago/?topic=payment&id=123')
        response = views.webhook_mercado_pago(request)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('consultar_pagamento_mercado_pago', data['message'])

    def test_extracts_payment_id_from_json_body_when_no_query_param(self):
        body = json.dumps({'action': 'payment.updated', 'data': {'id': '999'}})
        request = self.factory.post('/webhook-mercado-pago/', data=body, content_type='application/json')
        response = views.webhook_mercado_pago(request)
        # Sem payment_id/topic na query string, o body é usado -- ainda cai no
        # mesmo bug de consultar_pagamento_mercado_pago ausente, mas confirma
        # que a extração do id a partir do body funcionou (não foi "ignored").
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['status'], 'error')

    def test_approved_payment_updates_pagamento_and_marks_approved(self):
        pagamento = PagamentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', nome_cliente='Ana Silva', email_cliente='ana@example.com',
            valor=100, descricao='Certificado', gateway_payment_id='123',
        )
        fake_payment_info = {'status': 'approved'}
        with patch.object(views, 'consultar_pagamento_mercado_pago', return_value=fake_payment_info, create=True), \
             patch.object(repo, 'get_row', return_value={'id': 'CLI-aaaaaaaa', 'atualizado_em': '2024-01-01T00:00:00+00:00'}), \
             patch.object(repo, 'update_row') as mock_update:
            request = self.factory.post('/webhook-mercado-pago/?topic=payment&id=123')
            response = views.webhook_mercado_pago(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'success')
        pagamento.refresh_from_db()
        self.assertEqual(pagamento.status, PagamentoCliente.STATUS_APPROVED)
        mock_update.assert_called_once_with(
            'Clientes', 'CLI-aaaaaaaa', {'pago_venda': 'Sim'},
            expected_atualizado_em='2024-01-01T00:00:00+00:00',
        )


class LoginRequiredTests(DjangoTestCase):
    """Usa a TestCase original do Django (sem login automático) porque estes
    testes precisam controlar o estado de autenticação eles mesmos.

    O login real passa pelo SheetsBackend (core/app_Gestor/auth_backends.py),
    que busca usuário/senha na aba 'Usuarios' da planilha em vez do banco
    local -- por isso `repo.list_rows('Usuarios')` é mockado aqui em vez de
    usar a senha do `auth_user` local diretamente."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username=_TEST_USER_USERNAME)
        usuarios_rows = [{'username': _TEST_USER_USERNAME, 'password': make_password(_TEST_USER_PASSWORD)}]
        patcher = patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_protected_route_redirects_anonymous_to_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_page_is_public_and_renders_form(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="post">')

    def test_login_with_valid_credentials_redirects_and_authenticates(self):
        response = self.client.post(reverse('login'), {
            'username': _TEST_USER_USERNAME, 'password': _TEST_USER_PASSWORD,
        })

        self.assertRedirects(response, reverse('dashboard'))
        # Confirma que a sessao ficou autenticada: a proxima requisicao a uma
        # rota protegida nao deve mais redirecionar para o login.
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_login_with_invalid_credentials_shows_error_and_stays_anonymous(self):
        response = self.client.post(reverse('login'), {
            'username': _TEST_USER_USERNAME, 'password': 'senha-errada',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inválidos')
        response = self.client.get(reverse('dashboard'))
        self.assertNotEqual(response.status_code, 200)

    def test_logout_ends_session_and_protected_route_redirects_again(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('login'))
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_with_tipo_admin_grants_is_superuser(self):
        usuarios_rows = [{'username': 'chefe', 'password': make_password('senha123'), 'tipo': 'admin'}]
        with patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else []):
            self.client.post(reverse('login'), {'username': 'chefe', 'password': 'senha123'})

        user = get_user_model().objects.get(username='chefe')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_login_with_tipo_vendedor_does_not_grant_is_superuser(self):
        usuarios_rows = [{'username': 'vendedor1', 'password': make_password('senha123'), 'tipo': 'vendedor'}]
        with patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else []):
            self.client.post(reverse('login'), {'username': 'vendedor1', 'password': 'senha123'})

        user = get_user_model().objects.get(username='vendedor1')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_tipo_change_in_sheet_takes_effect_on_next_login(self):
        User = get_user_model()
        existing = User.objects.create_user(username='promovido', is_superuser=False, is_staff=False)
        usuarios_rows = [{'username': 'promovido', 'password': make_password('senha123'), 'tipo': 'admin'}]

        with patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else []):
            self.client.post(reverse('login'), {'username': 'promovido', 'password': 'senha123'})

        existing.refresh_from_db()
        self.assertTrue(existing.is_superuser)

    def test_login_syncs_granular_perms_for_vendedor(self):
        usuarios_rows = [{
            'username': 'vendedor-sync', 'password': make_password('senha123'), 'tipo': 'vendedor',
            'perm_parceiros': 'Sim', 'perm_precos': 'Não',
        }]
        with patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else []):
            self.client.post(reverse('login'), {'username': 'vendedor-sync', 'password': 'senha123'})

        perms = self.client.session.get('perms')
        self.assertEqual(perms.get('parceiros'), True)
        self.assertEqual(perms.get('precos'), False)
        self.assertEqual(perms.get('pagamentos'), False)
        self.assertEqual(perms.get('excluir_cliente'), False)
        self.assertEqual(perms.get('excluir_documento'), False)

    def test_login_does_not_set_perms_for_admin(self):
        usuarios_rows = [{'username': 'chefe-perms', 'password': make_password('senha123'), 'tipo': 'admin'}]
        with patch.object(repo, 'list_rows', side_effect=lambda tab: usuarios_rows if tab == 'Usuarios' else []):
            self.client.post(reverse('login'), {'username': 'chefe-perms', 'password': 'senha123'})

        self.assertEqual(self.client.session.get('perms'), {})


class PermissionRequiredTests(DjangoTestCase):
    """Endpoints admin-only (excluir, Parceiros, Preços) devem bloquear um
    usuário vendedor (is_superuser=False) e liberar um admin."""

    def setUp(self):
        User = get_user_model()
        self.vendedor = User.objects.create_user(username='vendedor-perm', is_superuser=False, is_staff=False)
        self.admin = User.objects.create_user(username='admin-perm', is_superuser=True, is_staff=True)

    def test_vendedor_blocked_from_cliente_excluir(self):
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))
        self.assertEqual(response.status_code, 403)

    def test_admin_allowed_on_cliente_excluir(self):
        self.client.force_login(self.admin)
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))
        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once()

    def test_vendedor_blocked_from_parceiro_criar(self):
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('parceiro_criar'), {'nome': 'Escritorio X'})
        self.assertEqual(response.status_code, 403)

    def test_vendedor_blocked_from_parceiro_excluir(self):
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('parceiro_excluir', kwargs={'id': 'PAR-aaaaaaaa'}))
        self.assertEqual(response.status_code, 403)

    def test_vendedor_blocked_from_preco_criar(self):
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('preco_criar'), {'tipo': 'e-CPF A1'})
        self.assertEqual(response.status_code, 403)

    def test_vendedor_blocked_from_preco_excluir(self):
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('preco_excluir', kwargs={'id': 'PRC-aaaaaaaa'}))
        self.assertEqual(response.status_code, 403)

    def test_vendedor_blocked_from_excluir_documento(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)
        self.client.force_login(self.vendedor)
        response = self.client.post(reverse('excluir_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))
        self.assertEqual(response.status_code, 403)

    def test_vendedor_still_allowed_on_cliente_edit(self):
        # Editar cliente (não excluir) continua liberado pro vendedor -- só
        # exclusão e as áreas de Preços/Parceiros são admin-only.
        self.client.force_login(self.vendedor)
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'cliente': 'Ana Silva', 'pago_comissao': 'Sim'},
            )
        self.assertRedirects(response, reverse('dashboard') + '#clientes', fetch_redirect_response=False)
        mock_update.assert_called_once()

    def _login_vendedor_with_perms(self, perms):
        # SESSION_ENGINE=signed_cookies não tem storage server-side -- a
        # sessão inteira É o valor do cookie, então session.save() sozinho
        # não basta em teste (não passa por um response real). Precisa
        # empurrar o cookie assinado de volta pro client manualmente.
        self.client.force_login(self.vendedor)
        session = self.client.session
        session['perms'] = perms
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_vendedor_with_excluir_cliente_perm_allowed(self):
        self._login_vendedor_with_perms({'excluir_cliente': True})
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('cliente_excluir', kwargs={'pk': 'CLI-aaaaaaaa'}))
        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once()

    def test_vendedor_with_parceiros_perm_allowed_on_criar(self):
        self._login_vendedor_with_perms({'parceiros': True})
        with patch.object(repo, 'create_row', return_value={'id': 'PAR-aaaaaaaa'}):
            response = self.client.post(reverse('parceiro_criar'), {'nome': 'Escritorio X'})
        self.assertEqual(response.status_code, 200)

    def test_vendedor_with_parceiros_perm_allowed_on_excluir(self):
        self._login_vendedor_with_perms({'parceiros': True})
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('parceiro_excluir', kwargs={'id': 'PAR-aaaaaaaa'}))
        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once()

    def test_vendedor_with_precos_perm_allowed_on_criar(self):
        self._login_vendedor_with_perms({'precos': True})
        with patch.object(repo, 'create_row', return_value={'id': 'PRC-aaaaaaaa'}):
            response = self.client.post(reverse('preco_criar'), {'tipo': 'e-CPF A1'})
        self.assertEqual(response.status_code, 200)

    def test_vendedor_with_precos_perm_allowed_on_excluir(self):
        self._login_vendedor_with_perms({'precos': True})
        with patch.object(repo, 'delete_row') as mock_delete:
            response = self.client.post(reverse('preco_excluir', kwargs={'id': 'PRC-aaaaaaaa'}))
        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once()

    def test_vendedor_with_excluir_documento_perm_allowed(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)
        self._login_vendedor_with_perms({'excluir_documento': True})
        response = self.client.post(reverse('excluir_documento', kwargs={'pk': 'CLI-aaaaaaaa', 'doc_id': doc.id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DocumentoCliente.objects.filter(pk=doc.id).exists())

    def test_vendedor_with_one_perm_still_blocked_from_others(self):
        # Confirma que a permissão é granular de verdade -- ter 'parceiros'
        # não libera 'precos'.
        self._login_vendedor_with_perms({'parceiros': True})
        response = self.client.post(reverse('preco_criar'), {'tipo': 'e-CPF A1'})
        self.assertEqual(response.status_code, 403)

    def test_vendedor_blocked_from_usuarios_gestao_even_with_all_perms(self):
        # Gestão de usuários não é uma permissão delegável -- só is_superuser
        # dá acesso, mesmo que o vendedor tenha todas as outras chaves.
        all_perms = {key: True for key in PERM_KEYS}
        self._login_vendedor_with_perms(all_perms)
        response = self.client.get(reverse('usuarios_gestao'))
        self.assertEqual(response.status_code, 403)

    def test_admin_allowed_on_usuarios_gestao(self):
        self.client.force_login(self.admin)
        with patch.object(repo, 'list_rows', return_value=[]):
            response = self.client.get(reverse('usuarios_gestao'))
        self.assertEqual(response.status_code, 200)

    def test_vendedor_blocked_from_usuarios_atualizar(self):
        self._login_vendedor_with_perms({key: True for key in PERM_KEYS})
        response = self.client.post(reverse('usuarios_atualizar', kwargs={'id': 'USR-aaaaaaaa'}), {'tipo': 'admin'})
        self.assertEqual(response.status_code, 403)

    def test_admin_allowed_on_usuarios_atualizar(self):
        self.client.force_login(self.admin)
        with patch.object(repo, 'update_row') as mock_update:
            response = self.client.post(
                reverse('usuarios_atualizar', kwargs={'id': 'USR-aaaaaaaa'}),
                {'tipo': 'vendedor', 'perm_parceiros': 'on'},
            )
        self.assertEqual(response.status_code, 302)
        mock_update.assert_called_once()
        called_fields = mock_update.call_args.args[2]
        self.assertEqual(called_fields['tipo'], 'vendedor')
        self.assertEqual(called_fields['perm_parceiros'], 'Sim')
        self.assertEqual(called_fields['perm_precos'], 'Não')

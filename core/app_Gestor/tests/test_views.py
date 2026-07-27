import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.app_Gestor import sheets_repository as repo
from core.app_Gestor import views
from core.app_Gestor.models import AppState, DocumentoCliente, PagamentoCliente

_MEDIA_ROOT = tempfile.mkdtemp(prefix='qcert_test_media_')


CLIENTE_ROW = {
    'id': 'CLI-aaaaaaaa',
    'atualizado_em': '2024-01-01T00:00:00+00:00',
    'data_venda': '2024-01-01',
    'contador_parceiro': 'Escritorio A',
    'contador_contabilidade': '',
    'telefone1': '(11) 99999-0000',
    'cliente': 'Ana Silva',
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


class BuildDashboardFromSheetsTests(ListRowsPatchMixin, SimpleTestCase):

    def test_builds_one_row_per_sheet_row_with_formatted_cells(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture()]})

        cols, rows = views._build_dashboard_from_sheets()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'CLI-aaaaaaaa')
        self.assertEqual(len(rows[0]['cells']), len(cols))
        cliente_cell = rows[0]['cells'][cols.index(next(c for c in cols if c['field'] == 'cliente'))]
        self.assertEqual(cliente_cell['value'], 'Ana Silva')

    def test_empty_sheet_returns_no_rows(self):
        self.patch_list_rows({'Clientes': []})

        _, rows = views._build_dashboard_from_sheets()

        self.assertEqual(rows, [])


class BuildAlertPayloadTests(ListRowsPatchMixin, SimpleTestCase):

    def test_row_without_vencimento_is_ignored(self):
        self.patch_list_rows({'Clientes': [_clientes_fixture(data_vencimento='')]})

        payload = views._build_alert_payload()

        self.assertEqual(payload['counts']['alertas_totais'], 0)

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
        }])


class BuildPrecosFromSourceTests(ListRowsPatchMixin, SimpleTestCase):

    def test_maps_sheet_rows_to_preco_dicts(self):
        self.patch_list_rows({'Precos': [{
            'id': 'PRC-aaaaaaaa', 'atualizado_em': '', 'tipo': 'e-CPF A1', 'validade': '1 ano', 'preco': '150',
        }]})

        precos = views._build_precos_from_source()

        self.assertEqual(precos, [{'id': 'PRC-aaaaaaaa', 'tipo': 'e-CPF A1', 'validade': '1 ano', 'preco': 150.0}])


@override_settings(GOOGLE_SHEET_ID='fake-sheet-id')
class DashboardViewTests(ListRowsPatchMixin, TestCase):

    def setUp(self):
        self.client = Client()

    def test_renders_ok_with_data_from_sheets(self):
        self.patch_list_rows({
            'Clientes': [_clientes_fixture()],
            'Parceiros': [],
            'Precos': [],
        })

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['google_rows']), 1)

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

    def test_post_invalid_valor_comissao_is_silently_ignored(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row') as mock_update:
            self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'valor_comissao': 'não é número', 'pago_comissao': 'Não'},
            )

        tab, pk, fields = mock_update.call_args.args
        self.assertNotIn('valor_comissao', fields)

    def test_post_generic_failure_shows_error_message(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row', side_effect=Exception('planilha fora do ar')), \
             patch.object(repo, 'list_rows', return_value=[]):
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'pago_comissao': 'Sim'},
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
                {'pago_comissao': 'Sim', 'expected_atualizado_em': 'stale'},
                follow=True,
            )

        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('alterado por outra pessoa' in m for m in messages))

    def test_post_row_deleted_meanwhile_raises_404(self):
        with patch.object(repo, 'get_row', return_value=_clientes_fixture()), \
             patch.object(repo, 'update_row', side_effect=LookupError('sumiu')):
            response = self.client.post(
                reverse('editar_google_row', kwargs={'pk': 'CLI-aaaaaaaa'}),
                {'pago_comissao': 'Sim'},
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


class DownloadExcluirDocumentoViewTests(TestCase):

    def test_download_404_when_missing(self):
        response = self.client.get(reverse('download_documento', kwargs={'doc_id': 999999}))
        self.assertEqual(response.status_code, 404)

    def test_download_404_when_file_missing_from_disk(self):
        doc = DocumentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', nome_original='fake.pdf', tamanho_bytes=1,
        )
        doc.arquivo.name = 'documentos_clientes/nao-existe/fake.pdf'
        doc.save(update_fields=['arquivo'])

        response = self.client.get(reverse('download_documento', kwargs={'doc_id': doc.id}))

        self.assertEqual(response.status_code, 404)

    @override_settings(MEDIA_ROOT=_MEDIA_ROOT)
    def test_download_success(self):
        arquivo = SimpleUploadedFile('doc.pdf', b'conteudo', content_type='application/pdf')
        doc = DocumentoCliente.objects.create(
            cliente_ref='CLI-aaaaaaaa', arquivo=arquivo, nome_original='doc.pdf', tamanho_bytes=8,
        )

        response = self.client.get(reverse('download_documento', kwargs={'doc_id': doc.id}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('doc.pdf', response['Content-Disposition'])
        response.close()

    def test_excluir_requires_post(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)
        response = self.client.get(reverse('excluir_documento', kwargs={'doc_id': doc.id}))
        self.assertEqual(response.status_code, 405)

    def test_excluir_redirects_using_cliente_ref(self):
        doc = DocumentoCliente.objects.create(cliente_ref='CLI-aaaaaaaa', nome_original='doc.pdf', tamanho_bytes=1)

        response = self.client.post(reverse('excluir_documento', kwargs={'doc_id': doc.id}))

        self.assertRedirects(
            response, reverse('documentos_cliente', kwargs={'pk': 'CLI-aaaaaaaa'}), fetch_redirect_response=False,
        )
        self.assertEqual(DocumentoCliente.objects.count(), 0)


class AppStateDownloadViewTests(TestCase):

    def test_get_without_saved_state_returns_empty_xlsx(self):
        response = self.client.get(reverse('app_state_download'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_get_uses_saved_app_state(self):
        AppState.objects.create(key='main', data={'clientes': [{'nome': 'Ana'}], 'parceiros': [], 'precos': []})

        response = self.client.get(reverse('app_state_download'))

        self.assertEqual(response.status_code, 200)

    def test_post_with_payload_returns_xlsx(self):
        response = self.client.post(
            reverse('app_state_download'),
            data='{"clientes": [{"nome": "Ana"}], "parceiros": [{"nome": "Escritorio A"}], "precos": [{"tipo": "e-CPF A1"}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_post_invalid_json_returns_500(self):
        response = self.client.post(
            reverse('app_state_download'), data='not json', content_type='application/json',
        )

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

        with patch.object(repo, 'update_row') as mock_update:
            views._marcar_pagamento_aprovado(pagamento)

        mock_update.assert_called_once_with('Clientes', 'CLI-aaaaaaaa', {'pago_venda': 'Sim'})

    def test_does_nothing_to_sheet_when_cliente_ref_blank(self):
        pagamento = self._make_pagamento(cliente_ref='')

        with patch.object(repo, 'update_row') as mock_update:
            views._marcar_pagamento_aprovado(pagamento)

        mock_update.assert_not_called()

    def test_swallows_lookup_error(self):
        pagamento = self._make_pagamento()

        with patch.object(repo, 'update_row', side_effect=LookupError('sumiu')):
            views._marcar_pagamento_aprovado(pagamento)

    def test_swallows_generic_exception(self):
        pagamento = self._make_pagamento()

        with patch.object(repo, 'update_row', side_effect=Exception('planilha fora do ar')):
            views._marcar_pagamento_aprovado(pagamento)

    def test_marks_matching_cliente_as_paid_in_app_state_blob(self):
        AppState.objects.create(key='main', data={'clientes': [{'id': 'CLI-aaaaaaaa', 'pago': False}]})
        pagamento = self._make_pagamento()

        with patch.object(repo, 'update_row'):
            views._marcar_pagamento_aprovado(pagamento)

        state = AppState.objects.get(key='main')
        self.assertTrue(state.data['clientes'][0]['pago'])

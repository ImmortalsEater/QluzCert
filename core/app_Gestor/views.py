from datetime import date, datetime
from .models import DocumentoCliente, PagamentoCliente
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.conf import settings
import json
import logging
import os
import re
from .models import AppState
from . import sheets_repository
from .parsing import parse_date, parse_decimal, bool_from
import io
import pandas as pd
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def _safe_json_dumps(obj):
    """json.dumps escapando '<', '>' e '&' como \\uXXXX -- continua JSON
    válido (esses escapes funcionam dentro de qualquer string JSON), mas
    impede que um valor vindo da planilha (ex: nome de cliente contendo
    "</script><script>...") feche a tag <script> onde este JSON é embutido
    em dashboard.html e injete HTML/JS arbitrário no dashboard."""
    dumped = json.dumps(obj, default=str)
    return dumped.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


# Traduz nomes técnicos de coluna (vindos direto do cabeçalho da planilha do
# Google Drive) para rótulos legíveis. Chave = nome do campo normalizado
# (minúsculo, sem acentos/pontuação).
FRIENDLY_COLUMN_LABELS = {
    'id': 'ID',
    'criadoem': 'Criado em',
    'historico': 'Histórico',
    'nome': 'Cliente',
    'cpfcnpj': 'CPF/CNPJ',
    'datanasc': 'Data de Nascimento',
    'telefone': 'Telefone',
    'email': 'E-mail',
    'parceiroid': 'Parceiro',
    'status': 'Status',
    'obs': 'Observações',
    'tipocert': 'Tipo de Certificado',
    'dataemissao': 'Data de Emissão',
    'datavencimento': 'Data de Vencimento',
    'valorcobrado': 'Valor Cobrado',
    'formapag': 'Forma de Pagamento',
    'pago': 'Pago',
}

def _normalize_field_key(field_name):
    return re.sub(r'[^a-z0-9]', '', str(field_name or '').lower())


def _annotate_columns(cols):
    annotated = []
    for col in cols:
        key = _normalize_field_key(col.get('field'))
        annotated.append({
            **col,
            'label': FRIENDLY_COLUMN_LABELS.get(key, col.get('label')),
            'default_visible': True,
        })
    return annotated


STATUS_OPCOES = ['Novo Lead', 'Documentação Pendente', 'Aguardando Pagamento', 'Agendado para Vídeo', 'Emitido']


CLIENTES_COLUMNS = [
    {'label':'Data da Venda','field':'data_venda','class':'col-data-venda'},
    {'label':'Contador/Parceiro','field':'contador_parceiro','class':'col-contador-parceiro'},
    {'label':'Contador/Contabilidade','field':'contador_contabilidade','class':'col-contador-contabilidade'},
    {'label':'Telefone','field':'telefone1','class':'col-telefone1'},
    {'label':'Cliente','field':'cliente','class':'col-cliente'},
    {'label':'Status','field':'status','class':'col-status'},
    {'label':'CPF/CNPJ','field':'cpf_cnpj','class':'col-cpf-cnpj'},
    {'label':'email','field':'email','class':'col-email'},
    {'label':'Telefone2','field':'telefone2','class':'col-telefone2'},
    {'label':'Tipo de Certificado','field':'tipo_certificado','class':'col-tipo-certificado'},
    {'label':'Valor da Venda (R$)','field':'valor_venda','class':'col-valor-venda'},
    {'label':'Percentual de Comissão (%)','field':'percentual_comissao','class':'col-percentual'},
    {'label':'Valor da Comissão (R$)','field':'valor_comissao','class':'col-valor-comissao'},
    {'label':'Pago_Comissao','field':'pago_comissao','class':'col-pago-comissao'},
    {'label':'Chave PIX','field':'chave_pix','class':'col-chave-pix'},
    {'label':'Data de Vencimento','field':'data_vencimento','class':'col-data-vencimento'},
    {'label':'Pago_Venda','field':'pago_venda','class':'col-pago-venda'},
    {'label':'Forma de pagamento','field':'forma_pagamento','class':'col-forma-pagamento'},
    {'label':'Banco','field':'banco','class':'col-banco'},
    {'label':'Certfificado Feito','field':'certificado_feito','class':'col-cert-feito'},
    {'label':'Venda','field':'venda','class':'col-venda'},
    {'label':'Custo do Certificado','field':'custo_certificado','class':'col-custo-cert'},
    {'label':'Valor Liquido','field':'valor_liquido','class':'col-valor-liquido'},
    {'label':'Atualizado em','field':'atualizado_em','class':'col-atualizado-em'},
]

_DATE_FIELDS = {'data_venda', 'data_vencimento'}
_DATETIME_FIELDS = {'atualizado_em'}
_DECIMAL_FIELDS = {'valor_venda', 'percentual_comissao', 'valor_comissao', 'custo_certificado', 'valor_liquido'}
_BOOL_FIELDS = {'pago_comissao', 'pago_venda'}


def _format_sheet_cell_value(field, raw):
    if raw is None or raw == '':
        return '—'
    if field in _DATE_FIELDS:
        parsed = parse_date(raw)
        return parsed.strftime('%d/%m/%Y') if parsed else raw
    if field in _DATETIME_FIELDS:
        try:
            parsed_dt = datetime.fromisoformat(str(raw))
            return parsed_dt.strftime('%d/%m/%Y %H:%M')
        except Exception:
            return raw
    if field in _DECIMAL_FIELDS:
        parsed = parse_decimal(raw)
        return f"{parsed:.2f}".replace('.', ',') if parsed is not None else raw
    if field in _BOOL_FIELDS:
        return 'Sim' if bool_from(raw) else 'Não'
    return raw


def _build_dashboard_from_sheets():
    cols = _annotate_columns(CLIENTES_COLUMNS)
    rows = []
    for row in sheets_repository.list_rows('Clientes'):
        row_id = row.get('id', '')
        if not row_id:
            # Linha sem id não é editável/endereçável (provável corrupção do
            # cabeçalho da planilha) -- ignorada em vez de derrubar a página
            # inteira quando o template tentar montar um link com id vazio.
            continue
        cells = [
            {
                'class': col['class'],
                'value': _format_sheet_cell_value(col['field'], row.get(col['field'], '')),
                'default_visible': col['default_visible'],
            }
            for col in cols
        ]
        rows.append({'id': row_id, 'cells': cells})
    return cols, rows


def _build_alert_payload():
    hoje = date.today()
    renovacoes_urgentes = []
    renovacoes_normais = []
    pagamentos_urgentes = []
    pagamentos_normais = []

    rows = [r for r in sheets_repository.list_rows('Clientes') if r.get('id')]
    # "Emitidos" conta pelo status do funil (o que o usuário de fato move no
    # Kanban), não pelo campo certificado_feito -- esse campo só é editável
    # manualmente na página de edição completa e na prática nunca é marcado
    # quando o card é movido para "Emitido" no funil, subcontando o card.
    emitidos = sum(1 for row in rows if (row.get('status') or '') == 'Emitido')
    vencendo_60_dias = 0

    def _base_payload(row, dias_restantes, vencimento):
        row_id = row.get('id', '')
        valor_venda = parse_decimal(row.get('valor_venda'))
        return {
            'id': f'planilha-{row_id}',
            'planilha_pk': row_id,
            'nome': row.get('cliente') or row.get('contador_parceiro') or row.get('email') or f'Registro {row_id}',
            'email': row.get('email', ''),
            'telefone': row.get('telefone1') or row.get('telefone2') or '',
            'parceiro': row.get('contador_parceiro', ''),
            'tipoCert': row.get('tipo_certificado', ''),
            'dataVencimento': vencimento.isoformat(),
            'dias': dias_restantes,
            'valorCobrado': valor_venda if valor_venda is not None else 0,
            'pago': bool_from(row.get('pago_venda')) or bool_from(row.get('pago_comissao')),
        }

    for row in rows:
        vencimento = parse_date(row.get('data_vencimento'))
        if not vencimento:
            continue

        dias_restantes = (vencimento - hoje).days
        if dias_restantes <= 60:
            vencendo_60_dias += 1
        base = _base_payload(row, dias_restantes, vencimento)
        base['statusLabel'] = f"Vencido há {abs(dias_restantes)} dias" if dias_restantes < 0 else f"Vence em {dias_restantes} dias"

        if dias_restantes <= 30:
            renovacoes_urgentes.append({**base, 'categoria': 'renovacao'})
        elif dias_restantes <= 90:
            renovacoes_normais.append({**base, 'categoria': 'renovacao'})

        if not bool_from(row.get('pago_venda')):
            pagamento_base = {**base, 'categoria': 'pagamento', 'tipoPagamento': 'Venda'}
            if dias_restantes <= 0:
                pagamentos_urgentes.append(pagamento_base)
            elif dias_restantes <= 30:
                pagamentos_normais.append(pagamento_base)

        if not bool_from(row.get('pago_comissao')):
            pagamento_base = {**base, 'categoria': 'pagamento', 'tipoPagamento': 'Comissão'}
            if dias_restantes <= 0:
                pagamentos_urgentes.append(pagamento_base)
            elif dias_restantes <= 30:
                pagamentos_normais.append(pagamento_base)

    counts = {
        'total_registros': len(rows),
        'emitidos': emitidos,
        'vencendo_60_dias': vencendo_60_dias,
        'renovacoes_urgentes': len(renovacoes_urgentes),
        'renovacoes_normais': len(renovacoes_normais),
        'pagamentos_urgentes': len(pagamentos_urgentes),
        'pagamentos_normais': len(pagamentos_normais),
        # Incluído aqui (não só no contexto inicial da DashboardView) para
        # que syncBackendAlertCounts() também atualize o card de faturamento
        # ao consultar /alertas/, e não só no primeiro carregamento da página.
        'faturamento_recebido': _build_faturamento_recebido(),
    }
    counts['alertas_totais'] = (
        counts['renovacoes_urgentes']
        + counts['renovacoes_normais']
        + counts['pagamentos_urgentes']
        + counts['pagamentos_normais']
    )

    return {
        'counts': counts,
        'renovacoes': {'urgentes': renovacoes_urgentes, 'normais': renovacoes_normais},
        'pagamentos': {'urgentes': pagamentos_urgentes, 'normais': pagamentos_normais},
    }


def _build_faturamento_recebido():
    """Soma valor_venda das linhas da planilha 'Clientes' cujo pago_venda é
    verdadeiro. Faturamento é sempre calculado a partir da fonte de dados
    real (Sheets), não da tabela PagamentoCliente (que reflete só os
    pagamentos processados via Mercado Pago, um subconjunto)."""
    total = 0.0
    for row in sheets_repository.list_rows('Clientes'):
        if not bool_from(row.get('pago_venda')):
            continue
        valor = parse_decimal(row.get('valor_venda'))
        if valor is not None:
            total += float(valor)
    return total


def _build_parceiros_from_source():
    parceiros = []
    for row in sheets_repository.list_rows('Parceiros'):
        parceiros.append({
            'id': row.get('id', ''),
            'nome': row.get('nome', ''),
            'tipo': row.get('tipo', ''),
            'telefone': row.get('telefone', ''),
            'email': row.get('email', ''),
            'comissao': parse_decimal(row.get('comissao')),
            'contato': row.get('contato', ''),
            'atualizadoEm': row.get('atualizado_em', ''),
        })
    return parceiros


def _build_precos_from_source():
    precos = []
    for row in sheets_repository.list_rows('Precos'):
        precos.append({
            'id': row.get('id', ''),
            'tipo': row.get('tipo', ''),
            'validade': row.get('validade', ''),
            'preco': parse_decimal(row.get('preco')),
            'atualizadoEm': row.get('atualizado_em', ''),
        })
    return precos


def _build_clientes_leads_from_sheets():
    leads = []
    for row in sheets_repository.list_rows('Clientes'):
        row_id = row.get('id', '')
        if not row_id:
            continue
        vencimento = parse_date(row.get('data_vencimento'))
        leads.append({
            'id': row_id,
            'nome': row.get('cliente', ''),
            'cpfCnpj': row.get('cpf_cnpj', ''),
            'status': row.get('status') or 'Novo Lead',
            'tipoCert': row.get('tipo_certificado', ''),
            'parceiro': row.get('contador_parceiro', ''),
            'telefone': row.get('telefone1') or row.get('telefone2') or '',
            'email': row.get('email', ''),
            'dataVencimento': vencimento.isoformat() if vencimento else '',
            'pago': bool_from(row.get('pago_venda')) or bool_from(row.get('pago_comissao')),
            'atualizadoEm': row.get('atualizado_em', ''),
        })
    return leads


def _build_notificacoes_recentes(limit=6):
    clientes_by_id = {row.get('id'): row for row in sheets_repository.list_rows('Clientes')}
    notificacoes = [row for row in sheets_repository.list_rows('Contatos') if row.get('tipo') == 'notificacao']
    notificacoes.sort(key=lambda row: row.get('atualizado_em', ''), reverse=True)

    result = []
    for row in notificacoes[:limit]:
        cliente = clientes_by_id.get(row.get('cliente_id'), {})
        result.append({
            'id': row.get('id', ''),
            'clienteId': row.get('cliente_id', ''),
            'nome': cliente.get('cliente') or 'Cliente removido',
            'titulo': row.get('titulo') or 'Notificação',
            'texto': row.get('texto', ''),
            'data': row.get('data') or row.get('atualizado_em', ''),
        })
    return result


def alertas_dashboard(request):
    return JsonResponse(_build_alert_payload())


def verificar_registro_existe(request, pk):
    existe = sheets_repository.get_row('Clientes', pk) is not None
    return JsonResponse({'existe': existe})


@require_POST
def atualizar_planilha(request):
    """Força a próxima leitura das abas Clientes/Parceiros/Precos a ignorar o
    cache em memória e buscar dados frescos direto da API do Google Sheets."""
    sheets_repository.invalidate_cache()
    return JsonResponse({'success': True})


@require_POST
def atualizar_status_cliente(request, pk):
    novo_status = (request.POST.get('status') or '').strip()
    if not novo_status:
        return JsonResponse({'error': 'Informe o novo status.'}, status=400)

    expected_atualizado_em = request.POST.get('expected_atualizado_em') or None
    try:
        atualizado = sheets_repository.update_row(
            'Clientes', pk, {'status': novo_status},
            expected_atualizado_em=expected_atualizado_em,
        )
        return JsonResponse({'success': True, 'atualizado_em': atualizado.get('atualizado_em')})
    except sheets_repository.ConcurrencyError:
        return JsonResponse({'error': 'Este registro foi alterado por outra pessoa. Recarregue e tente novamente.'}, status=409)
    except LookupError:
        return JsonResponse({'error': 'Registro não encontrado na planilha.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao atualizar status do cliente %s', pk)
        return JsonResponse({'error': str(e)}, status=500)


_DETALHE_EDITAVEL_FIELDS = {'cliente', 'telefone1', 'email', 'contador_parceiro', 'tipo_certificado', 'data_vencimento'}


@require_POST
def atualizar_detalhe_cliente(request, pk):
    fields = {k: v for k, v in request.POST.items() if k in _DETALHE_EDITAVEL_FIELDS}
    if 'cliente' in fields and not fields['cliente'].strip():
        return JsonResponse({'error': 'Informe o nome do cliente.'}, status=400)

    expected_atualizado_em = request.POST.get('expected_atualizado_em') or None
    try:
        atualizado = sheets_repository.update_row(
            'Clientes', pk, fields, expected_atualizado_em=expected_atualizado_em,
        )
        return JsonResponse({'success': True, 'atualizado_em': atualizado.get('atualizado_em')})
    except sheets_repository.ConcurrencyError:
        return JsonResponse({'error': 'Este registro foi alterado por outra pessoa. Recarregue e tente novamente.'}, status=409)
    except LookupError:
        return JsonResponse({'error': 'Registro não encontrado na planilha.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao atualizar detalhe do cliente %s', pk)
        return JsonResponse({'error': str(e)}, status=500)


class LoginPreviewView(TemplateView):
    template_name = 'login.html'


class CadastroPreviewView(TemplateView):
    template_name = 'cadastro.html'


class RecuperarSenhaPreviewView(TemplateView):
    template_name = 'recuperar-senha.html'


@method_decorator(ensure_csrf_cookie, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['google_columns'], context['google_rows'] = _build_dashboard_from_sheets()
        except Exception:
            logger.exception('Falha ao carregar Clientes da planilha do Google Sheets')
            context['google_columns'], context['google_rows'] = _annotate_columns(CLIENTES_COLUMNS), []

        try:
            state = AppState.objects.filter(key='main').first()
            initial_clientes = state.data.get('clientes', []) if state and isinstance(state.data, dict) else []
        except Exception:
            initial_clientes = []

        try:
            initial_parceiros = _build_parceiros_from_source()
        except Exception:
            initial_parceiros = []

        try:
            initial_precos = _build_precos_from_source()
        except Exception:
            initial_precos = []

        try:
            initial_leads = _build_clientes_leads_from_sheets()
        except Exception:
            initial_leads = []

        try:
            initial_notificacoes = _build_notificacoes_recentes()
        except Exception:
            initial_notificacoes = []

        try:
            alertas = _build_alert_payload()
        except Exception:
            logger.exception('Falha ao montar alertas a partir da planilha do Google Sheets')
            alertas = {
                'counts': {},
                'renovacoes': {'urgentes': [], 'normais': []},
                'pagamentos': {'urgentes': [], 'normais': []},
            }

        try:
            context['initial_clientes_json'] = _safe_json_dumps(initial_clientes)
        except Exception:
            context['initial_clientes_json'] = '[]'
        try:
            context['initial_parceiros_json'] = _safe_json_dumps(initial_parceiros)
        except Exception:
            context['initial_parceiros_json'] = '[]'
        try:
            context['initial_precos_json'] = _safe_json_dumps(initial_precos)
        except Exception:
            context['initial_precos_json'] = '[]'
        try:
            context['initial_leads_json'] = _safe_json_dumps(initial_leads)
        except Exception:
            context['initial_leads_json'] = '[]'
        try:
            context['initial_notificacoes_json'] = _safe_json_dumps(initial_notificacoes)
        except Exception:
            context['initial_notificacoes_json'] = '[]'
        try:
            context['initial_alerts_json'] = _safe_json_dumps(alertas)
        except Exception:
            context['initial_alerts_json'] = '{}'
        try:
            context['alert_counts_json'] = _safe_json_dumps(alertas.get('counts', {}))
        except Exception:
            context['alert_counts_json'] = '{}'
            
        return context
def editar_google_row(request, pk):
    registro = sheets_repository.get_row('Clientes', pk)
    if registro is None:
        raise Http404('Registro não encontrado na planilha.')

    if request.method == 'POST':
        nome = request.POST.get('cliente', '').strip()
        if not nome:
            messages.error(request, 'Informe o nome do cliente.')
            return redirect('editar_google_row', pk=pk)

        fields = {
            'cliente': nome,
            'status': request.POST.get('status', ''),
            'cpf_cnpj': request.POST.get('cpf_cnpj', ''),
            'email': request.POST.get('email', ''),
            'telefone1': request.POST.get('telefone1', ''),
            'telefone2': request.POST.get('telefone2', ''),
            'contador_parceiro': request.POST.get('contador_parceiro', ''),
            'contador_contabilidade': request.POST.get('contador_contabilidade', ''),
            'tipo_certificado': request.POST.get('tipo_certificado', ''),
            'forma_pagamento': request.POST.get('forma_pagamento', ''),
            'banco': request.POST.get('banco', ''),
            'chave_pix': request.POST.get('chave_pix', ''),
            'data_venda': request.POST.get('data_venda', ''),
            'data_vencimento': request.POST.get('data_vencimento', ''),
            'valor_venda': request.POST.get('valor_venda', ''),
            'percentual_comissao': request.POST.get('percentual_comissao', ''),
            'valor_comissao': request.POST.get('valor_comissao', ''),
            'pago_venda': request.POST.get('pago_venda', 'Não'),
            'pago_comissao': request.POST.get('pago_comissao', 'Não'),
            'certificado_feito': request.POST.get('certificado_feito', 'Não'),
            'venda': request.POST.get('venda', ''),
            'custo_certificado': request.POST.get('custo_certificado', ''),
            'valor_liquido': request.POST.get('valor_liquido', ''),
        }

        expected_atualizado_em = request.POST.get('expected_atualizado_em') or None
        try:
            sheets_repository.update_row('Clientes', pk, fields, expected_atualizado_em=expected_atualizado_em)
            messages.success(request, 'Registro atualizado na planilha com sucesso.')
        except sheets_repository.ConcurrencyError:
            messages.error(request, 'Este registro foi alterado por outra pessoa nesse meio tempo. Recarregue a página e tente novamente.')
        except LookupError:
            raise Http404('Registro não encontrado na planilha.')
        except Exception:
            logger.exception('Falha ao atualizar registro %s na planilha', pk)
            messages.error(request, 'Falha ao salvar as alterações na planilha do Google. Tente novamente.')

        return redirect(f"{reverse('dashboard')}#clientes")

    registro_view = {
        **registro,
        'pago_comissao': bool_from(registro.get('pago_comissao')),
        'pago_venda': bool_from(registro.get('pago_venda')),
        'certificado_feito': bool_from(registro.get('certificado_feito')),
    }
    return render(request, 'google_edit.html', {'registro': registro_view, 'status_opcoes': STATUS_OPCOES})


def criar_google_row(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        nome = request.POST.get('cliente', '').strip()
        if not nome:
            if is_ajax:
                return JsonResponse({'error': 'Informe o nome do cliente.'}, status=400)
            messages.error(request, 'Informe o nome do cliente.')
            return render(request, 'google_create.html')

        fields = {
            'cliente': nome,
            'status': request.POST.get('status', 'Novo Lead'),
            'cpf_cnpj': request.POST.get('cpf_cnpj', ''),
            'email': request.POST.get('email', ''),
            'telefone1': request.POST.get('telefone1', ''),
            'telefone2': request.POST.get('telefone2', ''),
            'contador_parceiro': request.POST.get('contador_parceiro', ''),
            'contador_contabilidade': request.POST.get('contador_contabilidade', ''),
            'tipo_certificado': request.POST.get('tipo_certificado', ''),
            'forma_pagamento': request.POST.get('forma_pagamento', ''),
            'banco': request.POST.get('banco', ''),
            'chave_pix': request.POST.get('chave_pix', ''),
            'data_venda': request.POST.get('data_venda', ''),
            'data_vencimento': request.POST.get('data_vencimento', ''),
            'valor_venda': request.POST.get('valor_venda', ''),
            'percentual_comissao': request.POST.get('percentual_comissao', ''),
            'valor_comissao': request.POST.get('valor_comissao', ''),
            'pago_venda': request.POST.get('pago_venda', 'Não'),
            'pago_comissao': request.POST.get('pago_comissao', 'Não'),
        }

        try:
            sheets_repository.create_row('Clientes', fields)
            sheet_ok = True
            sheet_error = ''
        except Exception as e:
            logger.exception('Falha ao criar cliente na planilha: %s', nome)
            sheet_ok = False
            sheet_error = str(e)

        if is_ajax:
            return JsonResponse({'success': sheet_ok, 'drive_updated': sheet_ok, 'drive_error': sheet_error})

        if sheet_ok:
            messages.success(request, 'Cliente criado na planilha com sucesso.')
        else:
            messages.error(request, f'Falha ao criar cliente na planilha: {sheet_error}')

        return redirect(f"{reverse('dashboard')}#clientes")

    return render(request, 'google_create.html')


@require_POST
def cliente_excluir(request, pk):
    try:
        sheets_repository.delete_row('Clientes', pk)
    except LookupError:
        return JsonResponse({'error': 'Cliente não encontrado.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao excluir cliente %s', pk)
        return JsonResponse({'error': str(e)}, status=500)

    # Cliente já foi removido da planilha nesse ponto -- limpa documentos de
    # identidade (RG/CNH, selfie etc.) e pagamentos associados, que ficariam
    # órfãos apontando para um cliente_ref que não existe mais em lugar
    # nenhum. Falha aqui é só logada (não desfaz nem falha a exclusão em si,
    # que já aconteceu de verdade na planilha).
    try:
        for documento in DocumentoCliente.objects.filter(cliente_ref=pk):
            documento.arquivo.delete(save=False)
            documento.delete()
        PagamentoCliente.objects.filter(cliente_ref=pk).delete()
    except Exception:
        logger.exception('Cliente %s excluído da planilha, mas falhou ao limpar documentos/pagamentos associados', pk)

    return JsonResponse({'success': True})


def contatos_cliente_registro(request, pk):
    cliente = sheets_repository.get_row('Clientes', pk)
    if cliente is None:
        return JsonResponse({'error': 'Cliente não encontrado na planilha.'}, status=404)

    if request.method == 'GET':
        contatos = [row for row in sheets_repository.list_rows('Contatos') if row.get('cliente_id') == pk]
        contatos.sort(key=lambda row: row.get('atualizado_em', ''), reverse=True)
        return JsonResponse({
            'cliente': {
                'nome': cliente.get('cliente', ''),
                'telefone': cliente.get('telefone1') or cliente.get('telefone2') or '',
                'email': cliente.get('email', ''),
                'tipoCert': cliente.get('tipo_certificado', ''),
            },
            'contatos': contatos,
        })

    if request.method == 'POST':
        tipo = request.POST.get('tipo', 'contato')
        fields = {
            'cliente_id': pk,
            'tipo': tipo,
            'data': request.POST.get('data', ''),
            'canal': request.POST.get('canal', ''),
            'resultado': request.POST.get('resultado', ''),
            'produto': request.POST.get('produto', ''),
            'agendamento': request.POST.get('agendamento', ''),
            'titulo': request.POST.get('titulo', ''),
            'texto': request.POST.get('texto', ''),
            'status': request.POST.get('status', ''),
        }
        try:
            registro = sheets_repository.create_row('Contatos', fields)
        except Exception as e:
            logger.exception('Falha ao registrar contato para o cliente %s', pk)
            return JsonResponse({'error': str(e)}, status=500)

        novo_status_funil = request.POST.get('novo_status_funil')
        if novo_status_funil:
            try:
                sheets_repository.update_row('Clientes', pk, {'status': novo_status_funil})
            except Exception:
                logger.exception('Falha ao atualizar status do funil junto do contato %s', pk)

        return JsonResponse({'success': True, 'id': registro.get('id')})

    return HttpResponseBadRequest('Método não permitido')


def parceiro_criar(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    nome = request.POST.get('nome', '').strip()
    if not nome:
        return JsonResponse({'error': 'Informe o nome do parceiro.'}, status=400)

    fields = {
        'nome': nome,
        'tipo': request.POST.get('tipo', ''),
        'telefone': request.POST.get('telefone', ''),
        'email': request.POST.get('email', ''),
        'comissao': request.POST.get('comissao', ''),
        'contato': request.POST.get('contato', ''),
    }
    try:
        created = sheets_repository.create_row('Parceiros', fields)
        return JsonResponse({'success': True, 'id': created.get('id')})
    except Exception as e:
        logger.exception('Falha ao criar parceiro: %s', nome)
        return JsonResponse({'error': str(e)}, status=500)


def parceiro_editar(request, id):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    fields = {}
    for name in ('nome', 'tipo', 'telefone', 'email', 'contato', 'comissao'):
        val = request.POST.get(name)
        if val is not None:
            fields[name] = val

    expected_atualizado_em = request.POST.get('expected_atualizado_em') or None
    try:
        sheets_repository.update_row('Parceiros', id, fields, expected_atualizado_em=expected_atualizado_em)
        return JsonResponse({'success': True})
    except sheets_repository.ConcurrencyError:
        return JsonResponse({'error': 'Este parceiro foi alterado por outra pessoa. Recarregue e tente novamente.'}, status=409)
    except LookupError:
        return JsonResponse({'error': 'Parceiro não encontrado.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao editar parceiro %s', id)
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def parceiro_excluir(request, id):
    try:
        sheets_repository.delete_row('Parceiros', id)
        return JsonResponse({'success': True})
    except LookupError:
        return JsonResponse({'error': 'Parceiro não encontrado.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao excluir parceiro %s', id)
        return JsonResponse({'error': str(e)}, status=500)


def preco_criar(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    tipo = request.POST.get('tipo', '').strip()
    if not tipo:
        return JsonResponse({'error': 'Informe o tipo de certificado.'}, status=400)

    fields = {
        'tipo': tipo,
        'validade': request.POST.get('validade', ''),
        'preco': request.POST.get('preco', ''),
    }
    try:
        created = sheets_repository.create_row('Precos', fields)
        return JsonResponse({'success': True, 'id': created.get('id')})
    except Exception as e:
        logger.exception('Falha ao criar preço: %s', tipo)
        return JsonResponse({'error': str(e)}, status=500)


def preco_editar(request, id):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    fields = {}
    for name in ('tipo', 'validade', 'preco'):
        val = request.POST.get(name)
        if val is not None:
            fields[name] = val

    expected_atualizado_em = request.POST.get('expected_atualizado_em') or None
    try:
        sheets_repository.update_row('Precos', id, fields, expected_atualizado_em=expected_atualizado_em)
        return JsonResponse({'success': True})
    except sheets_repository.ConcurrencyError:
        return JsonResponse({'error': 'Este preço foi alterado por outra pessoa. Recarregue e tente novamente.'}, status=409)
    except LookupError:
        return JsonResponse({'error': 'Preço não encontrado.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao editar preço %s', id)
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def preco_excluir(request, id):
    try:
        sheets_repository.delete_row('Precos', id)
        return JsonResponse({'success': True})
    except LookupError:
        return JsonResponse({'error': 'Preço não encontrado.'}, status=404)
    except Exception as e:
        logger.exception('Falha ao excluir preço %s', id)
        return JsonResponse({'error': str(e)}, status=500)


def app_state_download(request):
    """Gera e retorna um arquivo Excel (.xlsx) com os dados atuais das abas
    Clientes, Parceiros e Precos da planilha do Google Sheets.
    """
    try:
        df_clientes = pd.DataFrame(sheets_repository.list_rows('Clientes'))
        df_parceiros = pd.DataFrame(sheets_repository.list_rows('Parceiros'))
        df_precos = pd.DataFrame(sheets_repository.list_rows('Precos'))

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_clientes.empty:
                df_clientes.to_excel(writer, sheet_name='Clientes', index=False)
            else:
                pd.DataFrame([{'info': 'Nenhum cliente'}]).to_excel(writer, sheet_name='Clientes', index=False)
            if not df_parceiros.empty:
                df_parceiros.to_excel(writer, sheet_name='Parceiros', index=False)
            else:
                pd.DataFrame([{'info': 'Nenhum parceiro'}]).to_excel(writer, sheet_name='Parceiros', index=False)
            if not df_precos.empty:
                df_precos.to_excel(writer, sheet_name='Precos', index=False)
            else:
                pd.DataFrame([{'info': 'Nenhum preco'}]).to_excel(writer, sheet_name='Precos', index=False)

        output.seek(0)
        resp = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = 'attachment; filename="clientes_parceiros_precos.xlsx"'
        return resp
    except Exception as e:
        logger.exception('Falha ao gerar exportação xlsx da planilha')
        return JsonResponse({'error': str(e)}, status=500)


def _validar_arquivo_documento(arquivo):
    """Retorna uma mensagem de erro se o arquivo não passar nas regras de
    upload (extensão/tamanho), ou None se estiver tudo certo. Compartilhado
    entre upload_documento e documentos_cliente para não ter duas regras
    divergentes (ou uma delas esquecida) validando a mesma coisa."""
    extensoes_permitidas = getattr(settings, 'UPLOAD_DOCUMENTO_EXTENSOES_PERMITIDAS', ['.pdf', '.jpg', '.jpeg', '.png'])
    tamanho_maximo_mb = getattr(settings, 'UPLOAD_DOCUMENTO_TAMANHO_MAXIMO_MB', 10)
    tamanho_maximo_bytes = tamanho_maximo_mb * 1024 * 1024
    ext = os.path.splitext(arquivo.name)[1].lower()

    if ext not in extensoes_permitidas:
        return f'Tipo de arquivo não permitido ("{ext}"). Use: {", ".join(extensoes_permitidas)}.'
    if arquivo.size > tamanho_maximo_bytes:
        return f'Arquivo muito grande. O limite é {tamanho_maximo_mb}MB.'
    return None


def upload_documento(request):
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            messages.error(request, 'Selecione um arquivo para envio.')
            return redirect('upload_documento')

        erro = _validar_arquivo_documento(arquivo)
        if erro:
            messages.error(request, erro)
            return redirect('upload_documento')

        cliente_ref = request.POST.get('cliente_ref', '').strip()
        nome_cliente = request.POST.get('nome_cliente', '').strip()
        observacao = request.POST.get('observacao', '').strip()

        DocumentoCliente.objects.create(
            cliente_ref=cliente_ref,
            nome_cliente=nome_cliente,
            observacao=observacao,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tamanho_bytes=arquivo.size,
        )
        messages.success(request, 'Documento enviado com sucesso.')
        return redirect('upload_documento')

    documentos = DocumentoCliente.objects.order_by('-data_envio')[:20]
    return render(request, 'upload_documento.html', {'documentos': documentos})


def documentos_cliente(request, pk):
    registro = sheets_repository.get_row('Clientes', pk)
    if registro is None:
        raise Http404('Cliente não encontrado na planilha.')

    if request.method == 'GET' and request.GET.get('format') == 'json':
        documentos = DocumentoCliente.objects.filter(cliente_ref=pk).order_by('-data_envio')
        return JsonResponse({
            'registro': {
                'id': registro.get('id', ''),
                'cliente': registro.get('cliente', ''),
                'email': registro.get('email', ''),
                'cpf_cnpj': registro.get('cpf_cnpj', ''),
                'tipo_certificado': registro.get('tipo_certificado', ''),
            },
            'documentos': [
                {
                    'id': doc.id,
                    'nome_original': doc.nome_original or os.path.basename(doc.arquivo.name),
                    'tipo_documento': doc.tipo_documento,
                    'tipo_documento_display': doc.get_tipo_documento_display(),
                    'data_envio': doc.data_envio.isoformat() if doc.data_envio else '',
                    'tamanho_bytes': doc.tamanho_bytes,
                    'download_url': f'/planilha/{pk}/documentos/{doc.id}/download/',
                    'delete_url': f'/planilha/{pk}/documentos/{doc.id}/excluir/',
                }
                for doc in documentos
            ],
        })

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        tipo_documento = request.POST.get('tipo_documento', 'outro')

        if not arquivo:
            messages.error(request, 'Selecione um arquivo antes de enviar.')
            return redirect('documentos_cliente', pk=pk)

        erro = _validar_arquivo_documento(arquivo)
        if erro:
            messages.error(request, erro)
            return redirect('documentos_cliente', pk=pk)

        DocumentoCliente.objects.create(
            cliente_ref=pk,
            nome_cliente=registro.get('cliente', ''),
            arquivo=arquivo,
            nome_original=arquivo.name,
            tipo_documento=tipo_documento,
            tamanho_bytes=arquivo.size,
        )
        messages.success(request, f'Documento "{arquivo.name}" enviado com sucesso.')
        return redirect('documentos_cliente', pk=pk)

    documentos = DocumentoCliente.objects.filter(cliente_ref=pk).order_by('-data_envio')
    return render(request, 'documentos_cliente.html', {
        'registro': registro,
        'documentos': documentos,
        'tipos_documento': DocumentoCliente.TIPO_CHOICES,
        'pk': pk,
    })


def download_documento(request, pk, doc_id):
    # cliente_ref=pk exigido aqui evita IDOR: sem essa checagem, doc_id
    # (PK sequencial) sozinho deixaria baixar documento de identidade
    # (RG/CNH, selfie) de qualquer cliente só variando o número na URL.
    documento = get_object_or_404(DocumentoCliente, pk=doc_id, cliente_ref=pk)
    try:
        arquivo = documento.arquivo.open('rb')
    except FileNotFoundError:
        raise Http404('Arquivo não encontrado no armazenamento.')
    return FileResponse(arquivo, as_attachment=True, filename=documento.nome_original or os.path.basename(documento.arquivo.name))


@require_POST
def excluir_documento(request, pk, doc_id):
    documento = get_object_or_404(DocumentoCliente, pk=doc_id, cliente_ref=pk)
    documento.arquivo.delete(save=False)
    documento.delete()
    messages.success(request, 'Documento removido.')
    return redirect('documentos_cliente', pk=pk)


@csrf_exempt
def criar_pagamento_pix(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    is_json = 'application/json' in (request.content_type or '')
    try:
        payload = json.loads(request.body.decode('utf-8')) if is_json else request.POST
    except Exception:
        return HttpResponseBadRequest('JSON inválido')

    try:
        valor = float(payload.get('valor') or 0)
    except Exception:
        valor = 0

    email_cliente = (payload.get('email_cliente') or '').strip()
    descricao = (payload.get('descricao_produto') or payload.get('descricao') or 'Certificado Digital').strip()
    cliente_ref = (payload.get('cliente_ref') or '').strip()
    nome_cliente = (payload.get('nome_cliente') or '').strip()

    if valor <= 0:
        return JsonResponse({'error': 'Valor inválido.'}, status=400)
    if not email_cliente:
        return JsonResponse({'error': 'email_cliente é obrigatório.'}, status=400)

    try:
        payment = gerar_pagamento_mercado_pago(
            valor=valor,
            email_cliente=email_cliente,
            descricao_produto=descricao,
            metodo='pix',
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    gateway_payment_id = str(payment.get('id', ''))
    status = payment.get('status', PagamentoCliente.STATUS_PENDING)
    transaction_data = ((payment.get('point_of_interaction') or {}).get('transaction_data') or {})

    registro = PagamentoCliente.objects.create(
        cliente_ref=cliente_ref,
        nome_cliente=nome_cliente,
        email_cliente=email_cliente,
        metodo=PagamentoCliente.METODO_PIX,
        valor=valor,
        descricao=descricao,
        gateway_payment_id=gateway_payment_id or None,
        status=status if status in dict(PagamentoCliente.STATUS_CHOICES) else PagamentoCliente.STATUS_PENDING,
        qr_code_base64=transaction_data.get('qr_code_base64', ''),
        qr_code_copia_cola=transaction_data.get('qr_code', ''),
        raw_payload=payment,
    )

    return JsonResponse({
        'pagamento_id': registro.id,
        'gateway_payment_id': registro.gateway_payment_id,
        'status': registro.status,
        'qr_code_base64': registro.qr_code_base64,
        'qr_code_copia_cola': registro.qr_code_copia_cola,
    })


def _marcar_pagamento_aprovado(pagamento):
    # Atualiza estado JSON usado no dashboard
    state = AppState.objects.filter(key='main').first()
    if state and isinstance(state.data, dict):
        data = state.data
        clientes = data.get('clientes', []) or []
        alterado = False
        for cliente in clientes:
            if str(cliente.get('id', '')).strip() == str(pagamento.cliente_ref).strip():
                cliente['pago'] = True
                alterado = True
                break
        if alterado:
            data['clientes'] = clientes
            state.data = data
            state.save()

    # Atualiza registro da planilha quando o id estiver vinculado ao registro importado
    planilha_pk = (pagamento.cliente_ref or '').strip()
    if planilha_pk:
        try:
            registro_atual = sheets_repository.get_row('Clientes', planilha_pk)
            expected_atualizado_em = registro_atual.get('atualizado_em') if registro_atual else None
            sheets_repository.update_row(
                'Clientes', planilha_pk, {'pago_venda': 'Sim'},
                expected_atualizado_em=expected_atualizado_em,
            )
        except LookupError:
            pass
        except Exception:
            # Não interrompe o webhook caso a planilha esteja indisponível, mas
            # isso precisa ficar visível no log para investigação manual.
            logger.exception(
                'Pagamento %s aprovado, mas falhou ao marcar o registro %s como pago na planilha',
                pagamento.pk, planilha_pk,
            )


@csrf_exempt
def webhook_mercado_pago(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'invalid method'}, status=405)

    try:
        topic = request.GET.get('topic') or request.GET.get('type')
        payment_id = request.GET.get('id')

        payload = {}
        if request.body:
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except Exception:
                payload = {}

        if not payment_id:
            if payload.get('type') == 'payment' or payload.get('action') == 'payment.updated':
                payment_id = str((payload.get('data') or {}).get('id') or '')
                topic = topic or 'payment'

        if topic != 'payment' or not payment_id:
            return JsonResponse({'status': 'ignored'}, status=200)

        payment_info = consultar_pagamento_mercado_pago(payment_id)
        status = payment_info.get('status', '')

        pagamento = PagamentoCliente.objects.filter(gateway_payment_id=str(payment_id)).first()
        if pagamento:
            pagamento.status = status if status in dict(PagamentoCliente.STATUS_CHOICES) else pagamento.status
            pagamento.raw_payload = payment_info
            pagamento.save(update_fields=['status', 'raw_payload', 'data_atualizacao'])
            if pagamento.status == PagamentoCliente.STATUS_APPROVED:
                _marcar_pagamento_aprovado(pagamento)

        return JsonResponse({'status': 'success'}, status=200)
    except Exception as e:
        logger.exception('Falha ao processar webhook do Mercado Pago')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

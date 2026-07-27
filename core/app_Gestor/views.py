from datetime import date
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
from django.db.models import Sum, Q

logger = logging.getLogger(__name__)

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
    'origem': 'Origem',
    'status': 'Status',
    'obs': 'Observações',
    'tipocert': 'Tipo de Certificado',
    'dataemissao': 'Data de Emissão',
    'datavencimento': 'Data de Vencimento',
    'valorcobrado': 'Valor Cobrado',
    'formapag': 'Forma de Pagamento',
    'pago': 'Pago',
    'tipovalidacao': 'Tipo de Validação',
    'datavideo': 'Data do Vídeo',
    'solutilink': 'Link Soluti',
    'solutichave': 'Chave Soluti',
    'kitdestinatario': 'Destinatário do Kit',
    'kitenviado': 'Kit Enviado',
    'triagem': 'Triagem',
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


CLIENTES_COLUMNS = [
    {'label':'Data da Venda','field':'data_venda','class':'col-data-venda'},
    {'label':'Contador/Parceiro','field':'contador_parceiro','class':'col-contador-parceiro'},
    {'label':'Contador/Contabilidade','field':'contador_contabilidade','class':'col-contador-contabilidade'},
    {'label':'Telefone','field':'telefone1','class':'col-telefone1'},
    {'label':'Cliente','field':'cliente','class':'col-cliente'},
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
_DECIMAL_FIELDS = {'valor_venda', 'percentual_comissao', 'valor_comissao', 'custo_certificado', 'valor_liquido'}
_BOOL_FIELDS = {'pago_comissao', 'pago_venda'}


def _format_sheet_cell_value(field, raw):
    if raw is None or raw == '':
        return '—'
    if field in _DATE_FIELDS:
        parsed = parse_date(raw)
        return parsed.strftime('%d/%m/%Y') if parsed else raw
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
        cells = [
            {
                'class': col['class'],
                'value': _format_sheet_cell_value(col['field'], row.get(col['field'], '')),
                'default_visible': col['default_visible'],
            }
            for col in cols
        ]
        rows.append({'id': row.get('id', ''), 'cells': cells})
    return cols, rows


def _build_alert_payload():
    hoje = date.today()
    renovacoes_urgentes = []
    renovacoes_normais = []
    pagamentos_urgentes = []
    pagamentos_normais = []

    rows = sheets_repository.list_rows('Clientes')

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
        'renovacoes_urgentes': len(renovacoes_urgentes),
        'renovacoes_normais': len(renovacoes_normais),
        'pagamentos_urgentes': len(pagamentos_urgentes),
        'pagamentos_normais': len(pagamentos_normais),
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
        })
    return precos


def alertas_dashboard(request):
    return JsonResponse(_build_alert_payload())


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

        # --- CORREÇÃO PRECISA: Soma o faturamento diretamente do banco onde pago_venda é True ---
        from django.db.models import Sum

        faturamento_db = ( PagamentoCliente.objects.filter(status=PagamentoCliente.STATUS_APPROVED).aggregate(total=Sum("valor"))["total"] or 0)
        faturamento_total = float(faturamento_db)

        import json
        context['faturamento_recebido_json'] = json.dumps(faturamento_total, default=str)
        # ----------------------------------------------------------------------------------------

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
            alertas = _build_alert_payload()
        except Exception:
            logger.exception('Falha ao montar alertas a partir da planilha do Google Sheets')
            alertas = {
                'counts': {},
                'renovacoes': {'urgentes': [], 'normais': []},
                'pagamentos': {'urgentes': [], 'normais': []},
            }

        try:
            context['initial_clientes_json'] = json.dumps(initial_clientes, default=str)
        except Exception:
            context['initial_clientes_json'] = '[]'
        try:
            context['initial_parceiros_json'] = json.dumps(initial_parceiros, default=str)
        except Exception:
            context['initial_parceiros_json'] = '[]'
        try:
            context['initial_precos_json'] = json.dumps(initial_precos, default=str)
        except Exception:
            context['initial_precos_json'] = '[]'
        try:
            context['initial_alerts_json'] = json.dumps(alertas, default=str)
        except Exception:
            context['initial_alerts_json'] = '{}'
        try:
            context['alert_counts_json'] = json.dumps(alertas.get('counts', {}), default=str)
        except Exception:
            context['alert_counts_json'] = '{}'
            
        return context
def editar_google_row(request, pk):
    registro = sheets_repository.get_row('Clientes', pk)
    if registro is None:
        raise Http404('Registro não encontrado na planilha.')

    if request.method == 'POST':
        fields = {}

        cliente = request.POST.get('cliente')
        if cliente:
            fields['cliente'] = cliente

        email = request.POST.get('email')
        if email:
            fields['email'] = email

        valor_comissao = request.POST.get('valor_comissao')
        if valor_comissao:
            try:
                fields['valor_comissao'] = str(float(valor_comissao.replace(',', '.')))
            except ValueError:
                pass

        fields['pago_comissao'] = 'Sim' if request.POST.get('pago_comissao') in ['Sim', 'on', 'true', 'True'] else 'Não'

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

    registro_view = {**registro, 'pago_comissao': bool_from(registro.get('pago_comissao'))}
    return render(request, 'google_edit.html', {'registro': registro_view})


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

    try:
        sheets_repository.update_row('Parceiros', id, fields)
        return JsonResponse({'success': True})
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

    try:
        sheets_repository.update_row('Precos', id, fields)
        return JsonResponse({'success': True})
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


@csrf_exempt
def app_state_download(request):
    """Gera e retorna um arquivo Excel (.xlsx) com o estado enviado no body
    ou com o estado salvo no banco (key='main') quando chamado via GET.
    """
    try:
        if request.method == 'POST':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            state = AppState.objects.filter(key='main').first()
            payload = state.data if state else {'clientes': [], 'parceiros': [], 'precos': []}

        clientes = payload.get('clientes', []) or []
        parceiros = payload.get('parceiros', []) or []
        precos = payload.get('precos', []) or []

        df_clientes = pd.DataFrame(clientes)
        df_parceiros = pd.DataFrame(parceiros)
        df_precos = pd.DataFrame(precos)

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
        resp['Content-Disposition'] = 'attachment; filename="estado_clientes_parceiros.xlsx"'
        return resp
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def upload_documento(request):
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            messages.error(request, 'Selecione um arquivo para envio.')
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
                    'download_url': f'/documentos/{doc.id}/download/',
                    'delete_url': f'/documentos/{doc.id}/excluir/',
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

        extensoes_permitidas = getattr(settings, 'UPLOAD_DOCUMENTO_EXTENSOES_PERMITIDAS', ['.pdf', '.jpg', '.jpeg', '.png'])
        tamanho_maximo_mb = getattr(settings, 'UPLOAD_DOCUMENTO_TAMANHO_MAXIMO_MB', 10)
        tamanho_maximo_bytes = tamanho_maximo_mb * 1024 * 1024
        ext = os.path.splitext(arquivo.name)[1].lower()

        if ext not in extensoes_permitidas:
            messages.error(request, f'Tipo de arquivo não permitido ("{ext}"). Use: {", ".join(extensoes_permitidas)}.')
            return redirect('documentos_cliente', pk=pk)

        if arquivo.size > tamanho_maximo_bytes:
            messages.error(request, f'Arquivo muito grande. O limite é {tamanho_maximo_mb}MB.')
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
    })


def download_documento(request, doc_id):
    documento = get_object_or_404(DocumentoCliente, pk=doc_id)
    try:
        arquivo = documento.arquivo.open('rb')
    except FileNotFoundError:
        raise Http404('Arquivo não encontrado no armazenamento.')
    return FileResponse(arquivo, as_attachment=True, filename=documento.nome_original or os.path.basename(documento.arquivo.name))


@require_POST
def excluir_documento(request, doc_id):
    documento = get_object_or_404(DocumentoCliente, pk=doc_id)
    pk = documento.cliente_ref or documento.registro_id
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
            sheets_repository.update_row('Clientes', planilha_pk, {'pago_venda': 'Sim'})
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

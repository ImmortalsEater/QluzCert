from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.conf import settings
import json
import os
from core.app.services import importar_planilha_do_drive
from .services import save_state_to_drive, gerar_pagamento_mercado_pago, consultar_pagamento_mercado_pago
from core.app.services import salvar_no_drive_desde_db
from .models import Colaborador, AppState, DocumentoCliente, PagamentoCliente
from core.app.models import PlanilhaRegistro
import io
import pandas as pd
from django.http import HttpResponse


DEFAULT_GOOGLE_COLUMNS = [
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
    {'label':'Importado em','field':'data_registro','class':'col-data-registro'},
]


def _format_google_cell_value(val):
    from datetime import date, datetime

    if isinstance(val, float) or hasattr(val, 'quantize'):
        try:
            return f"{float(val):.2f}".replace('.', ',')
        except Exception:
            return val
    if isinstance(val, (date, datetime)):
        try:
            return val.strftime('%d/%m/%Y')
        except Exception:
            return val
    if isinstance(val, bool):
        return 'Sim' if val else 'Não'
    return val


def _load_sheet_snapshot():
    state = AppState.objects.filter(key='sheet_sync').first()
    if not state or not isinstance(state.data, dict):
        return None
    columns = state.data.get('columns') or []
    rows = state.data.get('rows') or []
    if not columns or not rows:
        return None
    return {'columns': columns, 'rows': rows}


def _build_dashboard_from_db():
    cols = DEFAULT_GOOGLE_COLUMNS
    rows = []
    for r in PlanilhaRegistro.objects.order_by('-data_registro'):
        cells = []
        for col in cols:
            val = getattr(r, col['field'], '')
            cells.append({'class': col['class'], 'value': _format_google_cell_value(val)})
        rows.append({'id': r.id, 'cells': cells, 'data_registro': r.data_registro})
    return cols, rows


def _build_dashboard_from_snapshot(snapshot):
    return snapshot['columns'], snapshot['rows']


def _build_alert_payload():
    hoje = date.today()
    renovacoes_urgentes = []
    renovacoes_normais = []
    pagamentos_urgentes = []
    pagamentos_normais = []

    def _base_payload(registro, dias_restantes):
        return {
            'id': f'planilha-{registro.pk}',
            'planilha_pk': registro.pk,
            'nome': registro.cliente or registro.contador_parceiro or registro.email or f'Registro {registro.pk}',
            'email': registro.email or '',
            'telefone': registro.telefone1 or registro.telefone2 or '',
            'parceiro': registro.contador_parceiro or '',
            'tipoCert': registro.tipo_certificado or '',
            'dataVencimento': registro.data_vencimento.isoformat() if registro.data_vencimento else '',
            'dias': dias_restantes,
            'valorCobrado': float(registro.valor_venda) if registro.valor_venda is not None else 0,
            'pago': bool(registro.pago_venda or registro.pago_comissao),
        }

    for registro in PlanilhaRegistro.objects.order_by('-data_registro'):
        if not registro.data_vencimento:
            continue

        dias_restantes = (registro.data_vencimento - hoje).days
        base = _base_payload(registro, dias_restantes)
        base['statusLabel'] = f"Vencido há {abs(dias_restantes)} dias" if dias_restantes < 0 else f"Vence em {dias_restantes} dias"

        if dias_restantes <= 30:
            renovacoes_urgentes.append({**base, 'categoria': 'renovacao'})
        elif dias_restantes <= 90:
            renovacoes_normais.append({**base, 'categoria': 'renovacao'})

        if not registro.pago_venda:
            pagamento_base = {**base, 'categoria': 'pagamento', 'tipoPagamento': 'Venda'}
            if dias_restantes <= 0:
                pagamentos_urgentes.append(pagamento_base)
            elif dias_restantes <= 30:
                pagamentos_normais.append(pagamento_base)

        if not registro.pago_comissao:
            pagamento_base = {**base, 'categoria': 'pagamento', 'tipoPagamento': 'Comissão'}
            if dias_restantes <= 0:
                pagamentos_urgentes.append(pagamento_base)
            elif dias_restantes <= 30:
                pagamentos_normais.append(pagamento_base)

    counts = {
        'total_registros': PlanilhaRegistro.objects.count(),
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
    parceiros_dict = {}

    for r in PlanilhaRegistro.objects.filter(contador_parceiro__gt=''):
        key = (r.contador_parceiro or '').strip()
        if not key or key in parceiros_dict:
            continue
        parceiros_dict[key] = {
            'id': key,
            'nome': r.contador_parceiro,
            'tipo': 'Parceiro',
            'comissao': float(r.percentual_comissao) if r.percentual_comissao is not None else None,
            'contato': r.telefone1 or '',
            'email': r.email or '',
        }

    if parceiros_dict:
        return list(parceiros_dict.values())

    snapshot = _load_sheet_snapshot()
    if not snapshot:
        return []

    columns = snapshot.get('columns') or []
    rows = snapshot.get('rows') or []

    def _match_partner_column(label, field):
        text = f"{label} {field}".lower()
        return any(token in text for token in ['contador', 'parceiro', 'escritorio', 'escritório'])

    partner_index = None
    name_index = None
    email_index = None
    phone_index = None
    cpf_index = None
    commission_index = None

    for index, col in enumerate(columns):
        label = str(col.get('label', ''))
        field = str(col.get('field', ''))
        text = f"{label} {field}".lower()
        if partner_index is None and _match_partner_column(label, field):
            partner_index = index
        if name_index is None and any(token in text for token in ['cliente', 'nome']):
            name_index = index
        if email_index is None and 'email' in text:
            email_index = index
        if phone_index is None and any(token in text for token in ['telefone', 'celular', 'whatsapp']):
            phone_index = index
        if cpf_index is None and any(token in text for token in ['cpf', 'cnpj']):
            cpf_index = index
        if commission_index is None and 'comissao' in text:
            commission_index = index

    for row in rows:
        cells = row.get('cells') or []
        if partner_index is None or partner_index >= len(cells):
            continue
        nome = str(cells[partner_index].get('value', '')).strip()
        if not nome:
            continue
        if nome in parceiros_dict:
            continue

        parceiros_dict[nome] = {
            'id': nome,
            'nome': nome,
            'tipo': 'Parceiro',
            'comissao': None,
            'contato': str(cells[phone_index].get('value', '')).strip() if phone_index is not None and phone_index < len(cells) else '',
            'email': str(cells[email_index].get('value', '')).strip() if email_index is not None and email_index < len(cells) else '',
        }

        if commission_index is not None and commission_index < len(cells):
            commission_value = cells[commission_index].get('value', '')
            try:
                parceiros_dict[nome]['comissao'] = float(str(commission_value).replace('.', '').replace(',', '.'))
            except Exception:
                parceiros_dict[nome]['comissao'] = None

        if name_index is not None and name_index < len(cells) and not parceiros_dict[nome]['contato']:
            parceiros_dict[nome]['contato'] = str(cells[name_index].get('value', '')).strip()

        if cpf_index is not None and cpf_index < len(cells):
            parceiros_dict[nome]['cpf_cnpj'] = str(cells[cpf_index].get('value', '')).strip()

    return list(parceiros_dict.values())


def sincronizar_drive(request):
    """
    Sincroniza parceiros e dados da planilha do Google Drive.
    O ID do arquivo fica na URL: https://docs.google.com/spreadsheets/d/ID_AQUI/edit
    """
    ID_DA_PLANILHA_DO_CLIENTE = 'https://docs.google.com/spreadsheets/d/1L-MX27Y6iwCOyd0e4FqLxZJyRFCpHIP6arYYeFIHLME/edit?gid=1382791784#gid=1382791784'

    try:
        with transaction.atomic():
            PlanilhaRegistro.objects.all().delete()
            total_importado = importar_planilha_do_drive(ID_DA_PLANILHA_DO_CLIENTE)
        messages.success(request, f"Sucesso! Banco limpo e {total_importado} registros sincronizados da planilha.")
    except Exception as e:
        messages.error(request, f"Erro ao acessar o Google Drive: {str(e)}")

    return redirect('dashboard')


def alertas_dashboard(request):
    return JsonResponse(_build_alert_payload())


@method_decorator(ensure_csrf_cookie, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard.html'  # Certifique-se de que o caminho está correto conforme seus TEMPLATES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = _load_sheet_snapshot()
        if snapshot:
            context['google_columns'], context['google_rows'] = _build_dashboard_from_snapshot(snapshot)
        else:
            context['google_columns'], context['google_rows'] = _build_dashboard_from_db()
        # Fornece clientes iniciais a partir da planilha importada; se não houver dados,
        # mantém o estado salvo localmente.
        try:
            initial_clientes = []
            for r in PlanilhaRegistro.objects.order_by('-data_registro'):
                status = 'Novo Lead'
                if str(r.certificado_feito).strip():
                    status = 'Emitido'
                elif r.pago_venda or r.pago_comissao:
                    status = 'Aguardando Pagamento'

                def fmt_date(value):
                    if not value:
                        return ''
                    try:
                        return value.isoformat()
                    except Exception:
                        return str(value)

                initial_clientes.append({
                    'id': f'planilha-{r.pk}',
                    'nome': r.cliente or r.contador_parceiro or r.email or 'Sem nome',
                    'cpfCnpj': r.cpf_cnpj or '',
                    'telefone': r.telefone1 or r.telefone2 or '',
                    'email': r.email or '',
                    'parceiroId': (r.contador_parceiro or '').strip() or None,
                    'origem': 'Planilha do Drive',
                    'status': status,
                    'obs': '',
                    'tipoCert': r.tipo_certificado or '',
                    'dataEmissao': fmt_date(r.data_venda),
                    'dataVencimento': fmt_date(r.data_vencimento),
                    'valorCobrado': float(r.valor_venda) if r.valor_venda is not None else 0,
                    'formaPag': r.forma_pagamento or '',
                    'pago': bool(r.pago_venda or r.pago_comissao),
                    'tipoValidacao': '',
                    'criadoEm': r.data_registro.isoformat() if r.data_registro else '',
                })
        except Exception:
            try:
                state = AppState.objects.filter(key='main').first()
                initial_clientes = state.data.get('clientes', []) if state and isinstance(state.data, dict) else []
            except Exception:
                initial_clientes = []

        try:
            initial_parceiros = _build_parceiros_from_source()
        except Exception:
            initial_parceiros = []

        alertas = _build_alert_payload()

        import json
        try:
            context['initial_clientes_json'] = json.dumps(initial_clientes, default=str)
        except Exception:
            context['initial_clientes_json'] = '[]'
        try:
            context['initial_parceiros_json'] = json.dumps(initial_parceiros, default=str)
        except Exception:
            context['initial_parceiros_json'] = '[]'
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
    registro = get_object_or_404(PlanilhaRegistro, pk=pk)
    if request.method == 'POST':
        registro.cliente = request.POST.get('cliente', registro.cliente) or registro.cliente
        registro.email = request.POST.get('email', registro.email) or registro.email
        # campos numéricos
        def parse_decimal_field(name, current):
            val = request.POST.get(name)
            if val is None:
                return current
            try:
                return float(val.replace(',', '.'))
            except Exception:
                return current

        registro.valor_venda = parse_decimal_field('valor_venda', registro.valor_venda)
        registro.percentual_comissao = parse_decimal_field('percentual_comissao', registro.percentual_comissao)
        registro.valor_comissao = parse_decimal_field('valor_comissao', registro.valor_comissao)

        registro.pago_comissao = request.POST.get('pago_comissao') in ['Sim', 'on', 'true', 'True']
        registro.pago_venda = request.POST.get('pago_venda') in ['Sim', 'on', 'true', 'True']

        registro.save()

        # Reescreve a planilha no Drive com os dados atualizados
        SPREADSHEET_ID = '1L-MX27Y6iwCOyd0e4FqLxZJyRFCpHIP6arYYeFIHLME'
        try:
            salvar_no_drive_desde_db(SPREADSHEET_ID)
            messages.success(request, 'Registro atualizado e planilha no Drive sobrescrita com sucesso.')
        except Exception as e:
            messages.warning(request, f'Registro salvo localmente, falha ao atualizar Drive: {str(e)}')

        return redirect('dashboard')

    return render(request, 'google_edit.html', {'registro': registro})


@csrf_exempt
def app_state(request):
    if request.method == 'GET':
        state = AppState.objects.filter(key='main').first()
        data = state.data if state else {'clientes': [], 'parceiros': [], 'precos': []}
        return JsonResponse(data)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            return HttpResponseBadRequest('JSON inválido')

        state, _ = AppState.objects.get_or_create(key='main')
        state.data = payload
        state.save()
        return JsonResponse({'saved': True})

    return HttpResponseBadRequest('Método não permitido')


@csrf_exempt
def app_state_drive(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método não permitido')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('JSON inválido')

    state, _ = AppState.objects.get_or_create(key='main')
    state.data = payload
    state.save()

    SPREADSHEET_ID = '1L-MX27Y6iwCOyd0e4FqLxZJyRFCpHIP6arYYeFIHLME'
    success = False
    try:
        save_state_to_drive(payload, SPREADSHEET_ID)
        success = True
    except Exception as e:
        messages.warning(request, f'Falha ao salvar na nuvem: {str(e)}')

    return JsonResponse({'saved': True, 'drive': success})


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
    registro = get_object_or_404(PlanilhaRegistro, pk=pk)

    if request.method == 'GET' and request.GET.get('format') == 'json':
        documentos = registro.documentos.order_by('-data_envio')
        return JsonResponse({
            'registro': {
                'id': registro.id,
                'cliente': registro.cliente,
                'email': registro.email,
                'cpf_cnpj': registro.cpf_cnpj,
                'tipo_certificado': registro.tipo_certificado,
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
            registro=registro,
            arquivo=arquivo,
            nome_original=arquivo.name,
            tipo_documento=tipo_documento,
            tamanho_bytes=arquivo.size,
        )
        messages.success(request, f'Documento "{arquivo.name}" enviado com sucesso.')
        return redirect('documentos_cliente', pk=pk)

    documentos = registro.documentos.all()
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
    pk = documento.registro_id
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


def _extrair_planilha_pk(cliente_ref):
    # Exemplo esperado: planilha-123
    if not cliente_ref or not cliente_ref.startswith('planilha-'):
        return None
    try:
        return int(cliente_ref.split('-', 1)[1])
    except Exception:
        return None


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
    planilha_pk = _extrair_planilha_pk(pagamento.cliente_ref)
    if planilha_pk:
        registro = PlanilhaRegistro.objects.filter(pk=planilha_pk).first()
        if registro:
            registro.pago_venda = True
            registro.save(update_fields=['pago_venda'])
            spreadsheet_id = '1L-MX27Y6iwCOyd0e4FqLxZJyRFCpHIP6arYYeFIHLME'
            try:
                salvar_no_drive_desde_db(spreadsheet_id)
            except Exception:
                # Não interrompe o webhook caso o Drive esteja indisponível.
                pass


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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class ParceirosView(TemplateView):
    template_name = 'parceiros.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import date, datetime

        parceiros_source = _build_parceiros_from_source()
        parceiros_dict = {}
        for parceiro in parceiros_source:
            key = parceiro.get('nome') or parceiro.get('contador_parceiro')
            if not key or key in parceiros_dict:
                continue
            parceiros_dict[key] = {
                'contador_parceiro': parceiro.get('nome') or parceiro.get('contador_parceiro') or '',
                'cpf_cnpj': parceiro.get('cpf_cnpj', ''),
                'percentual_comissao': parceiro.get('comissao', None),
                'telefone1': parceiro.get('contato', ''),
                'email': parceiro.get('email', ''),
            }
        
        # Monta estrutura de colunas e linhas
        context['columns'] = [
            {'label': 'Contador Parceiro', 'field': 'contador_parceiro', 'class': 'col-contador'},
            {'label': 'CPF/CNPJ', 'field': 'cpf_cnpj', 'class': 'col-cpf'},
            {'label': 'Percentual de Comissão (%)', 'field': 'percentual_comissao', 'class': 'col-percentual'},
            {'label': 'Telefone', 'field': 'telefone1', 'class': 'col-telefone'},
            {'label': 'Email', 'field': 'email', 'class': 'col-email'},
        ]
        
        rows = []
        for parceiro in parceiros_dict.values():
            cells = []
            for col in context['columns']:
                field = col['field']
                val = parceiro.get(field, '')
                
                # Formata decimais
                if isinstance(val, float) or (hasattr(val, 'quantize')):
                    try:
                        val = f"{float(val):.2f}".replace('.', ',')
                    except Exception:
                        pass
                
                cells.append({'class': col['class'], 'value': val})
            
            rows.append({'cells': cells})
        
        context['parceiros_rows'] = rows
        return context

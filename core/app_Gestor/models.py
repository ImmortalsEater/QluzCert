import os
import uuid

from django.db import models


def caminho_documento_cliente(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    nome_unico = f"{uuid.uuid4().hex}{ext}"
    registro_part = instance.registro_id or 'sem-registro'
    return os.path.join('documentos_clientes', str(registro_part), nome_unico)


class Colaborador(models.Model):
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    valor_comissao = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    comissao_paga = models.BooleanField(default=False)
    data_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class AppState(models.Model):
    key = models.CharField(max_length=50, unique=True)
    data = models.JSONField(default=dict)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AppState({self.key})"


class DocumentoCliente(models.Model):
    TIPO_CHOICES = [
        ('rg_cnh', 'RG/CNH'),
        ('contrato_social', 'Contrato Social'),
        ('comprovante_residencia', 'Comprovante de Residência'),
        ('foto_selfie', 'Foto/Selfie'),
        ('outro', 'Outro'),
    ]

    cliente_ref = models.CharField(max_length=128, blank=True, db_index=True)
    nome_cliente = models.CharField(max_length=255, blank=True)
    registro = models.ForeignKey('app.PlanilhaRegistro', null=True, blank=True, on_delete=models.CASCADE, related_name='documentos')
    arquivo = models.FileField(upload_to=caminho_documento_cliente)
    nome_original = models.CharField(max_length=255, blank=True, default='')
    tipo_documento = models.CharField(max_length=32, choices=TIPO_CHOICES, blank=True, default='outro')
    tamanho_bytes = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True)
    data_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        base = self.nome_original or self.nome_cliente or self.cliente_ref or 'Sem cliente'
        return f"Documento({base})"


class PagamentoCliente(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_APPROVED, 'Aprovado'),
        (STATUS_REJECTED, 'Recusado'),
        (STATUS_CANCELLED, 'Cancelado'),
    ]

    METODO_PIX = 'pix'
    METODO_BOLETO = 'bolbradesco'
    METODO_CHOICES = [
        (METODO_PIX, 'Pix'),
        (METODO_BOLETO, 'Boleto'),
    ]

    cliente_ref = models.CharField(max_length=128, blank=True, db_index=True)
    nome_cliente = models.CharField(max_length=255, blank=True)
    email_cliente = models.EmailField(blank=True)
    metodo = models.CharField(max_length=32, choices=METODO_CHOICES, default=METODO_PIX)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.CharField(max_length=255)
    gateway = models.CharField(max_length=32, default='mercadopago')
    gateway_payment_id = models.CharField(max_length=64, blank=True, null=True, unique=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    qr_code_base64 = models.TextField(blank=True)
    qr_code_copia_cola = models.TextField(blank=True)
    boleto_url = models.URLField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pagamento({self.gateway_payment_id or self.pk}, {self.status})"

"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from core.app_Gestor.views import DashboardView, alertas_dashboard, sincronizar_drive, editar_google_row, ParceirosView, app_state, app_state_drive, app_state_download, upload_documento, criar_pagamento_pix, webhook_mercado_pago, documentos_cliente, download_documento, excluir_documento

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardView.as_view(), name='dashboard'),
    path('parceiros/', ParceirosView.as_view(), name='parceiros'),
    path('sincronizar/', sincronizar_drive, name='sincronizar_drive'),
    path('alertas/', alertas_dashboard, name='alertas_dashboard'),
    path('planilha/editar/<int:pk>/', editar_google_row, name='editar_google_row'),
    path('planilha/<int:pk>/documentos/', documentos_cliente, name='documentos_cliente'),
    path('documentos/<int:doc_id>/download/', download_documento, name='download_documento'),
    path('documentos/<int:doc_id>/excluir/', excluir_documento, name='excluir_documento'),
    path('app_state/', app_state, name='app_state'),
    path('app_state_drive/', app_state_drive, name='app_state_drive'),
    path('app_state_download/', app_state_download, name='app_state_download'),
    path('documentos/upload/', upload_documento, name='upload_documento'),
    path('pagamentos/pix/', criar_pagamento_pix, name='criar_pagamento_pix'),
    path('webhook/mercadopago/', webhook_mercado_pago, name='webhook_mercado_pago'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

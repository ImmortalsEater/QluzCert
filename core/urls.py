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
from django.contrib.auth import views as auth_views
from django.urls import path

from core.app_Gestor.views import DashboardView, LoginPreviewView, CadastroPreviewView, RecuperarSenhaPreviewView, alertas_dashboard, atualizar_planilha, atualizar_status_cliente, atualizar_detalhe_cliente, verificar_registro_existe, editar_google_row, criar_google_row, cliente_excluir, contatos_cliente_registro, parceiro_criar, parceiro_editar, parceiro_excluir, preco_criar, preco_editar, preco_excluir, app_state_download, upload_documento, criar_pagamento_pix, webhook_mercado_pago, documentos_cliente, download_documento, excluir_documento

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', DashboardView.as_view(), name='dashboard'),
    path('preview/login/', LoginPreviewView.as_view(), name='login_preview'),
    path('preview/cadastro/', CadastroPreviewView.as_view(), name='cadastro_preview'),
    path('preview/recuperar-senha/', RecuperarSenhaPreviewView.as_view(), name='recuperar_senha_preview'),
    path('alertas/', alertas_dashboard, name='alertas_dashboard'),
    path('atualizar-planilha/', atualizar_planilha, name='atualizar_planilha'),
    path('planilha/criar/', criar_google_row, name='criar_google_row'),
    path('planilha/editar/<str:pk>/', editar_google_row, name='editar_google_row'),
    path('planilha/<str:pk>/status/', atualizar_status_cliente, name='atualizar_status_cliente'),
    path('planilha/<str:pk>/detalhe/', atualizar_detalhe_cliente, name='atualizar_detalhe_cliente'),
    path('planilha/<str:pk>/existe/', verificar_registro_existe, name='verificar_registro_existe'),
    path('planilha/<str:pk>/excluir/', cliente_excluir, name='cliente_excluir'),
    path('planilha/<str:pk>/contatos/', contatos_cliente_registro, name='contatos_cliente_registro'),
    path('planilha/<str:pk>/documentos/', documentos_cliente, name='documentos_cliente'),
    path('documentos/upload/', upload_documento, name='upload_documento'),
    path('planilha/<str:pk>/documentos/<int:doc_id>/download/', download_documento, name='download_documento'),
    path('planilha/<str:pk>/documentos/<int:doc_id>/excluir/', excluir_documento, name='excluir_documento'),
    path('parceiro/criar/', parceiro_criar, name='parceiro_criar'),
    path('parceiro/editar/<str:id>/', parceiro_editar, name='parceiro_editar'),
    path('parceiro/excluir/<str:id>/', parceiro_excluir, name='parceiro_excluir'),
    path('preco/criar/', preco_criar, name='preco_criar'),
    path('preco/editar/<str:id>/', preco_editar, name='preco_editar'),
    path('preco/excluir/<str:id>/', preco_excluir, name='preco_excluir'),
    path('app_state_download/', app_state_download, name='app_state_download'),
]

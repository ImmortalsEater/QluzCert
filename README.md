# QCert Manager

Painel interno (Django + JS puro) para gestão de vendas de certificados digitais (e-CPF/e-CNPJ): clientes, parceiros, tabela de preços, renovações e pagamentos, com o Google Sheets como fonte de verdade ao vivo (não um sync em lote) para Clientes, Parceiros e Preços.

## Estrutura do projeto

- `core.app_Gestor` — app ativo, roteado em `core/urls.py`. Toda view, template e arquivo estático novo deve entrar aqui.
  - `sheets_repository.py` — única camada de acesso à planilha (`list_rows`/`get_row`/`create_row`/`update_row`/`delete_row`), com cache de leitura em memória de curto TTL e controle de concorrência otimista via `atualizado_em`. Toda leitura/escrita de Clientes, Parceiros e Preços passa por aqui.
  - `parsing.py` — parsers compartilhados (`parse_date`, `parse_decimal`, `bool_from`) usados para interpretar os valores de célula (sempre texto) vindos da planilha.
- `core.app` — não tem nenhuma URL própria. Existe só para manter os modelos `PlanilhaRegistro`/`Colaborador`, que ficam sem uso ativo hoje (preservados apenas para uma eventual migração futura para um servidor com banco compartilhado). Não adicione views, templates ou estáticos novos aqui.
- `preview_login/` — mockups estáticos (HTML/CSS) de login, cadastro e recuperação de senha, mantidos aqui só como referência de design. As páginas realmente servidas pelo Django (rotas `/preview/login/`, `/preview/cadastro/`, `/preview/recuperar-senha/`) usam os templates equivalentes em `core/app_Gestor/templates/`, não estes arquivos.

A planilha do Google (`GOOGLE_SHEET_ID`) tem três abas geridas pelo app — **Clientes**, **Parceiros**, **Precos** — cada uma com colunas `id`/`atualizado_em` geridas automaticamente pelo `sheets_repository`, mais os campos específicos de cada entidade (ver `CLIENTES_COLUMNS` em `core/app_Gestor/views.py` para a lista completa de Clientes).

## Configuração

1. Crie e ative um virtualenv, depois instale as dependências:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Variáveis de ambiente (opcionais, têm valor padrão para desenvolvimento):
   - `MERCADO_PAGO_ACCESS_TOKEN` — token de acesso da API do Mercado Pago, necessário para gerar pagamentos PIX reais.
   - `GOOGLE_SHEET_ID` — ID da planilha do Google Sheets que serve Clientes/Parceiros/Preços ao vivo (tem um valor padrão em `core/settings.py`, sobrescreva se for usar outra planilha). Precisa ter as abas `Clientes`, `Parceiros` e `Precos` já criadas, compartilhadas com a conta de serviço do `credentials.json`.
   - `GOOGLE_SHEETS_CACHE_TTL_SECONDS` — TTL (segundos, padrão 20) do cache de leitura em memória do `sheets_repository`.
3. Coloque o `credentials.json` (Service Account do Google com acesso à planilha/Drive) na raiz do projeto. Esse arquivo é ignorado pelo git — nunca o adicione ao versionamento.
4. Rode as migrações e inicie o servidor:
   ```
   python manage.py migrate
   python manage.py runserver
   ```
5. Acesse o painel em `http://127.0.0.1:8000/` (não pede login — ver limitação abaixo).

## Rodando os testes

```
python manage.py test core.app_Gestor.tests
```

Cobre `parsing.py`, `sheets_repository.py`, `models.py` e `views.py`. Os scripts em `scripts/` continuam sendo checagens manuais avulsas, não testes de CI.

## Limitações conhecidas

- **Nenhum endpoint exige login.** O projeto não usa `django.contrib.auth` em nenhuma view — é adequado apenas para uso interno em rede restrita, não para exposição pública, até que autenticação seja adicionada.

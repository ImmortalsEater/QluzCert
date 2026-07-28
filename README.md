# QCert Manager

Painel interno (Django + JS puro) para gestão de vendas de certificados digitais (e-CPF/e-CNPJ): clientes, parceiros, tabela de preços, renovações e pagamentos, com o Google Sheets como fonte de verdade ao vivo (não um sync em lote) para Clientes, Parceiros, Preços e Contatos.

## Estrutura do projeto

- `core.app_Gestor` — app ativo, roteado em `core/urls.py`. Toda view, template e arquivo estático novo deve entrar aqui.
  - `sheets_repository.py` — única camada de acesso à planilha (`list_rows`/`get_row`/`create_row`/`update_row`/`delete_row`), com cache de leitura em memória de curto TTL e controle de concorrência otimista via `atualizado_em`. Toda leitura/escrita de Clientes, Parceiros e Preços passa por aqui.
  - `parsing.py` — parsers compartilhados (`parse_date`, `parse_decimal`, `bool_from`) usados para interpretar os valores de célula (sempre texto) vindos da planilha.
- `core.app` — não tem nenhuma URL própria. Existe só para manter os modelos `PlanilhaRegistro`/`Colaborador`, que ficam sem uso ativo hoje (preservados apenas para uma eventual migração futura para um servidor com banco compartilhado). Não adicione views, templates ou estáticos novos aqui.
- `preview_login/` — mockups estáticos (HTML/CSS) de login, cadastro e recuperação de senha, mantidos aqui só como referência de design. As páginas realmente servidas pelo Django (rotas `/preview/login/`, `/preview/cadastro/`, `/preview/recuperar-senha/`) usam os templates equivalentes em `core/app_Gestor/templates/`, não estes arquivos.

A planilha do Google (`GOOGLE_SHEET_ID`) tem quatro abas geridas pelo app — **Clientes**, **Parceiros**, **Precos** e **Contatos** — cada uma com colunas `id`/`atualizado_em` geridas automaticamente pelo `sheets_repository`, mais os campos específicos de cada entidade (ver `CLIENTES_COLUMNS` em `core/app_Gestor/views.py` para a lista completa de Clientes). A aba **Contatos** guarda o histórico de contato e as notificações de pagamento (colunas: `cliente_id`, `tipo` — `contato` ou `notificacao` —, `data`, `canal`, `resultado`, `produto`, `agendamento`, `titulo`, `texto`, `status`) e precisa ser criada manualmente na planilha antes do primeiro uso.

## Configuração

1. Crie e ative um virtualenv, depois instale as dependências:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Variáveis de ambiente (opcionais, têm valor padrão para desenvolvimento):
   - `MERCADO_PAGO_ACCESS_TOKEN` — token de acesso da API do Mercado Pago, necessário para gerar pagamentos PIX reais.
   - `GOOGLE_SHEET_ID` — ID da planilha do Google Sheets que serve Clientes/Parceiros/Preços/Contatos ao vivo (tem um valor padrão em `core/settings.py`, sobrescreva se for usar outra planilha). Precisa ter as abas `Clientes`, `Parceiros`, `Precos` e `Contatos` já criadas, compartilhadas com a conta de serviço do `credentials.json`.
   - `GOOGLE_SHEETS_CACHE_TTL_SECONDS` — TTL (segundos, padrão 20) do cache de leitura em memória do `sheets_repository`.
   - `DJANGO_SECRET_KEY` — chave secreta do Django. Tem um valor padrão de desenvolvimento em `core/settings.py`; **defina esta variável em qualquer ambiente que não seja a sua máquina local**.
   - `DJANGO_DEBUG` — `True`/`False` (padrão `True`). Defina como `False` ao publicar fora da rede interna — com `DEBUG=True`, erros expõem stack trace completo (incluindo `DJANGO_SECRET_KEY`/`GOOGLE_SHEET_ID`) para qualquer requisição.
   - `DJANGO_ALLOWED_HOSTS` — lista de hosts separada por vírgula (ex: `qcert.empresa.com,10.0.0.5`). Obrigatório preencher se `DJANGO_DEBUG=False`.
3. Coloque o `credentials.json` (Service Account do Google com acesso à planilha/Drive) na raiz do projeto. Esse arquivo é ignorado pelo git — nunca o adicione ao versionamento.
4. Rode as migrações e inicie o servidor:
   ```
   python manage.py migrate
   python manage.py runserver
   ```
5. Acesse o painel em `http://127.0.0.1:8000/` (não pede login — ver limitação abaixo).

Em produção (`DJANGO_DEBUG=False`), os estáticos passam a ser servidos com hash
de conteúdo no nome do arquivo (cache-busting) — rode `python manage.py
collectstatic` antes de subir o servidor, ou os arquivos em `staticfiles/`
ficarão desatualizados em relação ao código.

## Rodando os testes

```
python manage.py test core.app_Gestor.tests
```

Cobre `parsing.py`, `sheets_repository.py`, `models.py` e `views.py`. Os scripts em `scripts/` continuam sendo checagens manuais avulsas, não testes de CI.

## Limitações conhecidas

- **Nenhum endpoint exige login.** O projeto não usa `django.contrib.auth` em nenhuma view — é adequado apenas para uso interno em rede restrita, não para exposição pública, até que autenticação seja adicionada.

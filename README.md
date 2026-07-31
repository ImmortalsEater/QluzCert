# QCert Manager

Painel interno para gestão de vendas e emissão de certificados digitais (e-CPF/e-CNPJ) — clientes, parceiros, tabela de preços, renovações, documentos e permissões, tudo rodando em cima do Google Sheets como fonte de verdade ao vivo, não um sync em lote.

## Visão geral

- **Dashboard** — métricas de clientes, alertas de vencimento/pagamento e notificações recentes, tudo calculado na hora a partir da planilha.
- **Funil de Atendimento** — quadro Kanban por status do cliente, com drag-and-drop persistido direto na planilha.
- **Clientes / Planilha** — busca, filtros, seleção de colunas, edição com controle de concorrência otimista (evita sobrescrever edição concorrente sem avisar).
- **Parceiros** e **Tabela de Preços** — cadastro simples, com acesso controlável por permissão.
- **Renovações** — clientes agrupados por proximidade do vencimento do certificado.
- **Documentos do cliente** — upload de RG/CNH/contrato social etc. para uma pasta do cliente no Google Drive, com fallback local se o Drive estiver indisponível.
- **Cadastro e login** — autenticação real via planilha (sem depender de banco local), com cadastro self-service de vendedor.
- **Permissões granulares** — cada vendedor libera ações específicas (parceiros, preços, pagamentos, comissões, exclusões) por coluna na planilha, aplicadas sempre no servidor.
- **Exportação `.xlsx`** — snapshot de Clientes/Parceiros/Preços pra baixar quando precisar.

Fora do ar hoje: pagamento via PIX/Mercado Pago (código existe, mas não está ligado a nenhuma rota) e recuperação de senha self-service (só existe como mockup de tela) — ver [Limitações conhecidas](#limitações-conhecidas).

## Stack técnico

| Camada | Tecnologia |
|---|---|
| Backend | Django 5.2 |
| Dados de negócio (Clientes/Parceiros/Preços/Contatos/Usuarios/Documentos) | Google Sheets, via API — não um banco tradicional |
| Arquivos de cliente | Google Drive (Shared Drive), com fallback em disco local |
| Banco local | SQLite — só sessão legada e alguns modelos ainda não migrados pra planilha (ver [Limitações](#limitações-conhecidas)) |
| Exportação/planilha | pandas, openpyxl |
| Monitoramento (opcional) | Sentry |
| Frontend | HTML + CSS + JavaScript puro, sem framework |

## Arquitetura

- **`core.app_Gestor`** — o único app ativo. Toda view, template e arquivo estático novo entra aqui, roteado por `core/urls.py`.
  - `sheets_repository.py` — única camada de acesso à planilha (`list_rows`/`get_row`/`create_row`/`update_row`/`delete_row`). Cuida de retry com backoff, cache de leitura em memória de curto TTL, controle de concorrência otimista (`atualizado_em`) e geração automática de `id`/`atualizado_em` por aba.
  - `drive_repository.py` — mesma ideia, mas para o Google Drive (`get_or_create_client_folder`/`upload_file`/`download_file`/`delete_file`), usado só pela feature de Documentos.
  - `auth_backends.py` — `SheetsBackend`, autentica contra a aba **Usuarios** da planilha em vez de um banco local.
  - `parsing.py` — parsers compartilhados (`parse_date`, `parse_decimal`, `bool_from`) pra interpretar valores de célula, que sempre chegam como texto.
- **`core.app`** — sem URLs próprias. Existe só pra manter os modelos legados `PlanilhaRegistro`/`Colaborador`, sem uso ativo hoje. Não adicione nada novo aqui.

A planilha do Google (`GOOGLE_SHEET_ID`) tem seis abas geridas pelo app:

| Aba | Guarda |
|---|---|
| **Clientes** | Dados de venda/certificado de cada cliente (ver `CLIENTES_COLUMNS` em `views.py` pra lista completa) |
| **Parceiros** | Cadastro de parceiros/contadores |
| **Precos** | Tabela de preços por tipo de certificado |
| **Contatos** | Histórico de contato e notificações de pagamento — setup manual antes do primeiro uso |
| **Usuarios** | Login (`username`, `password` hasheada, `tipo`) e permissões granulares (`perm_*`) — ver [Permissões](#permissões) |
| **Documentos** | Metadados dos arquivos de cliente enviados pro Drive — ver [Documentos](#documentos) |

Todas as abas ganham `id` e `atualizado_em` automaticamente; Contatos, Usuarios e Documentos exigem o cabeçalho criado manualmente na planilha antes do primeiro uso (o app não cria abas sozinho).

## Configuração

1. Crie e ative um virtualenv, depois instale as dependências:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Variáveis de ambiente (todas com valor padrão de desenvolvimento em `core/settings.py`, exceto onde indicado):
   - `DJANGO_SECRET_KEY` — **defina em qualquer ambiente que não seja sua máquina local**; fora do modo debug, o Django recusa subir com a chave padrão.
   - `DJANGO_DEBUG` — `True`/`False` (padrão `True`). Com `True`, erros expõem stack trace completo (incluindo segredos) pra qualquer requisição — nunca deixe `True` fora da rede interna.
   - `DJANGO_ALLOWED_HOSTS` — hosts separados por vírgula. Obrigatório se `DJANGO_DEBUG=False`.
   - `DJANGO_CSRF_TRUSTED_ORIGINS` — origens completas separadas por vírgula (ex: `https://qcert.empresa.com`), só relevante atrás de HTTPS/proxy.
   - `GOOGLE_SHEET_ID` — ID da planilha que serve Clientes/Parceiros/Preços/Contatos/Usuarios/Documentos ao vivo. Precisa ter as abas já criadas e compartilhadas com a conta de serviço do `credentials.json`.
   - `GOOGLE_SHEETS_CACHE_TTL_SECONDS` — TTL (segundos, padrão 20) do cache de leitura em memória.
   - `GOOGLE_DRIVE_ROOT_FOLDER_ID` — pasta raiz no Drive onde as subpastas de cliente são criadas. **Precisa ser um Shared Drive (Workspace)** — uma conta de serviço não tem cota própria fora de um Shared Drive, então uma pasta pessoal compartilhada falha o upload mesmo permitindo criar subpastas.
   - `SENTRY_DSN` — opcional; sem ela, monitoramento de erro fica desligado.
   - `MERCADO_PAGO_ACCESS_TOKEN` — lido pelo código de pagamento PIX, mas essa integração **não está roteada hoje** (ver [Limitações](#limitações-conhecidas)) — não configure esperando que funcione.
3. Coloque o `credentials.json` (Service Account do Google, com escopo de **Sheets e Drive**) na raiz do projeto. Ignorado pelo git — nunca commite.
4. Crie as abas **Usuarios** e **Documentos** na planilha (cabeçalhos descritos em [Arquitetura](#arquitetura) e [Documentos](#documentos)), rode as migrações, crie o primeiro usuário admin e suba o servidor:
   ```
   python manage.py migrate
   python manage.py create_sheets_user <usuario> <senha> --admin
   python manage.py runserver
   ```
5. Acesse `http://127.0.0.1:8000/` — redireciona pra `/login/`. A partir daí:
   - Novos vendedores podem se cadastrar sozinhos em `/cadastro/` (cria direto como vendedor, sem nenhuma permissão extra).
   - Promover alguém a admin, ou ajustar as permissões de um vendedor, continua sendo manual: `create_sheets_user --admin` pra criar, ou a tela **Gestão de Usuários** (`/usuarios/`, só admin) pra editar quem já existe.
   - Recuperação de senha esquecida ainda não existe — reset é manual, editando a planilha.

`python manage.py createsuperuser` continua existindo, mas cria um usuário **local** (SQLite), só útil pra acessar `/admin/` numa máquina de desenvolvimento — não é o login usado pelo resto do time, que vem sempre da aba Usuarios.

Em produção (`DJANGO_DEBUG=False`), os estáticos passam a ser servidos com hash de conteúdo no nome do arquivo — rode `python manage.py collectstatic` antes de subir o servidor.

## Permissões

Papel base pela coluna `tipo` na aba Usuarios:

- **admin** — acesso total, bypassa toda permissão granular abaixo. Único papel que acessa a tela de Gestão de Usuários (`/usuarios/`).
- **vendedor** (qualquer valor de `tipo` diferente de `admin`, incluindo vazio) — acesso base: Dashboard, Funil de Atendimento, Clientes, Planilha, Renovações, criar/editar clientes, upload de documentos, registrar contatos. Ações extras dependem de permissão individual.

Permissões individuais vêm de sete colunas booleanas (`Sim`/`Não`) na mesma aba — **precisam existir no cabeçalho antes de usar**, mesmo padrão de setup manual das outras abas:

| Coluna | Libera |
|---|---|
| `perm_parceiros` | criar/editar/excluir Parceiro + menu "Parceiros" |
| `perm_precos` | criar/editar/excluir Tabela de Preços + menu "Tabela de Preços" |
| `perm_pagamentos` | visibilidade do menu/cards "Pagamentos" |
| `perm_excluir_cliente` | excluir Cliente |
| `perm_excluir_documento` | excluir Documento |
| `perm_comissoes` | ver valores reais de comissão (sem a permissão, o dado vem mascarado do servidor) |
| `perm_financeiro` | ver faturamento recebido no Dashboard (mesma regra: mascarado no servidor, não só escondido) |

Célula vazia = `Não` (restrito por padrão). Comissão e faturamento são o único caso onde a permissão **impede o dado de sair do servidor** — não é uma coluna escondida por CSS, o número real nunca chega ao navegador de quem não tem a permissão. Todas as outras permissões são checadas no servidor a cada requisição (`@admin_required`/`permission_required` em `views.py`), mesmo se a rota for acessada direto pela URL — o menu escondido no frontend é só a primeira camada.

`is_superuser`/`is_staff` e as permissões granulares (guardadas na sessão do navegador, não no banco local) são resincronizadas a partir da planilha a cada login.

## Documentos

Documentos de cliente (RG/CNH, contrato social etc.) ficam como arquivos numa pasta do Drive por cliente, com metadados na aba **Documentos**:

```
id, cliente_ref, nome_cliente, nome_original, tipo_documento, tamanho_bytes,
observacao, drive_file_id, drive_view_url, local_path, atualizado_em
```

A aba **Clientes** precisa de uma coluna extra `drive_folder_id` (também setup manual). A pasta do cliente é criada só no primeiro upload dele, não na criação do cliente — leads que nunca enviam nada não deixam pasta vazia no Drive.

Se o Drive estiver fora do ar (API desligada, sem rede, cota estourada, pasta não compartilhada), o arquivo é salvo em `MEDIA_ROOT/documentos_pendentes/<cliente_id>/` em vez de ser perdido, e a linha na aba fica marcada como pendente — sem ressincronização automática depois. Em um deploy sem disco persistente esse fallback local não sobrevive a um restart.

Downloads passam pelo servidor (nunca redirecionam direto pro link do Drive), o que garante a checagem de que o documento pertence mesmo ao cliente pedido — sem isso, alguém poderia trocar o ID na URL e baixar documento de outro cliente.

## Rodando os testes

```
python manage.py test core.app_Gestor.tests
```

Cobre `parsing.py`, `sheets_repository.py`, `models.py` e `views.py` — inclui autenticação, permissões, cadastro, documentos e o mascaramento de comissão/financeiro. Os scripts em `scripts/` são checagens manuais avulsas, não fazem parte do CI.

Pra um roteiro de QA manual ponta a ponta (criar cliente, testar concorrência, upload de documento, XSS, etc.), veja [`TESTING.md`](TESTING.md).

## Limitações conhecidas

- **Pagamento via PIX/Mercado Pago não funciona.** O código (`criar_pagamento_pix`, `webhook_mercado_pago`) existe mas não está registrado em nenhuma rota de `core/urls.py` — não é uma feature em produção, é código órfão.
- **Sem recuperação de senha self-service.** A tela existe (`recuperar-senha.html`), mas é só um mockup de design sem lógica por trás. Reset de senha hoje é manual, editando a planilha diretamente.
- **Sem servidor com disco persistente.** Por isso login/permissões vivem na planilha (não em banco local) e a sessão do navegador vive inteira num cookie assinado (`SESSION_ENGINE = signed_cookies`), não na tabela `django_session`. Isso também significa que `AppState`, `PagamentoCliente` e `DocumentoCliente` (modelos que ainda usam SQLite local, não a planilha) **não são confiáveis** nesse mesmo cenário — ainda não migrados.

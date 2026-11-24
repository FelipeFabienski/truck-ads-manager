# 📢 Facilitador de Anúncios

Plataforma online para criar, publicar e gerenciar anúncios no **Facebook** e **Instagram** de forma simplificada: o usuário preenche os dados do produto, **escreve o texto do anúncio** com ajuda de dicas, e publica direto nas redes sociais com os interessados sendo direcionados para o **WhatsApp** do vendedor.

> **Modelo de integração:** BYOT (*Bring Your Own Token*) — cada usuário conecta a própria conta de anúncios da Meta com um Access Token gerado no Meta Business Suite. **Sem Facebook OAuth** e sem exigir cadastro do SaaS no Meta for Developers.
>
> **RBAC:** sem cadastro público — o **administrador** cria e gerencia usuários (clientes), bloqueios e senhas; cada **cliente** gerencia seus próprios anúncios e integrações, com isolamento total de dados (IDOR protegido).
>
> **Nota:** o texto do anúncio é escrito pelo usuário. Cobrança/planos ficam para uma fase futura.

---

## Funcionalidades

| Área | O que faz |
|---|---|
| **Usuários (admin)** | Criar clientes/admins, editar, ativar/bloquear/desativar, redefinir senha, ver contadores — com guardas de "último admin" |
| **Conta** | Confirmação por email (24h), login bloqueado até confirmar, reset de senha por link (30 min) |
| **Sessão** | Cookie httpOnly; expira por inatividade (15 min) com renovação automática; máximo de 7 dias |
| **Proteção anti-abuso** | Rate limit por IP e bloqueio progressivo de login: 5 falhas → 1 min · 10 → 5 min · 20 → 30 min |
| **Criação de anúncio** | Wizard em 5 passos: Produto (até 6 fotos) → Vendedor → Campanha (**escolha da integração Meta**) → Público → **Texto do anúncio** (manual, título ≤90 / texto ≤900) |
| **Integrações Meta (BYOT)** | Múltiplas credenciais por usuário; nome, Access Token, Ad Account, Page, Instagram, Business, App ID/Secret, WhatsApp; **descoberta automática de ativos**; **validação completa**; token criptografado (AES-256-GCM) e sempre mascarado; uma ativa por usuário |
| **Publicação** | Campanha → conjunto (budget, segmentação, WhatsApp) → criativo → anúncio, sempre **PAUSADO** na Meta; só integrações **validadas** publicam |
| **Gestão** | Listar com filtros/busca, pausar, ativar, excluir, editar texto e integração |
| **Métricas** | Impressões, cliques, leads, valor gasto e custo por lead — hoje / 7 dias / 30 dias (por credencial BYOT) |
| **Auditoria** | Tabela `audit_logs` registra criação/edição/validação/exclusão de credenciais e publicação/edição/pausa de campanhas (sem segredos) |

---

## Stack

- **Backend:** Node.js + Express 5 + SQLite (better-sqlite3) — camadas: rotas finas → `credentialStore`/`userStore`/`campaignStore` → `metaOps` → **`MetaAdsService`** (única saída de rede)
- **Frontend:** React 19 + Vite + React Router, CSS próprio
- **Monorepo npm workspaces:** `server/` (porta 4000) + `web/` (porta 5173 com proxy `/api` e `/uploads`)
- **Legado:** a implementação anterior em **Python/FastAPI** está preservada em [`legacy-python/`](legacy-python/) (com seus próprios `railway.toml`, `Dockerfile`, `Procfile`, `alembic` e `requirements.txt`), **sem papel ativo** na aplicação atual. Para implantar o legado no Railway, aponte o *Root Directory* do serviço para `/legacy-python`.

---

## Como rodar

### Pré-requisitos
- Node.js 22+ ([download](https://nodejs.org)) — no Windows: `winget install OpenJS.NodeJS.LTS`

### Passos

```bash
npm install        # instala backend + frontend (workspaces)
npm run dev        # sobe API (4000) e frontend (5173) juntos
```

Abra **http://localhost:5173**

- O **primeiro usuário cadastrado vira admin** automaticamente (acesso à área de Integrações).
- Sem SMTP configurado, os emails (confirmação/reset) entram em **modo dev**: o link aparece na resposta da própria tela e no console do servidor (tabela `email_outbox`, consultável em `GET /api/dev/emails`).

### Scripts úteis

| Comando | Faz o quê |
|---|---|
| `npm run dev` | API + frontend em paralelo |
| `npm run dev:server` | só a API |
| `npm run dev:web` | só o frontend |
| `npm run build` | build de produção do frontend (`web/dist`) |

O banco SQLite é criado sozinho em `server/data/facilitador.db` (delete a pasta para recomeçar do zero). Uploads ficam em `server/uploads/`.

---

## Configuração (`.env`)

Copie `server/.env.example` para `server/.env` e ajuste. Todas as variáveis são opcionais em desenvolvimento:

```bash
# --- Geral ---
NODE_ENV=production            # em produção; cookie ganha Secure
PORT=4000
APP_URL=http://localhost:5173  # URL pública do frontend (links dos emails)

# --- Segurança ---
# Chave AES-256 (64 chars hex) para criptografar tokens do Meta.
# Se não definir, uma chave é gerada e salva em server/data/.encryption-key (dev).
ENCRYPTION_KEY=sua-chave-hex-de-64-caracteres

# --- Sessão (padrões da spec: 15 min idle / 7 dias) ---
SESSION_IDLE_MINUTES=15
SESSION_ABSOLUTE_DAYS=7

# --- Anti-abuso (padrões da spec) ---
RATE_LIMIT_GLOBAL=300          # req/min por IP no /api
RATE_LIMIT_AUTH=20             # req/min por IP em /api/auth
LOGIN_COUNT_WINDOW_MINUTES=15  # janela de contagem de falhas

# --- Emails (SMTP real) ---
# Sem estas variáveis o sistema usa o modo dev (outbox local + link na tela).
SMTP_HOST=smtp.seudominio.com.br
SMTP_PORT=587
SMTP_SECURE=false              # true para porta 465
SMTP_USER=usuario
SMTP_PASS=senha
SMTP_FROM="Facilitador de Anúncios <nao-responder@seudominio.com.br>"

# --- Meta Graph API ---
GRAPH_API_VERSION=v23.0
```

---

## Conectando o Meta (BYOT — integração por usuário)

Cada usuário (admin ou cliente) conecta a própria conta em **Integrações → Nova integração**:

1. No [Meta Business Suite](https://business.facebook.com/settings), gere um **Access Token** (de usuário, idealmente de longa duração) com as permissões mínimas:
   - `ads_management` · `pages_read_engagement` · `pages_manage_ads`
   - Opcionalmente `business_management`, `ads_read`
2. Cadastre a integração informando: **nome**, **token**, **Ad Account ID** (`act_...` — normalizado automaticamente), **Page ID**, e opcionais: Instagram Account ID, Business ID, App ID, App Secret, WhatsApp. Os identificadores ficam **pendentes** até a primeira validação.
3. **Descobrir ativos** — consulta real na Graph API (`/me/adaccounts`, `/me/accounts` com Instagram vinculado, `/me/businesses`) e preenche os campos de seleção (também aceita digitação manual).
4. **Validar integração** — validação completa na Meta: token (`/me`), permissões concedidas (`/me/permissions`) vs. mínimas exigidas, contas de anúncios (nome/moeda/status), página, Instagram, compatibilidade entre ativos e **expiração do token** (`/debug_token` quando App ID + App Secret estão configurados). A integração só vira **Conectada** se tudo crítico passar — um HTTP 200 isolado não basta.
5. **Tornar ativa** — apenas uma integração fica ativa por usuário; é ela que publica por padrão (ou a escolhida na criação da campanha).

**Status possíveis:** Pendente de validação · Conectado · Token expirado · Permissões insuficientes · Erro de conexão · Desativado.

**Publicação:** objetivo `OUTCOME_ENGAGEMENT`, destino `WHATSAPP_MESSAGE` (link wa.me com mensagem pré-preenchida + CTA WhatsApp), segmentação BR + idade/gênero/interesses. Sempre criado **PAUSADO** — o usuário revisa e ativa. `appsecret_proof` (HMAC-SHA256) é enviado automaticamente quando há App Secret.

### Importação inicial do administrador

```bash
# 1. Defina temporariamente em server/.env (nunca no código):
META_ADMIN_INITIAL_ACCESS_TOKEN=seu-token-aqui

# 2. Rode a partir da pasta server/:
cd server && node scripts/import-admin-token.mjs

# 3. REMOVA o valor da variável do .env (o token já está criptografado no banco).
```

A integração **"Meta Ads - Administrador"** é criada associada ao administrador ativo existente (sem presumir id), com status **Pendente de validação** e ativos pendentes — valide quando quiser pelo botão na interface.

### Substituição e renovação de tokens

Em **Editar** integração: informe um novo Access Token (vazio mantém o atual). Qualquer troca de token, App Secret ou identificador de ativo devolve a integração para **Pendente de validação** — revalide com o botão. O endpoint `debug_token` (com App ID/Secret) detecta e registra a data de expiração do token.

### Segurança das credenciais

- Tokens e App Secrets criptografados com **AES-256-GCM** (`META_CREDENTIALS_ENCRYPTION_KEY`); descriptografados **somente em memória**, dentro do `MetaAdsService`
- API nunca devolve segredos — apenas versões **mascaradas** (`EAAG••••••••x9ZD`)
- Nenhum token/segredo em logs ou na auditoria
- RBAC completo: cliente acessa só o que é dele; admin gerencia todos (seguindo mascarado)
- Endpoints sensíveis com rate limiting; credencial não validada/desativada **não publica**
- Toda comunicação com a Meta acontece **somente por ação explícita do usuário** — nada automático no startup

---

## 🚀 Deploy no Railway (versão Node/React — aplicação principal)

Deploy de **serviço único**: o backend Node serve também o frontend React compilado (`web/dist`) com fallback SPA — um só serviço e domínio.

### Como funciona (automático)

O arquivo [`railway.json`](railway.json) na raiz configura o Railway (Railpack):
- **Build:** `npm ci && npm run build` (instala workspaces e compila o React para `web/dist`)
- **Start:** `npm run start` → `node server/src/index.js` (lê `PORT` do Railway e escuta em `0.0.0.0`)
- **Health check:** `GET /api/health` (público, sem autenticação)

> ⚠️ **Cada push em `main` dispara o deploy automaticamente.** O painel do serviço deve estar com **Root Directory = `/`** (raiz do repositório).

### Configuração obrigatória no painel do Railway

1. **Settings → Root Directory:** `/` (raiz) — atualmente pode estar `/legacy-python`; corrija para a raiz
2. **Variables:**

| Variável | Valor | Por quê |
|---|---|---|
| `NODE_ENV` | `production` | cookies Secure + modo produção |
| `APP_URL` | `https://truck-ads-manager-production.up.railway.app` | links nos emails |
| `META_CREDENTIALS_ENCRYPTION_KEY` | 64 hex **fixos** (ex: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`) | **CRÍTICO:** sem chave fixa, os tokens criptografados ficam ilegíveis após cada redeploy (o arquivo dev vive em filesystem efêmero) |
| `DATABASE_PATH` | `/data/facilitador.db` | persistência fora do efêmero |
| `UPLOAD_DIR` | `/data/uploads` | fotos/avatares persistentes |
| `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASS`/`SMTP_FROM` | do seu provedor | emails reais (confirmação/reset); sem eles, modo dev |
| `SESSION_IDLE_MINUTES` / `SESSION_ABSOLUTE_DAYS` | opcional | padrões: 15 min / 7 dias |

3. **Storage → +New → Volume:** monte um volume em **`/data`** (mesma máquina do serviço). É ele que garante que **usuários, campanhas, tokens criptografados e o banco SQLite sobrevivam aos redeploys**. Sem volume, o banco é recriado vazio a cada deploy (nenhum dado do Postgres legado é apagado — o banco legado do Python continua intocado no seu plugin PostgreSQL).

### Sobre o PostgreSQL legado

A versão atual usa **SQLite** no volume; o PostgreSQL do legado **não é lido nem alterado** pela aplicação atual. Se quiser migrar dados antigos (usuários/campanhas do legado), será um projeto à parte — nada é excluído automaticamente.

### Health check e rotas

- API sob `/api/*` (404 JSON em rotas inexistentes)
- Frontend SPA em todas as demais rotas GET (`/login`, `/app/*`…) com `index.html` do build
- Uploads servidos em `/uploads/*`
- Health check público: `/api/health`

### Deploy do legado (se um dia precisar)

O código Python permanece **apenas referência** em `legacy-python/`, autocontido (com `railway.toml`, `Dockerfile`, `Procfile` e `alembic` próprios). Para implantá-lo, crie um serviço Railway com **Root Directory = `/legacy-python`** — não afeta a aplicação principal.

---

## Estrutura do projeto

```
facilitador-anuncios/
├── AGENTS.md                            # regras permanentes para agentes (sync, segredos)
├── server/                              # ⭐ APLICAÇÃO PRINCIPAL — backend Node.js
│   ├── scripts/import-admin-token.mjs   # importação inicial BYOT do admin
│   ├── src/
│   │   ├── config.js                    # env + defaults (META_API_VERSION, sessão…)
│   │   ├── db.js / migrations.js        # schema SQLite + migration 001 (credenciais v2, audit_logs)
│   │   ├── app.js / index.js
│   │   ├── middlewares/                 # auth (sessão), rateLimit, loginLock
│   │   ├── routes/                      # auth, admin (RBAC), profile, credentials,
│   │   │                                # campaignsThin, metrics, plans, dev
│   │   └── services/                    # meta (MetaAdsService), metaOps, stores, audit…
│   ├── .env.example                     # template de variáveis (valores fictícios)
│   ├── data/                            # banco SQLite (gitignore)
│   └── uploads/                         # fotos e avatares (gitignore)
├── web/                                 # ⭐ APLICAÇÃO PRINCIPAL — frontend React
│   └── src/                             # páginas: Login, Dashboard, Wizard, Integrations,
│                                        # AdminUsers, Metrics, Profile, Plans…
└── legacy-python/                       # 📦 implementação legada Python/FastAPI — SEM papel
                                         #    ativo; preservada com histórico e configs de deploy
```

---

## Segurança implementada

- Senhas com **scrypt**; tokens de email/sessão guardados como SHA-256
- Access Tokens e App Secrets com **AES-256-GCM**, mascarados na interface, descriptografados só em memória
- Cookies httpOnly + SameSite=Lax + Secure (produção)
- Bloqueio progressivo de login + rate limit por IP
- RBAC (admin/cliente) e isolamento de dados (proteção IDOR em todas as rotas por ID)
- Validação de todos os IDs antes de qualquer requisição à Graph API; host em allowlist fixa (https, sem loopback/privados)
- Link do WhatsApp com allowlist estrita (https + wa.me + dígitos)
- Auditoria (`audit_logs`) de credenciais, campanhas e gestão de usuários — sem segredos
- Reset de senha encerra todas as sessões; guardas de "último admin"

## Executando os testes futuramente (após autorização)

Nenhuma validação ou comunicação com a Meta é executada automaticamente. Para testar quando autorizado:

1. **Validar a integração do admin:** login como admin → Integrações → "Meta Ads - Administrador" → **Validar integração** (executa /me, /me/permissions, /me/adaccounts, debug_token etc.)
2. **Descobrir ativos:** botão "Descobrir ativos" no mesmo cartão → preencher Ad Account/Page → revalidar
3. **Publicar de verdade:** criar campanha com foto → Publicar (cria PAUSADO na conta) → conferir no Gerenciador de Anúncios → Ativar
4. **Métricas:** aba Métricas após a veiculação começar

## Limitações e pendências conhecidas

- **WhatsApp ads:** a Meta exige que a página tenha um **WhatsApp Business Account** vinculado; o sistema detecta o WABA da página na publicação quando disponível — sem ele, a Meta pode recusar o anúncio com erro explícito
- **Interesses** não resolvidos pelo `targetingsearch` são silenciosamente ignorados (informado na resposta da publicação)
- **Cobrança/planos**: catálogo existe, sem enforcement — fase futura
- **Discover-raw** (descoberta com token não salvo) foi simplificado: salve a integração e use "Descobrir ativos" no cartão

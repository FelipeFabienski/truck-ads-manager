# AGENTS.md — Instruções permanentes para agentes de desenvolvimento

Projeto: **Facilitador de Anúncios** (`truck-ads-manager`)
Repositório: https://github.com/FelipeFabienski/truck-ads-manager.git
Branch principal: `main`

---

## Fluxo obrigatório ao finalizar QUALQUER implementação (regra permanente)

Ao finalizar qualquer implementação, correção, melhoria ou alteração solicitada,
**realizar automaticamente a sincronização com o GitHub**, sem necessidade de nova
solicitação do usuário:

1. **Analisar** a estrutura atual do projeto.
2. **Verificar** o estado do repositório e possíveis alterações remotas (`git fetch`).
3. **Implementar** a funcionalidade solicitada.
4. **Revisar** as alterações realizadas.
5. **Verificar** possíveis exposições de credenciais e informações sensíveis.
6. **Atualizar** a documentação, quando necessário.
7. **Adicionar ao stage somente** os arquivos pertinentes à implementação.
8. **Criar commit** com mensagem descritiva (padrão Conventional Commits).
9. **Realizar push** para o GitHub.
10. **Confirmar** que a sincronização foi concluída (hash local == remoto).

### Padrões de commit (Conventional Commits)

- `feat:` novas funcionalidades
- `fix:` correções de problemas
- `refactor:` reestruturação de código
- `docs:` atualização de documentação
- `style:` alterações visuais
- `security:` melhorias de segurança
- `chore:` manutenção e configurações

## Segurança — NUNCA enviar ao GitHub

- Arquivos `.env` com credenciais reais (manter apenas `.env.example` com valores fictícios)
- Access Tokens da Meta
- App Secrets
- Senhas SMTP
- Chaves de criptografia (`META_CREDENTIALS_ENCRYPTION_KEY`, `ENCRYPTION_KEY`)
- Bancos de dados locais (`server/data/`) — contêm usuários e tokens criptografados
- Backups com informações sensíveis
- Logs com credenciais
- `node_modules/`

**Se credenciais forem identificadas no histórico do Git, INTERROMPER a sincronização
e informar o usuário imediatamente.**

## Restrições

- ❌ Não executar testes funcionais/automatizados sem autorização do usuário
- ❌ Não realizar requisições à Meta sem autorização
- ❌ Não publicar ou ativar anúncios
- ❌ **Nunca usar `git push --force`**
- ❌ Não descartar alterações locais ou remotas
- ❌ Não fazer deploy em produção automaticamente
- ⚠️ Em conflito não resolúvel com segurança: **interromper e informar o motivo**

## Relatório obrigatório ao final de cada implementação

- Resumo da implementação
- Arquivos criados e modificados
- Alterações no banco de dados (quando aplicável)
- Mensagem do commit
- Hash do commit
- Branch utilizada
- Status do push
- Link do commit no GitHub
- Confirmação de que nenhuma credencial foi versionada
- Limitações e pendências

A atualização do repositório GitHub faz parte da **definição de conclusão** de cada
implementação.

---

## Contexto técnico do projeto (para agentes futuros)

- **Aplicação principal:** Node.js/React — **todas as novas implementações são feitas
  exclusivamente em `server/` (Express 5 + better-sqlite3, porta 4000) e `web/`
  (React 19 + Vite, porta 5173)**. Nada deve ser adicionado ao `legacy-python/`.
- **Legado:** `legacy-python/` preserva a implementação anterior em Python/FastAPI
  (com `railway.toml`, `Dockerfile`, `alembic` próprios) — apenas referência histórica,
  SEM papel ativo. Se precisar implantá-la no Railway, aponte o *Root Directory* do
  serviço para `/legacy-python`.
- **Integração Meta:** BYOT (Bring Your Own Token), sem OAuth; `MetaAdsService`
  (`server/src/services/meta.js`) é a única saída de rede; tokens criptografados
  AES-256-GCM; validação/descoberta/publicação somente por ação explícita do usuário
- **RBAC:** sem cadastro público; admin cria usuários; status `active|inactive|blocked`
- **Arquitetura:** rotas finas → stores (`credentialStore`, `userStore`, `campaignStore`)
  → ops (`metaOps`, `campaignOps`) → `MetaAdsService`
- **Banco:** SQLite em `server/data/` (gitignored); migrations idempotentes em
  `server/src/migrations.js`
- **Textos de anúncio:** escritos manualmente pelo usuário (IA removida por decisão)
- **Cobrança/planos:** catálogo existe, sem enforcement — fase futura
- **Node:** instalar via `winget` se ausente; PATH: `export PATH="/c/Program Files/nodejs:$PATH"`

import Database from 'better-sqlite3';
import fs from 'node:fs';
import path from 'node:path';
import { config } from './config.js';
import { runLegacyMigrations } from './migrations.js';

fs.mkdirSync(path.dirname(config.databasePath), { recursive: true });

export const db = new Database(config.databasePath);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Executa um único statement SQL constante (sem .exec para Multi-statement; ver migrations.js)
const ddl = (sql) => db.prepare(sql).run();

// ---------------------------------------------------------------------------
// Schema base (instalações novas). O schema antigo de meta_credentials é
// convertido pela migration 001 (src/migrations.js), preservando os dados.
// ---------------------------------------------------------------------------
ddl(`CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',          -- user | admin
  company TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  avatar_path TEXT DEFAULT '',
  timezone TEXT DEFAULT 'America/Sao_Paulo',
  email_verified INTEGER NOT NULL DEFAULT 0,
  plan_id INTEGER REFERENCES plans(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','blocked')),
  created_at TEXT NOT NULL
)`);

ddl(`CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  absolute_expires_at TEXT NOT NULL,
  ip TEXT DEFAULT '',
  user_agent TEXT DEFAULT ''
)`);
ddl(`CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)`);

ddl(`CREATE TABLE IF NOT EXISTS email_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL,                          -- confirm | reset
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
)`);

ddl(`CREATE TABLE IF NOT EXISTS login_lockouts (
  email TEXT PRIMARY KEY COLLATE NOCASE,
  fail_count INTEGER NOT NULL DEFAULT 0,
  window_start TEXT NOT NULL,
  locked_until TEXT,
  last_fail_at TEXT NOT NULL
)`);

ddl(`CREATE TABLE IF NOT EXISTS meta_credentials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  access_token_enc TEXT NOT NULL,              -- AES-256-GCM, nunca texto puro
  ad_account_id TEXT,                          -- formato normalizado act_ID (nulo enquanto pendente)
  page_id TEXT,
  instagram_actor_id TEXT,
  business_id TEXT,
  app_id TEXT,
  app_secret_enc TEXT,                         -- AES-256-GCM, opcional (appsecret_proof)
  whatsapp_number TEXT DEFAULT '',
  token_expires_at TEXT,                       -- detectado na validação (debug_token)
  last_validated_at TEXT,
  validation_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (validation_status IN ('pending','connected','token_expired','insufficient_permissions','connection_error')),
  is_active INTEGER NOT NULL DEFAULT 0,        -- habilitada (0 = "Desativado" na UI)
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)`);
// (índices de meta_credentials criados na migration 001, após o rebuild)

ddl(`CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,                        -- ex: credential.validated, campaign.published
  resource_type TEXT DEFAULT '',               -- credential | campaign | user
  resource_id TEXT DEFAULT '',
  status TEXT DEFAULT 'ok',                    -- ok | error | forbidden
  ip_address TEXT DEFAULT '',
  created_at TEXT NOT NULL
)`);
ddl(`CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id)`);
ddl(`CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)`);

ddl(`CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_name TEXT NOT NULL,
  color TEXT DEFAULT '',
  year TEXT DEFAULT '',
  price TEXT DEFAULT '',
  km TEXT DEFAULT '',
  city TEXT DEFAULT '',
  state TEXT DEFAULT '',
  seller_name TEXT NOT NULL,
  whatsapp TEXT NOT NULL,
  daily_budget REAL NOT NULL,
  duration_days INTEGER NOT NULL,
  age_min INTEGER NOT NULL DEFAULT 18,
  age_max INTEGER NOT NULL DEFAULT 65,
  gender TEXT NOT NULL DEFAULT 'all',          -- all | male | female
  interests TEXT NOT NULL DEFAULT '[]',        -- JSON array
  photos TEXT NOT NULL DEFAULT '[]',           -- JSON array de paths
  title TEXT DEFAULT '',
  ad_text TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',        -- draft | paused | active
  credential_id INTEGER REFERENCES meta_credentials(id) ON DELETE SET NULL, -- integração escolhida
  meta_campaign_id TEXT DEFAULT '',
  meta_adset_id TEXT DEFAULT '',
  meta_ad_id TEXT DEFAULT '',
  published_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)`);
ddl(`CREATE INDEX IF NOT EXISTS idx_campaigns_user ON campaigns(user_id)`);

ddl(`CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  price_cents INTEGER NOT NULL,
  max_campaigns INTEGER,
  features TEXT NOT NULL DEFAULT '[]'
)`);

ddl(`CREATE TABLE IF NOT EXISTS email_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  to_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  html TEXT NOT NULL,
  text TEXT DEFAULT '',
  created_at TEXT NOT NULL
)`);

const seedPlans = db.prepare('SELECT COUNT(*) AS n FROM plans');
if (seedPlans.get().n === 0) {
  const insert = db.prepare(
    'INSERT INTO plans (name, price_cents, max_campaigns, features) VALUES (?, ?, ?, ?)'
  );
  const tx = db.transaction(() => {
    insert.run('Gratuito', 0, 5, JSON.stringify(['5 campanhas por mês', 'Publicação no Facebook', 'Métricas básicas']));
    insert.run('Profissional', 9900, 50, JSON.stringify(['50 campanhas por mês', 'Publicação no Facebook e Instagram', 'Métricas completas', 'Suporte prioritário']));
    insert.run('Empresa', 29900, null, JSON.stringify(['Contas ilimitadas', 'Múltiplas contas de anúncio', 'Relatórios avançados', 'Suporte dedicado']));
  });
  tx();
  db.prepare('UPDATE users SET plan_id = 1 WHERE plan_id IS NULL').run();
}

// Converte instalações do schema legado (executa uma vez; idempotente)
runLegacyMigrations(db);

/**
 * Migração 001 — converte instalações do schema legado de `meta_credentials`
 * (created_by/token_encrypted/instagram_id) para o schema multiusuário atual
 * (user_id/access_token_enc/instagram_actor_id/business_id/app_id/app_secret_enc/
 * token_expires_at/updated_at), preservando os dados existentes.
 *
 * Também garante audit_logs e campaigns.credential_id em instalações antigas.
 * Idempotente: cada passo checa o schema atual antes de agir.
 */
export function runLegacyMigrations(db) {
  // ---- 1. meta_credentials: rebuild se o schema for o legado ----
  const credCols = db.prepare('PRAGMA table_info(meta_credentials)').all().map((c) => c.name);
  if (credCols.length > 0 && credCols.includes('created_by')) {
    const migrate = db.transaction(() => {
      db.prepare(`CREATE TABLE meta_credentials_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        access_token_enc TEXT NOT NULL,
        ad_account_id TEXT,
        page_id TEXT,
        instagram_actor_id TEXT,
        business_id TEXT,
        app_id TEXT,
        app_secret_enc TEXT,
        whatsapp_number TEXT DEFAULT '',
        token_expires_at TEXT,
        last_validated_at TEXT,
        validation_status TEXT NOT NULL DEFAULT 'pending'
          CHECK (validation_status IN ('pending','connected','token_expired','insufficient_permissions','connection_error')),
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )`).run();

      // Preserva credenciais existentes; IDs de ativo ficam no formato antigo e são
      // renormalizados; validation_status legado é mapeado para os novos valores.
      db.prepare(`INSERT INTO meta_credentials_new
        (id, user_id, name, access_token_enc, ad_account_id, page_id, instagram_actor_id,
         whatsapp_number, last_validated_at, validation_status, is_active, created_at, updated_at)
        SELECT
          id, created_by, name, token_encrypted,
          CASE WHEN ad_account_id IS NOT NULL AND ad_account_id != '' THEN 'act_' || ad_account_id ELSE NULL END,
          NULLIF(page_id, ''),
          NULLIF(instagram_id, ''),
          whatsapp_number,
          last_validated_at,
          CASE validation_status WHEN 'valid' THEN 'connected' WHEN 'invalid' THEN 'connection_error' ELSE 'pending' END,
          is_active,
          created_at, created_at
        FROM meta_credentials
        WHERE created_by IS NOT NULL`).run();

      db.prepare('DROP TABLE meta_credentials').run();
      db.prepare('ALTER TABLE meta_credentials_new RENAME TO meta_credentials').run();
    });
    migrate();
    console.log('✅ Migration: meta_credentials migrada para o schema multiusuário (dados preservados)');
  }

  // ---- 2. Colunas novas em instalações que já têm o schema intermediário ----
  const afterCols = db.prepare('PRAGMA table_info(meta_credentials)').all().map((c) => c.name);
  if (afterCols.length > 0) {
    if (!afterCols.includes('business_id')) {
      db.prepare('ALTER TABLE meta_credentials ADD COLUMN business_id TEXT').run();
    }
    if (!afterCols.includes('app_id')) {
      db.prepare('ALTER TABLE meta_credentials ADD COLUMN app_id TEXT').run();
    }
    if (!afterCols.includes('app_secret_enc')) {
      db.prepare('ALTER TABLE meta_credentials ADD COLUMN app_secret_enc TEXT').run();
    }
    if (!afterCols.includes('token_expires_at')) {
      db.prepare('ALTER TABLE meta_credentials ADD COLUMN token_expires_at TEXT').run();
    }
    if (!afterCols.includes('updated_at')) {
      db.prepare('ALTER TABLE meta_credentials ADD COLUMN updated_at TEXT').run();
    }
  }

  // ---- 3. audit_logs (idempotente) ----
  db.prepare(`CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    status TEXT DEFAULT 'ok',
    ip_address TEXT DEFAULT '',
    created_at TEXT NOT NULL
  )`).run();
  db.prepare('CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id)').run();
  db.prepare('CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at)').run();

  // ---- 4. campaigns.credential_id (idempotente) ----
  const campCols = db.prepare('PRAGMA table_info(campaigns)').all().map((c) => c.name);
  if (campCols.length > 0 && !campCols.includes('credential_id')) {
    db.prepare('ALTER TABLE campaigns ADD COLUMN credential_id INTEGER REFERENCES meta_credentials(id) ON DELETE SET NULL').run();
    console.log('✅ Migration: campaigns.credential_id adicionada');
  }
}

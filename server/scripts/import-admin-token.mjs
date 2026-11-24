/**
 * Importação inicial da credencial do administrador (BYOT).
 *
 * Lê META_ADMIN_INITIAL_ACCESS_TOKEN do ambiente (server/.env ou variável de
 * sessão), criptografa (AES-256-GCM) e grava a integração "Meta Ads - Administrador"
 * associada ao administrador ativo existente — SEM presumir user id 1.
 * NÃO valida na Meta (status fica "Pendente de validação"); nenhuma chamada externa.
 *
 * Uso (após definir a variável em server/.env):
 *   cd server && node scripts/import-admin-token.mjs
 * A variável de ambiente pode ser removida após a importação.
 */
import 'dotenv/config';
import { db } from '../src/db.js';
import { encryptSecret } from '../src/services/crypto.js';

const token = process.env.META_ADMIN_INITIAL_ACCESS_TOKEN || '';
if (!token) {
  console.error('❌ META_ADMIN_INITIAL_ACCESS_TOKEN não definida. Adicione-a em server/.env (temporariamente).');
  process.exit(1);
}

const admin = db
  .prepare("SELECT * FROM users WHERE role = 'admin' AND status = 'active' ORDER BY id ASC LIMIT 1")
  .get();
if (!admin) {
  console.error('❌ Nenhum administrador ativo encontrado. Crie o admin primeiro (primeiro usuário do sistema).');
  process.exit(1);
}

const name = 'Meta Ads - Administrador';
const existing = db.prepare('SELECT id FROM meta_credentials WHERE user_id = ? AND name = ?').get(admin.id, name);
if (existing) {
  console.log(`ℹ️  A integração "${name}" já existe (id ${existing.id}) para o admin ${admin.name} (id ${admin.id}). Nada a fazer.`);
  process.exit(0);
}

const now = new Date().toISOString();
const info = db
  .prepare(
    'INSERT INTO meta_credentials (user_id, name, access_token_enc, whatsapp_number, validation_status, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  )
  .run(admin.id, name, encryptSecret(token), '', 'pending', 0, now, now);

console.log('✅ Integração importada:');
console.log(`   id: ${info.lastInsertRowid}`);
console.log(`   admin: ${admin.name} (user id ${admin.id})`);
console.log(`   nome: ${name}`);
console.log('   status: Pendente de validação (não validamos na Meta — validação só quando o admin autorizar)');
console.log('   🔒 Token criptografado (AES-256-GCM). Você já pode REMOVER META_ADMIN_INITIAL_ACCESS_TOKEN do .env.');

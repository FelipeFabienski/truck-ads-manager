import { db } from '../db.js';
import { hashPassword, generateToken, hashToken } from '../services/crypto.js';
import { publicCredentialView } from './credentialStore.js';
import { config } from '../config.js';

/**
 * Camada de acesso a usuários para o painel administrativo (RBAC).
 * Hash de senha, tokens de confirmação e guardas de "último admin" ficam aqui —
 * as rotas admin chamam apenas funções de alto nível (padrão credentialStore).
 */

export function listUsersWithCounts() {
  return db
    .prepare(
      'SELECT u.*,(SELECT COUNT(*) FROM campaigns c WHERE c.user_id = u.id) AS campaigns_count,(SELECT COUNT(*) FROM meta_credentials mc WHERE mc.user_id = u.id) AS credentials_count FROM users u ORDER BY u.created_at ASC'
    )
    .all();
}

export function getUserById(id) {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(id) || null;
}

export function getUserPublic(row) {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    company: row.company,
    phone: row.phone,
    avatarPath: row.avatar_path,
    timezone: row.timezone,
    emailVerified: !!row.email_verified,
    planId: row.plan_id,
    status: row.status, // active | inactive | blocked
    createdAt: row.created_at,
  };
}

function issueConfirmToken(userId) {
  const token = generateToken();
  db.prepare('INSERT INTO email_tokens (token_hash, user_id, type, expires_at, created_at) VALUES (?, ?, ?, ?, ?)').run(
    hashToken(token),
    userId,
    'confirm',
    new Date(Date.now() + config.tokens.confirmMs).toISOString(),
    new Date().toISOString()
  );
  return token;
}

/**
 * Cria usuário sem cadastro público. Conta nasce não verificada; devolve o link
 * de confirmação para o administrador encaminhar (sem envio automático de email).
 */
export function createUserByAdmin({ name, email, senha, role }) {
  const now = new Date().toISOString();
  const info = db
    .prepare(
      "INSERT INTO users (name, email, password_hash, role, email_verified, plan_id, status, created_at) VALUES (?, ?, ?, ?, 0, 1, 'active', ?)"
    )
    .run(name, email, hashPassword(senha), role, now);
  const token = issueConfirmToken(info.lastInsertRowid);
  const confirmUrl = config.appUrl + '/verificar-email?token=' + encodeURIComponent(token);
  return { userId: info.lastInsertRowid, confirmUrl };
}

/** Edita nome/role/status com guardas de último admin. Devolve null se alvo inexistente. */
export function updateUserByAdmin(targetId, { name, role, status }, requester) {
  const target = getUserById(targetId);
  if (!target) return { error: { status: 404, message: 'Usuário não encontrado.' } };

  const nextRole = role === 'admin' ? 'admin' : role === 'user' ? 'user' : target.role;
  const nextStatus = ['active', 'inactive', 'blocked'].includes(status) ? status : target.status;

  if (target.role === 'admin' && nextRole === 'user') {
    const admins = db.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND status = 'active'").get().n;
    if (admins <= 1) return { error: { status: 409, message: 'Não é possível remover o último administrador ativo.' } };
  }
  if (target.id === requester.id && (nextRole === 'user' || nextStatus !== 'active')) {
    return { error: { status: 409, message: 'Você não pode rebaixar ou bloquear a própria conta de administrador.' } };
  }

  db.prepare('UPDATE users SET name = ?, role = ?, status = ? WHERE id = ?').run(name, nextRole, nextStatus, targetId);
  if (nextStatus !== 'active') db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);
  return { user: getUserById(targetId) };
}

/** Ativa/bloqueia/desativa com as mesmas guardas. */
export function setUserStatus(targetId, status, requester) {
  const target = getUserById(targetId);
  if (!target) return { error: { status: 404, message: 'Usuário não encontrado.' } };

  if (!['active', 'inactive', 'blocked'].includes(status)) {
    return { error: { status: 400, message: 'Status inválido (active, inactive ou blocked).' } };
  }
  if (target.id === requester.id && status !== 'active') {
    return { error: { status: 409, message: 'Você não pode alterar o status da própria conta de administrador.' } };
  }
  if (target.role === 'admin' && status !== 'active') {
    const admins = db.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND status = 'active'").get().n;
    if (admins <= 1) return { error: { status: 409, message: 'Não é possível bloquear o último administrador ativo.' } };
  }

  db.prepare('UPDATE users SET status = ? WHERE id = ?').run(status, targetId);
  if (status !== 'active') db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);
  return { user: getUserById(targetId) };
}

/** Redefine a senha de um usuário e encerra suas sessões. */
export function resetUserPassword(targetId, senha) {
  const target = getUserById(targetId);
  if (!target) return { error: { status: 404, message: 'Usuário não encontrado.' } };
  if (senha.length < 8 || senha.length > 72) {
    return { error: { status: 400, message: 'A senha precisa ter entre 8 e 72 caracteres.' } };
  }
  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hashPassword(senha), targetId);
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);
  return { ok: true };
}

/** Integrações de um cliente (sempre mascaradas, nunca expõem segredos). */
export function listUserCredentials(targetId) {
  const target = db.prepare('SELECT id, name, email FROM users WHERE id = ?').get(targetId);
  if (!target) return { error: { status: 404, message: 'Usuário não encontrado.' } };
  const rows = db.prepare('SELECT * FROM meta_credentials WHERE user_id = ? ORDER BY created_at DESC').all(targetId);
  return { user: target, credentials: rows.map((r) => publicCredentialView(r)) };
}

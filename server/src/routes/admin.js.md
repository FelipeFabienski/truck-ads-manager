// admin.js — gestão de usuários (RBAC): criar/editar/status/senha/integrações dos clientes.
// (Arquivo auxiliar .md — convertido para routes/admin.js por script; ver relatório.)

import { Router } from 'express';
import { db } from '../db.js';
import { requireAuth, requireAdmin } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import { hashPassword, generateToken, hashToken } from '../services/crypto.js';
import { publicCredentialView } from '../services/credentialStore.js';
import { audit } from '../services/audit.js';
import { isEmail, str } from '../utils/validate.js';
import { config } from '../config.js';

const router = Router();
router.use(requireAuth, requireAdmin);

function publicUser(row) {
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

/** GET /api/admin/users — lista todos os usuários com contadores. */
router.get('/users', (req, res) => {
  const rows = db
    .prepare(
      'SELECT u.*,(SELECT COUNT(*) FROM campaigns c WHERE c.user_id = u.id) AS campaigns_count,(SELECT COUNT(*) FROM meta_credentials mc WHERE mc.user_id = u.id) AS credentials_count FROM users u ORDER BY u.created_at ASC'
    )
    .all();
  res.json({
    users: rows.map((r) => ({ ...publicUser(r), campaignsCount: r.campaigns_count, credentialsCount: r.credentials_count })),
  });
});

/**
 * POST /api/admin/users — cria usuário (RBAC: sem cadastro público).
 * Conta nasce não verificada; o link de confirmação é devolvido na resposta
 * para o administrador encaminhar. Sem chamadas externas aqui.
 */
router.post('/users', rateLimit('admin-users', 10), (req, res) => {
  const name = str(req.body?.name, 120);
  const email = str(req.body?.email, 200).toLowerCase();
  const senhaInicial = String(req.body?.senha ?? '');
  const role = req.body?.role === 'admin' ? 'admin' : 'user';

  const errors = {};
  if (!name) errors.name = 'Informe o nome.';
  if (!isEmail(email)) errors.email = 'Email inválido.';
  if (senhaInicial.length < 8) errors.senha = 'A senha precisa ter pelo menos 8 caracteres.';
  if (senhaInicial.length > 72) errors.senha = 'A senha pode ter no máximo 72 caracteres.';
  if (Object.keys(errors).length) return res.status(400).json({ error: 'Verifique os campos.', errors });

  const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
  if (existing) return res.status(409).json({ error: 'Este email já está cadastrado.', errors: { email: 'Este email já está cadastrado.' } });

  const now = new Date().toISOString();
  const info = db
    .prepare(
      "INSERT INTO users (name, email, password_hash, role, email_verified, plan_id, status, created_at) VALUES (?, ?, ?, ?, 0, 1, 'active', ?)"
    )
    .run(name, email, hashPassword(senhaInicial), role, now);

  const confirmToken = issueConfirmToken(info.lastInsertRowid);
  const confirmUrl = config.appUrl + '/verificar-email?token=' + encodeURIComponent(confirmToken);

  audit({ userId: req.user.id, action: 'user.created', resourceType: 'user', resourceId: info.lastInsertRowid, ip: req.ip });
  const row = db.prepare('SELECT * FROM users WHERE id = ?').get(info.lastInsertRowid);
  res.status(201).json({
    message: 'Usuário criado! Encaminhe o link de confirmação para ' + email + '.',
    user: publicUser(row),
    devEmailLink: config.isDev ? confirmUrl : undefined,
  });
});

/** PUT /api/admin/users/:id — edita nome/role/status (guardas de último admin). */
router.put('/users/:id', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });
  const target = db.prepare('SELECT * FROM users WHERE id = ?').get(targetId);
  if (!target) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const name = str(req.body?.name, 120) || target.name;
  const role = req.body?.role === 'admin' ? 'admin' : req.body?.role === 'user' ? 'user' : target.role;
  const status = ['active', 'inactive', 'blocked'].includes(req.body?.status) ? req.body.status : target.status;

  if (target.role === 'admin' && role === 'user') {
    const admins = db.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND status = 'active'").get().n;
    if (admins <= 1) return res.status(409).json({ error: 'Não é possível remover o último administrador ativo.' });
  }
  if (target.id === req.user.id && (role === 'user' || status !== 'active')) {
    return res.status(409).json({ error: 'Você não pode rebaixar ou bloquear a própria conta de administrador.' });
  }

  db.prepare('UPDATE users SET name = ?, role = ?, status = ? WHERE id = ?').run(name, role, status, targetId);
  if (status !== 'active') db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);

  audit({ userId: req.user.id, action: 'user.updated', resourceType: 'user', resourceId: targetId, ip: req.ip });
  res.json({ message: 'Usuário atualizado!', user: publicUser(db.prepare('SELECT * FROM users WHERE id = ?').get(targetId)) });
});

/** POST /api/admin/users/:id/status — ativar / bloquear / desativar. */
router.post('/users/:id/status', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });
  const target = db.prepare('SELECT * FROM users WHERE id = ?').get(targetId);
  if (!target) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const status = req.body?.status;
  if (!['active', 'inactive', 'blocked'].includes(status)) {
    return res.status(400).json({ error: 'Status inválido (active, inactive ou blocked).' });
  }
  if (target.id === req.user.id && status !== 'active') {
    return res.status(409).json({ error: 'Você não pode alterar o status da própria conta de administrador.' });
  }
  if (target.role === 'admin' && status !== 'active') {
    const admins = db.prepare("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND status = 'active'").get().n;
    if (admins <= 1) return res.status(409).json({ error: 'Não é possível bloquear o último administrador ativo.' });
  }

  db.prepare('UPDATE users SET status = ? WHERE id = ?').run(status, targetId);
  if (status !== 'active') db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);

  audit({ userId: req.user.id, action: 'user.updated', resourceType: 'user', resourceId: targetId, ip: req.ip });
  const labels = { active: 'ativado', blocked: 'bloqueado', inactive: 'desativado' };
  res.json({ message: 'Usuário ' + labels[status] + '!', user: publicUser(db.prepare('SELECT * FROM users WHERE id = ?').get(targetId)) });
});

/** POST /api/admin/users/:id/password — redefine a senha do usuário. */
router.post('/users/:id/password', rateLimit('admin-password', 10), (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });
  const target = db.prepare('SELECT * FROM users WHERE id = ?').get(targetId);
  if (!target) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const novaSenha = String(req.body?.senha ?? '');
  if (novaSenha.length < 8 || novaSenha.length > 72) {
    return res.status(400).json({ error: 'A senha precisa ter entre 8 e 72 caracteres.' });
  }
  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hashPassword(novaSenha), targetId);
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(targetId);

  audit({ userId: req.user.id, action: 'user.password_reset', resourceType: 'user', resourceId: targetId, ip: req.ip });
  res.json({ message: 'Senha redefinida e sessões encerradas.' });
});

/** GET /api/admin/users/:id/credentials — integrações de um cliente (mascaradas). */
router.get('/users/:id/credentials', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });
  const target = db.prepare('SELECT id, name, email FROM users WHERE id = ?').get(targetId);
  if (!target) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const rows = db.prepare('SELECT * FROM meta_credentials WHERE user_id = ? ORDER BY created_at DESC').all(targetId);
  res.json({ user: target, credentials: rows.map((r) => publicCredentialView(r)) });
});

export default router;

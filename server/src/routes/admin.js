import { Router } from 'express';
import { requireAuth, requireAdmin } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import {
  listUsersWithCounts,
  getUserById,
  getUserPublic,
  createUserByAdmin,
  updateUserByAdmin,
  setUserStatus,
  resetUserPassword,
  listUserCredentials,
} from '../services/userStore.js';
import { audit } from '../services/audit.js';

const router = Router();
router.use(requireAuth, requireAdmin);

/** GET /api/admin/users — lista todos os usuários com contadores. */
router.get('/users', (req, res) => {
  const rows = listUsersWithCounts();
  res.json({
    users: rows.map((r) => {
      const u = getUserPublic(r);
      return { ...u, campaignsCount: r.campaigns_count, credentialsCount: r.credentials_count };
    }),
  });
});

/**
 * POST /api/admin/users — cria usuário (RBAC: sem cadastro público).
 * O link de confirmação volta na resposta para o administrador encaminhar.
 */
router.post('/users', rateLimit('admin-users', 10), (req, res) => {
  const name = String(req.body?.name ?? '').trim().slice(0, 120);
  const email = String(req.body?.email ?? '').trim().toLowerCase().slice(0, 200);
  const senhaInicial = String(req.body?.senha ?? '');
  const role = req.body?.role === 'admin' ? 'admin' : 'user';

  const errors = {};
  if (!name) errors.name = 'Informe o nome.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) errors.email = 'Email inválido.';
  if (senhaInicial.length < 8) errors.senha = 'A senha precisa ter pelo menos 8 caracteres.';
  if (senhaInicial.length > 72) errors.senha = 'A senha pode ter no máximo 72 caracteres.';
  if (Object.keys(errors).length) return res.status(400).json({ error: 'Verifique os campos.', errors });

  const result = createUserByAdmin({ name, email, senha: senhaInicial, role });
  audit({ userId: req.user.id, action: 'user.created', resourceType: 'user', resourceId: result.userId, ip: req.ip });
  const row = getUserById(result.userId);
  res.status(201).json({
    message: 'Usuário criado! Encaminhe o link de confirmação para ' + email + '.',
    user: getUserPublic(row),
    devEmailLink: result.confirmUrl,
  });
});

/** PUT /api/admin/users/:id — edita nome/role/status. */
router.put('/users/:id', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const result = updateUserByAdmin(
    targetId,
    { name: String(req.body?.name ?? ''), role: req.body?.role, status: req.body?.status },
    { id: req.user.id }
  );
  if (result.error) return res.status(result.error.status).json({ error: result.error.message });

  audit({ userId: req.user.id, action: 'user.updated', resourceType: 'user', resourceId: targetId, ip: req.ip });
  res.json({ message: 'Usuário atualizado!', user: getUserPublic(result.user) });
});

/** POST /api/admin/users/:id/status — ativar / bloquear / desativar. */
router.post('/users/:id/status', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const result = setUserStatus(targetId, req.body?.status, { id: req.user.id });
  if (result.error) return res.status(result.error.status).json({ error: result.error.message });

  audit({ userId: req.user.id, action: 'user.updated', resourceType: 'user', resourceId: targetId, ip: req.ip });
  const labels = { active: 'ativado', blocked: 'bloqueado', inactive: 'desativado' };
  res.json({ message: 'Usuário ' + labels[req.body?.status] + '!', user: getUserPublic(result.user) });
});

/** POST /api/admin/users/:id/password — redefine a senha do usuário. */
router.post('/users/:id/password', rateLimit('admin-password', 10), (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const result = resetUserPassword(targetId, String(req.body?.senha ?? ''));
  if (result.error) return res.status(result.error.status).json({ error: result.error.message });

  audit({ userId: req.user.id, action: 'user.password_reset', resourceType: 'user', resourceId: targetId, ip: req.ip });
  res.json({ message: 'Senha redefinida e sessões encerradas.' });
});

/** GET /api/admin/users/:id/credentials — integrações de um cliente (mascaradas). */
router.get('/users/:id/credentials', (req, res) => {
  const targetId = Number.parseInt(String(req.params.id), 10);
  if (!Number.isInteger(targetId)) return res.status(404).json({ error: 'Usuário não encontrado.' });

  const result = listUserCredentials(targetId);
  if (result.error) return res.status(result.error.status).json({ error: result.error.message });
  res.json(result);
});

export default router;

import { Router } from 'express';
import multer from 'multer';
import path from 'node:path';
import fs from 'node:fs';
import { db } from '../db.js';
import { config } from '../config.js';
import { requireAuth } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import { hashPassword, verifyPassword } from '../services/crypto.js';
import { str } from '../utils/validate.js';

const router = Router();
router.use(requireAuth);

const avatarStorage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(config.uploadDir, 'avatars');
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase() || '.jpg';
    cb(null, `${Date.now()}-${Math.random().toString(36).slice(2, 10)}${ext}`);
  },
});
const avatarUpload = multer({
  storage: avatarStorage,
  limits: { fileSize: 2 * 1024 * 1024 },
  fileFilter: (req, file, cb) => cb(null, /^image\/(jpeg|png|webp|gif)$/.test(file.mimetype)),
});

router.get('/', (req, res) => {
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);
  res.json({
    user: {
      id: user.id, name: user.name, email: user.email, role: user.role, company: user.company,
      phone: user.phone, avatarPath: user.avatar_path, timezone: user.timezone,
      emailVerified: !!user.email_verified, planId: user.plan_id, createdAt: user.created_at,
    },
  });
});

router.put('/', (req, res) => {
  const name = str(req.body?.name, 120);
  const company = str(req.body?.company, 120);
  const phone = str(req.body?.phone, 40);
  const timezone = str(req.body?.timezone, 60) || 'America/Sao_Paulo';
  if (!name) return res.status(400).json({ error: 'Informe seu nome.', errors: { name: 'Informe seu nome.' } });
  db.prepare('UPDATE users SET name = ?, company = ?, phone = ?, timezone = ? WHERE id = ?').run(name, company, phone, timezone, req.user.id);
  res.json({ message: 'Perfil atualizado com sucesso!' });
});

router.post('/avatar', avatarUpload.single('avatar'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'Envie uma imagem (JPG, PNG, WEBP ou GIF, até 2MB).' });
  const old = db.prepare('SELECT avatar_path FROM users WHERE id = ?').get(req.user.id)?.avatar_path;
  const relPath = `avatars/${req.file.filename}`;
  db.prepare('UPDATE users SET avatar_path = ? WHERE id = ?').run(relPath, req.user.id);
  // remove o avatar antigo do disco
  if (old) {
    const oldAbs = path.join(config.uploadDir, old);
    if (oldAbs.startsWith(config.uploadDir) && fs.existsSync(oldAbs)) fs.unlink(oldAbs, () => {});
  }
  res.json({ message: 'Foto de perfil atualizada!', avatarPath: relPath });
});

router.put('/password', rateLimit('password-change', 5), (req, res) => {
  const current = String(req.body?.currentPassword || '');
  const next = String(req.body?.newPassword || '');
  if (!current || !next) return res.status(400).json({ error: 'Informe a senha atual e a nova senha.' });
  if (next.length < 8 || next.length > 72) {
    return res.status(400).json({ error: 'A nova senha precisa ter entre 8 e 72 caracteres.' });
  }
  const user = db.prepare('SELECT password_hash FROM users WHERE id = ?').get(req.user.id);
  if (!verifyPassword(current, user.password_hash)) {
    return res.status(401).json({ error: 'A senha atual está incorreta.' });
  }
  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hashPassword(next), req.user.id);
  res.json({ message: 'Senha alterada com sucesso!' });
});

router.post('/deactivate', rateLimit('deactivate', 5), (req, res) => {
  const password = String(req.body?.password || '');
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);
  if (!verifyPassword(password, user.password_hash)) {
    return res.status(401).json({ error: 'Senha incorreta. A desativação exige confirmação da senha.' });
  }
  db.prepare("UPDATE users SET status = 'inactive' WHERE id = ?").run(req.user.id);
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(req.user.id);
  res.clearCookie(config.session.cookieName, { path: '/' });
  res.json({ message: 'Sua conta foi desativada.' });
});

export default router;

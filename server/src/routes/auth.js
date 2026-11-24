import { Router } from 'express';
import { db } from '../db.js';
import { config } from '../config.js';
import { hashPassword, verifyPassword, generateToken, hashToken } from '../services/crypto.js';
import { mailer } from '../services/mailer.js';
import { setSessionCookie, clearSessionCookie, createSessionForUser, destroySession } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import { loginLockGuard, checkLock, recordFailure, recordSuccess } from '../middlewares/loginLock.js';
import { isEmail, str } from '../utils/validate.js';

const router = Router();
const authLimiter = rateLimit('auth', config.rateLimit.authMax);

function sendTokenEmail({ to, name, url, kind }) {
  const isConfirm = kind === 'confirm';
  const subject = isConfirm ? 'Confirme seu email — Facilitador de Anúncios' : 'Redefinição de senha — Facilitador de Anúncios';
  const label = isConfirm
    ? `${name}, clique no botão abaixo para ativar sua conta:`
    : `${name}, clique no botão abaixo para criar uma nova senha (o link é válido por 30 minutos):`;
  return mailer.send({
    to,
    subject,
    html: `<div style="font-family:Arial,sans-serif;max-width:520px">
      <h2 style="color:#2590eb">Facilitador de Anúncios</h2>
      ${mailer.linkHtml(url, label)}
      <p style="color:#888;font-size:13px">Se você não solicitou este email, ignore esta mensagem.</p>
    </div>`,
    text: `${label} ${url}`,
  });
}

function issueEmailToken(userId, type, expiresMs) {
  const token = generateToken();
  db.prepare('INSERT INTO email_tokens (token_hash, user_id, type, expires_at, created_at) VALUES (?, ?, ?, ?, ?)').run(
    hashToken(token),
    userId,
    type,
    new Date(Date.now() + expiresMs).toISOString(),
    new Date().toISOString()
  );
  return token;
}

function consumeEmailToken(rawToken, type) {
  const row = db.prepare('SELECT * FROM email_tokens WHERE token_hash = ? AND type = ?').get(hashToken(rawToken), type);
  if (!row) return null;
  if (row.used_at) return null;
  if (Date.now() > Date.parse(row.expires_at)) return null;
  db.prepare('UPDATE email_tokens SET used_at = ? WHERE token_hash = ?').run(new Date().toISOString(), row.token_hash);
  return row;
}

function publicUser(user) {
  const { id, name, email, role, company, phone, avatar_path, timezone, email_verified, plan_id, status, created_at } = user;
  return { id, name, email, role, company, phone, avatarPath: avatar_path, timezone, emailVerified: !!email_verified, planId: plan_id, status, createdAt: created_at };
}

function devLink(url) {
  // Em modo dev (sem SMTP) devolvemos o link para facilitar os testes
  return config.isDev && mailer.isDevMode ? { devEmailLink: url } : {};
}

// ---------------------------------------------------------------------------
// Cadastro público REMOVIDO: somente o administrador cria usuários (RBAC).
// ---------------------------------------------------------------------------

router.post('/resend-verification', authLimiter, (req, res) => {
  const email = str(req.body?.email, 200).toLowerCase();
  const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  // Resposta genérica para não revelar quais emails existem
  if (user && !user.email_verified) {
    const token = issueEmailToken(user.id, 'confirm', config.tokens.confirmMs);
    const url = `${config.appUrl}/verificar-email?token=${encodeURIComponent(token)}`;
    sendTokenEmail({ to: user.email, name: user.name, url, kind: 'confirm' });
    return res.json({ message: 'Email de confirmação reenviado.', ...devLink(url) });
  }
  res.json({ message: 'Se este email precisar de confirmação, reenviamos o link.' });
});

router.post('/verify-email', authLimiter, (req, res) => {
  const row = consumeEmailToken(String(req.body?.token || ''), 'confirm');
  if (!row) return res.status(400).json({ error: 'Link de confirmação inválido ou expirado. Solicite um novo.' });
  db.prepare('UPDATE users SET email_verified = 1 WHERE id = ?').run(row.user_id);
  res.json({ message: 'Email confirmado! Sua conta está ativa. Faça login para continuar.' });
});

router.post('/login', authLimiter, loginLockGuard, (req, res) => {
  const email = str(req.body?.email, 200).toLowerCase();
  const password = String(req.body?.password || '');

  if (!email || !password) return res.status(400).json({ error: 'Informe email e senha.' });

  const { locked, retryAfterSec } = checkLock(email);
  if (locked) {
    res.set('Retry-After', String(retryAfterSec));
    return res.status(423).json({
      error: `Muitas tentativas incorretas. Tente novamente em ${retryAfterSec > 60 ? `${Math.ceil(retryAfterSec / 60)} minuto(s)` : `${retryAfterSec} segundo(s)`}.`,
    });
  }

  const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
  if (!user || !verifyPassword(password, user.password_hash)) {
    const { locked: nowLocked, failCount, lockMinutes } = recordFailure(email);
    if (nowLocked) {
      res.set('Retry-After', String(lockMinutes * 60));
      return res.status(423).json({
        error: `Conta temporariamente bloqueada por ${lockMinutes} minuto(s) após ${failCount} tentativas incorretas.`,
      });
    }
    return res.status(401).json({ error: 'Email ou senha incorretos.' });
  }
  if (user.status === 'inactive') {
    return res.status(403).json({ error: 'Esta conta foi desativada. Entre em contato com o administrador.' });
  }
  if (user.status === 'blocked') {
    return res.status(403).json({ error: 'Esta conta foi bloqueada pelo administrador. Entre em contato com o suporte.' });
  }
  if (!user.email_verified) {
    return res.status(403).json({ error: 'Confirme seu email antes de acessar. Verifique sua caixa de entrada.', code: 'EMAIL_UNVERIFIED' });
  }

  recordSuccess(email);
  const token = createSessionForUser(user.id, { ip: req.ip, userAgent: req.headers['user-agent'] });
  setSessionCookie(res, token);
  res.json({ user: publicUser(user) });
});

router.post('/logout', (req, res) => {
  const token = req.cookies?.[config.session.cookieName];
  if (token) destroySession(token);
  clearSessionCookie(res);
  res.json({ message: 'Sessão encerrada.' });
});

router.get('/me', (req, res) => {
  const token = req.cookies?.[config.session.cookieName];
  if (!token) return res.status(401).json({ error: 'Não autenticado.' });
  const session = db.prepare('SELECT * FROM sessions WHERE token_hash = ?').get(hashToken(token));
  const user = session && db.prepare('SELECT * FROM users WHERE id = ?').get(session.user_id);
  if (!user || user.status !== 'active') return res.status(401).json({ error: 'Não autenticado.' });
  res.json({ user: publicUser(user) });
});

router.post('/forgot-password', authLimiter, (req, res) => {
  const email = str(req.body?.email, 200).toLowerCase();
  const user = db.prepare('SELECT * FROM users WHERE email = ? AND status = ?').get(email, 'active');
  if (user) {
    const token = issueEmailToken(user.id, 'reset', config.tokens.resetMs);
    const url = `${config.appUrl}/redefinir-senha?token=${encodeURIComponent(token)}`;
    sendTokenEmail({ to: user.email, name: user.name, url, kind: 'reset' });
    return res.json({ message: 'Enviamos um link de redefinição válido por 30 minutos.', ...devLink(url) });
  }
  res.json({ message: 'Se este email estiver cadastrado, enviamos um link de redefinição.' });
});

router.post('/reset-password', authLimiter, (req, res) => {
  const password = String(req.body?.password || '');
  if (password.length < 8 || password.length > 72) {
    return res.status(400).json({ error: 'A senha precisa ter entre 8 e 72 caracteres.' });
  }
  const row = consumeEmailToken(String(req.body?.token || ''), 'reset');
  if (!row) return res.status(400).json({ error: 'Link de redefinição inválido ou expirado. Solicite um novo (válido por 30 minutos).' });

  db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(hashPassword(password), row.user_id);
  // Por segurança, encerra todas as sessões existentes
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(row.user_id);
  res.json({ message: 'Senha redefinida com sucesso! Faça login com a nova senha.' });
});

export default router;

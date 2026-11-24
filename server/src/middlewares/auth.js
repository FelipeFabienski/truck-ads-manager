import { db } from '../db.js';
import { config } from '../config.js';
import { generateToken, hashToken } from '../services/crypto.js';

const COOKIE = config.session.cookieName;

export function setSessionCookie(res, token) {
  res.cookie(COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: !config.isDev,
    path: '/',
    maxAge: config.session.absoluteMs,
  });
}

export function clearSessionCookie(res) {
  res.clearCookie(COOKIE, { path: '/', sameSite: 'lax', secure: !config.isDev, httpOnly: true });
}

export function createSessionForUser(userId, { ip = '', userAgent = '' } = {}) {
  const token = generateToken();
  const now = new Date();
  db.prepare(
    `INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, absolute_expires_at, ip, user_agent)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(hashToken(token), userId, now.toISOString(), now.toISOString(), new Date(now.getTime() + config.session.absoluteMs).toISOString(), ip, userAgent);
  return token;
}

export function destroySession(token) {
  db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(hashToken(token));
}

/**
 * Middleware de sessão com renovação deslizante:
 * - inativo por 15 min → expira;
 * - absoluto de 7 dias desde a criação → expira;
 * - cada request autenticado atualiza last_seen e reemite o cookie.
 */
export function requireAuth(req, res, next) {
  const token = req.cookies?.[COOKIE];
  if (!token) return res.status(401).json({ error: 'Não autenticado.' });

  const session = db.prepare('SELECT * FROM sessions WHERE token_hash = ?').get(hashToken(token));
  if (!session) return res.status(401).json({ error: 'Sessão inválida. Faça login novamente.' });

  const now = Date.now();
  const created = Date.parse(session.created_at);
  const lastSeen = Date.parse(session.last_seen_at);

  if (now > Date.parse(session.absolute_expires_at)) {
    db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(session.token_hash);
    return res.status(401).json({ error: 'Sessão expirada (limite de 7 dias). Faça login novamente.' });
  }
  if (now - lastSeen > config.session.idleMs) {
    db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(session.token_hash);
    return res.status(401).json({ error: 'Sessão expirada por inatividade. Faça login novamente.' });
  }

  const user = db
    .prepare('SELECT id, name, email, role, company, phone, avatar_path, timezone, email_verified, plan_id, status, created_at FROM users WHERE id = ?')
    .get(session.user_id);
  if (!user || user.status !== 'active') {
    db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(session.token_hash);
    return res.status(401).json({ error: 'Sessão encerrada.' });
  }

  db.prepare('UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?').run(new Date(now).toISOString(), session.token_hash);

  // Renova o cookie quando o usuário está ativo há mais de 1 minuto (mantém o usuário conectado)
  if (now - lastSeen > config.session.renewThresholdMs) {
    setSessionCookie(res, token);
  }

  req.user = user;
  req.sessionTokenHash = session.token_hash;
  next();
}

/** Restringe rotas de administração. */
export function requireAdmin(req, res, next) {
  if (req.user?.role !== 'admin') {
    return res.status(403).json({ error: 'Apenas o administrador pode acessar esta área.' });
  }
  next();
}

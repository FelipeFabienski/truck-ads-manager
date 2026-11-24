import { db } from '../db.js';
import { config } from '../config.js';

/**
 * Bloqueio progressivo por tentativas erradas de login (por email):
 * 5 falhas → bloqueio de 1 min · 10 → 5 min · 20 → 30 min.
 * A contagem fica em janela de 15 min (ou até o próximo login de sucesso).
 */
const ROW = db.prepare('SELECT * FROM login_lockouts WHERE email = ?');
const UPSERT = db.prepare(`
  INSERT INTO login_lockouts (email, fail_count, window_start, locked_until, last_fail_at)
  VALUES (?, 1, ?, NULL, ?)
  ON CONFLICT(email) DO UPDATE SET last_fail_at = excluded.last_fail_at
`);
const UPDATE = db.prepare(`
  UPDATE login_lockouts
  SET fail_count = ?, locked_until = ?, last_fail_at = ?, window_start = CASE WHEN ? THEN ? ELSE window_start END
  WHERE email = ?
`);
const CLEAR = db.prepare('DELETE FROM login_lockouts WHERE email = ?');

function activeLockUntil(row, now) {
  if (!row?.locked_until) return null;
  const until = Date.parse(row.locked_until);
  return now < until ? until : null;
}

export function checkLock(email) {
  const row = ROW.get(email);
  const now = Date.now();
  const until = activeLockUntil(row, now);
  if (until) {
    return { locked: true, retryAfterSec: Math.ceil((until - now) / 1000), failCount: row.fail_count };
  }
  return { locked: false, retryAfterSec: 0, failCount: row?.fail_count || 0 };
}

/** Registra uma falha. Pode disparar bloqueio conforme os limites progressivos. */
export function recordFailure(email) {
  const row = ROW.get(email);
  const now = new Date();
  const nowMs = now.getTime();

  if (!row) {
    UPSERT.run(email, now.toISOString(), now.toISOString());
    return { locked: false, failCount: 1 };
  }

  const windowExpired = nowMs - Date.parse(row.window_start) > config.loginLock.countWindowMs;
  const failCount = windowExpired ? 1 : row.fail_count + 1;
  const windowStart = windowExpired ? now.toISOString() : row.window_start;

  let lockMinutes = 0;
  for (const t of config.loginLock.thresholds) {
    if (failCount >= t.fails) {
      lockMinutes = t.lockMinutes;
      break;
    }
  }
  const lockedUntil = lockMinutes ? new Date(nowMs + lockMinutes * 60_000).toISOString() : null;

  // SQLite não aceita boolean — usa 1/0
  UPDATE.run(failCount, lockedUntil, now.toISOString(), windowExpired ? 1 : 0, now.toISOString(), email);
  return { locked: !!lockedUntil, failCount, lockMinutes };
}

export function recordSuccess(email) {
  CLEAR.run(email);
}

/** Middleware express para a rota de login. */
export function loginLockGuard(req, res, next) {
  const { email } = req.body || {};
  if (!email) return next();
  const { locked, retryAfterSec } = checkLock(email);
  if (locked) {
    res.set('Retry-After', String(retryAfterSec));
    return res.status(423).json({
      error: `Conta temporariamente bloqueada após ${retryAfterSec > 60 ? `${Math.ceil(retryAfterSec / 60)} minutos` : `${retryAfterSec} segundos`} de tentativas incorretas. Aguarde e tente novamente.`,
    });
  }
  next();
}

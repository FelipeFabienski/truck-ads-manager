import 'dotenv/config';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(__dirname, '..');

function num(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

export const config = {
  env: process.env.NODE_ENV || 'development',
  isDev: (process.env.NODE_ENV || 'development') !== 'production',
  port: num(process.env.PORT, 4000),
  // URL pública do frontend, usada nos links dos emails
  appUrl: process.env.APP_URL || 'http://localhost:5173',

  databasePath: process.env.DATABASE_PATH || path.join(ROOT, 'data', 'facilitador.db'),
  uploadDir: process.env.UPLOAD_DIR || path.join(ROOT, 'uploads'),

  session: {
    cookieName: 'fa_session',
    idleMs: num(process.env.SESSION_IDLE_MINUTES, 15) * 60_000, // expira se inativo por 15 min
    absoluteMs: num(process.env.SESSION_ABSOLUTE_DAYS, 7) * 24 * 60 * 60_000, // máximo de 7 dias
    renewThresholdMs: 60_000, // renova cookie quando idle > 1 min
  },

  // Limite de requisições por minuto (proteção anti-abuso)
  rateLimit: {
    globalMax: num(process.env.RATE_LIMIT_GLOBAL, 300),
    authMax: num(process.env.RATE_LIMIT_AUTH, 20),
    windowMs: num(process.env.RATE_LIMIT_WINDOW_MS, 60_000),
  },

  // Bloqueio progressivo de login: 5 falhas → 1 min, 10 → 5 min, 20 → 30 min
  loginLock: {
    countWindowMs: num(process.env.LOGIN_COUNT_WINDOW_MINUTES, 15) * 60_000,
    thresholds: [
      { fails: 20, lockMinutes: 30 },
      { fails: 10, lockMinutes: 5 },
      { fails: 5, lockMinutes: 1 },
    ],
  },

  tokens: {
    confirmMs: num(process.env.CONFIRM_TOKEN_HOURS, 24) * 60 * 60_000,
    resetMs: num(process.env.RESET_TOKEN_MINUTES, 30) * 60_000,
  },

  encryptionKey: resolveEncryptionKey(),

  smtp: {
    host: process.env.SMTP_HOST || '',
    port: num(process.env.SMTP_PORT, 587),
    user: process.env.SMTP_USER || '',
    pass: process.env.SMTP_PASS || '',
    from: process.env.SMTP_FROM || 'Facilitador de Anúncios <nao-responder@facilitador.local>',
    secure: process.env.SMTP_SECURE === 'true',
  },

  meta: {
    // Versão da Graph API (configurável via META_API_VERSION)
    graphVersion: process.env.META_API_VERSION || process.env.GRAPH_API_VERSION || 'v23.0',
    graphUrl: 'https://graph.facebook.com',
    // Permissões mínimas para uma integração ser considerada apta à publicação
    requiredPermissions: ['ads_management', 'pages_read_engagement', 'pages_manage_ads'],
  },
};

// Chave AES-256: lê do env ou gera/persiste em server/data/.encryption-key (conveniência dev)
function resolveEncryptionKey() {
  if (process.env.ENCRYPTION_KEY && /^[0-9a-fA-F]{64}$/.test(process.env.ENCRYPTION_KEY)) {
    return Buffer.from(process.env.ENCRYPTION_KEY, 'hex');
  }
  const keyFile = path.join(ROOT, 'data', '.encryption-key');
  try {
    if (fs.existsSync(keyFile)) {
      const stored = fs.readFileSync(keyFile, 'utf8').trim();
      if (/^[0-9a-fA-F]{64}$/.test(stored)) return Buffer.from(stored, 'hex');
    }
  } catch {
    /* ignora e recria */
  }
  const key = crypto.randomBytes(32);
  fs.mkdirSync(path.dirname(keyFile), { recursive: true });
  fs.writeFileSync(keyFile, key.toString('hex'), { mode: 0o600 });
  return key;
}

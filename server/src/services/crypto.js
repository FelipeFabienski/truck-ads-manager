import crypto from 'node:crypto';
import { config } from '../config.js';

const KEY = config.encryptionKey;

/** Senha: scrypt nativo do Node (hash salgado). Formato: scrypt$N$salt$hash */
export function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(password.normalize('NFKC'), salt, 64, { N: 16384, r: 8, p: 1 });
  return `scrypt$16384$${salt.toString('hex')}$${hash.toString('hex')}`;
}

export function verifyPassword(password, stored) {
  try {
    const [algo, N, saltHex, hashHex] = stored.split('$');
    if (algo !== 'scrypt') return false;
    const hash = crypto.scryptSync(password.normalize('NFKC'), Buffer.from(saltHex, 'hex'), 64, { N: Number(N), r: 8, p: 1 });
    const expected = Buffer.from(hashHex, 'hex');
    return hash.length === expected.length && crypto.timingSafeEqual(hash, expected);
  } catch {
    return false;
  }
}

/** Tokens de email / sessão: guardamos apenas o SHA-256 do valor aleatório */
export function generateToken() {
  return crypto.randomBytes(32).toString('base64url');
}

export function hashToken(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

/** Token Meta: AES-256-GCM. Saída: base64(iv|tag|ciphertext) */
export function encryptSecret(plaintext) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', KEY, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([iv, tag, ciphertext]).toString('base64');
}

export function decryptSecret(encrypted) {
  try {
    const raw = Buffer.from(encrypted, 'base64');
    const iv = raw.subarray(0, 12);
    const tag = raw.subarray(12, 28);
    const ciphertext = raw.subarray(28);
    const decipher = crypto.createDecipheriv('aes-256-gcm', KEY, iv);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8');
  } catch {
    throw new Error('Falha ao descriptografar credencial — a ENCRYPTION_KEY mudou?');
  }
}

export function maskSecret(plaintext) {
  if (!plaintext) return '';
  if (plaintext.length <= 8) return '••••••••';
  return `${plaintext.slice(0, 4)}••••••••${plaintext.slice(-4)}`;
}

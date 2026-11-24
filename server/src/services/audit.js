import { db } from '../db.js';

/**
 * Registro de auditoria — NUNCA registra tokens, segredos ou conteúdo sensível.
 * Falha de auditoria não derruba a requisição principal.
 */
export function audit({ userId, action, resourceType = '', resourceId = '', status = 'ok', ip = '' }) {
  try {
    db.prepare(
      'INSERT INTO audit_logs (user_id, action, resource_type, resource_id, status, ip_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
    ).run(userId ?? null, action, resourceType, String(resourceId ?? ''), status, ip ?? '', new Date().toISOString());
  } catch (err) {
    console.error('Falha ao registrar auditoria:', err.message);
  }
}

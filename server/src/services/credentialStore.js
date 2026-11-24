import { db } from '../db.js';
import { decryptSecret, encryptSecret, maskSecret } from '../services/crypto.js';

/**
 * Camada de acesso às credenciais Meta com guards de RBAC e status.
 * Sem nenhuma chamada de rede — isolada do MetaAdsService para manter
 * o fluxo "request → banco" separado do fluxo "rede".
 * A descriptografia aqui serve APENAS para mascarar (nunca expor) segredos.
 */
export function getCredentialById(id) {
  return db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(id) || null;
}

export function getOwnCredentialOr403(id, req) {
  const row = getCredentialById(id);
  if (!row) return { error: 404, message: 'Integração não encontrada.' };
  if (row.user_id !== req.user.id) return { error: 403, message: 'Esta integração pertence a outro usuário.' };
  return { row };
}

export function getManageableCredentialOr403(id, req) {
  const row = getCredentialById(id);
  if (!row) return { error: 404, message: 'Integração não encontrada.' };
  if (row.user_id !== req.user.id && req.user.role !== 'admin') {
    return { error: 403, message: 'Apenas o administrador pode gerenciar integrações de outros usuários.' };
  }
  return { row };
}

export function getActiveCredentialForUser(userId) {
  return db.prepare('SELECT * FROM meta_credentials WHERE user_id = ? AND is_active = 1').get(userId) || null;
}

/** Mascara segredos armazenados (descriptografa apenas em memória para o mask). */
function maskStored(encrypted) {
  try {
    return maskSecret(decryptSecret(encrypted));
  } catch {
    return '••••••••';
  }
}

/** Campos do formulário → colunas (ativos podem ficar nulos enquanto pendente). */
export function extractCredentialFields(body) {
  const digits = (v) => {
    const s = String(v ?? '').replace(/\D/g, '');
    return s || null;
  };
  const actId = (v) => {
    const s = String(v ?? '').replace(/^act_/i, '').replace(/\D/g, '');
    return s ? `act_${s}` : null;
  };
  return {
    name: String(body?.name ?? '').trim().slice(0, 80),
    adAccountId: body?.adAccountId !== undefined ? actId(body.adAccountId) : undefined,
    pageId: body?.pageId !== undefined ? digits(body.pageId) : undefined,
    instagramActorId: body?.instagramActorId !== undefined ? digits(body.instagramActorId) : undefined,
    businessId: body?.businessId !== undefined ? digits(body.businessId) : undefined,
    appId: body?.appId !== undefined ? digits(body.appId) : undefined,
    whatsappNumber: String(body?.whatsappNumber ?? '').trim().slice(0, 30),
  };
}

/**
 * Criar credencial: token criptografado (AES-256-GCM) antes do INSERT.
 * Status inicial sempre "pending"; identificação por dono (user_id).
 */
export function createCredential({ userId, name, accessToken, fields = {}, appSecret = '' }) {
  const now = new Date().toISOString();
  const info = db
    .prepare(
      'INSERT INTO meta_credentials (user_id, name, access_token_enc, ad_account_id, page_id, instagram_actor_id, business_id, app_id, app_secret_enc, whatsapp_number, validation_status, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .run(
      userId,
      name,
      encryptSecret(accessToken),
      fields.adAccountId ?? null,
      fields.pageId ?? null,
      fields.instagramActorId ?? null,
      fields.businessId ?? null,
      fields.appId ?? null,
      appSecret ? encryptSecret(appSecret) : null,
      fields.whatsappNumber ?? '',
      'pending',
      0,
      now,
      now
    );
  return db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(info.lastInsertRowid);
}

/** Importação inicial do admin: credencial pendente, sem ativos, sem validação. */
export function insertAdminCredential(userId, name, accessToken) {
  const now = new Date().toISOString();
  const info = db
    .prepare(
      'INSERT INTO meta_credentials (user_id, name, access_token_enc, whatsapp_number, validation_status, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .run(userId, name, encryptSecret(accessToken), '', 'pending', 0, now, now);
  return db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(info.lastInsertRowid);
}

/**
 * Atualiza campos editáveis. Troca de token/appSecret/ativos força revalidação
 * (status volta a "pending"). Campos undefined mantêm o valor atual.
 */
export function updateCredentialFields(credRow, fields, { accessToken = '', appSecret } = {}) {
  const assetsChanged =
    (fields.adAccountId !== undefined && fields.adAccountId !== credRow.ad_account_id) ||
    (fields.pageId !== undefined && fields.pageId !== credRow.page_id) ||
    (fields.instagramActorId !== undefined && fields.instagramActorId !== credRow.instagram_actor_id) ||
    (fields.businessId !== undefined && fields.businessId !== credRow.business_id);
  const needsRevalidation = !!accessToken || assetsChanged || appSecret !== undefined;
  const newStatus = needsRevalidation ? 'pending' : credRow.validation_status;
  const now = new Date().toISOString();

  db.prepare(
    'UPDATE meta_credentials SET name = ?, access_token_enc = ?, ad_account_id = ?, page_id = ?, instagram_actor_id = ?, business_id = ?, app_id = ?, app_secret_enc = ?, whatsapp_number = ?, validation_status = ?, updated_at = ? WHERE id = ?'
  ).run(
    fields.name || credRow.name,
    accessToken ? encryptSecret(accessToken) : credRow.access_token_enc,
    fields.adAccountId !== undefined ? fields.adAccountId : credRow.ad_account_id,
    fields.pageId !== undefined ? fields.pageId : credRow.page_id,
    fields.instagramActorId !== undefined ? fields.instagramActorId : credRow.instagram_actor_id,
    fields.businessId !== undefined ? fields.businessId : credRow.business_id,
    fields.appId !== undefined ? fields.appId : credRow.app_id,
    appSecret !== undefined ? appSecret : credRow.app_secret_enc,
    fields.whatsappNumber !== undefined ? fields.whatsappNumber : credRow.whatsapp_number,
    newStatus,
    now,
    credRow.id
  );
  return { needsRevalidation, updated: db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(credRow.id) };
}

/** Ativa a credencial para o dono (apenas uma ativa por usuário). */
export function activateCredentialForOwner(credRow) {
  const activate = db.transaction(() => {
    db.prepare('UPDATE meta_credentials SET is_active = 0 WHERE user_id = ?').run(credRow.user_id);
    db.prepare('UPDATE meta_credentials SET is_active = 1, updated_at = ? WHERE id = ?').run(new Date().toISOString(), credRow.id);
  });
  activate();
}

/** Habilita/desabilita (is_active = 0 → status "Desativado" na UI). */
export function setCredentialEnabled(credRow, enabled) {
  db.prepare('UPDATE meta_credentials SET is_active = ?, updated_at = ? WHERE id = ?').run(
    enabled ? 1 : 0, new Date().toISOString(), credRow.id
  );
}

/** Deleta a credencial (campanhas mantêm histórico com credential_id = NULL). */
export function deleteCredential(credRow) {
  db.prepare('DELETE FROM meta_credentials WHERE id = ?').run(credRow.id);
}

/**
 * Atualiza o resultado de uma validação (chamado após validateStoredCredential).
 */
export function applyValidationResult(credId, { status, tokenExpiresAt = null }) {
  const now = new Date().toISOString();
  db.prepare(
    'UPDATE meta_credentials SET validation_status = ?, token_expires_at = ?, last_validated_at = ?, updated_at = ? WHERE id = ?'
  ).run(status, tokenExpiresAt, now, now, credId);
}

/** Marca falha de validação (sem mexer em token_expires_at). */
export function applyValidationFailure(credId, status) {
  const now = new Date().toISOString();
  db.prepare('UPDATE meta_credentials SET validation_status = ?, last_validated_at = ?, updated_at = ? WHERE id = ?').run(
    status, now, now, credId
  );
}

/**
 * View pública da credencial: JAMAIS inclui access_token_enc/app_secret_enc.
 * Segredos aparecem apenas mascarados (ex: EAAG••••••••x9ZD).
 */
export function publicCredentialView(row, options = {}) {
  const includeUser = options.includeUser === true;
  const base = {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    adAccountId: row.ad_account_id || null,
    pageId: row.page_id || null,
    instagramActorId: row.instagram_actor_id || null,
    businessId: row.business_id || null,
    appId: row.app_id || null,
    hasAppSecret: !!row.app_secret_enc,
    appSecretMasked: row.app_secret_enc ? maskStored(row.app_secret_enc) : null,
    tokenMasked: maskStored(row.access_token_enc),
    whatsappNumber: row.whatsapp_number || '',
    tokenExpiresAt: row.token_expires_at || null,
    lastValidatedAt: row.last_validated_at || null,
    validationStatus: row.validation_status, // pending|connected|token_expired|insufficient_permissions|connection_error
    isActive: !!row.is_active,
    createdAt: row.created_at,
    updatedAt: row.updated_at || row.created_at,
  };
  if (includeUser) {
    const owner = db.prepare('SELECT id, name, email FROM users WHERE id = ?').get(row.user_id);
    base.owner = owner ? { id: owner.id, name: owner.name, email: owner.email } : null;
  }
  return base;
}

/**
 * Resolve a credencial que uma campanha usará para publicar, com todas as
 * garantias: propriedade do dono da campanha (ou admin), habilitada e validada.
 * Lança objetos { status, message } prontos para as rotas.
 */
export function resolveCredentialForCampaign(campaignRow, requester) {
  const credId = campaignRow.credential_id || null;
  let row = null;
  if (credId) {
    row = getCredentialById(credId);
    if (row && row.user_id !== campaignRow.user_id && requester.role !== 'admin') {
      throw { status: 403, message: 'A integração vinculada pertence a outro usuário.' };
    }
  }
  if (!row) {
    row = getActiveCredentialForUser(campaignRow.user_id);
  }
  if (!row) {
    throw {
      status: 409,
      message: 'Nenhuma integração Meta habilitada para este usuário. Configure e valide uma integração em "Integrações".',
    };
  }
  if (!row.is_active) {
    throw { status: 409, message: 'A integração vinculada está desativada. Habilite-a em "Integrações" antes de publicar.' };
  }
  if (row.validation_status !== 'connected') {
    const labels = {
      pending: 'Pendente de validação',
      token_expired: 'Token expirado',
      insufficient_permissions: 'Permissões insuficientes',
      connection_error: 'Erro de conexão',
    };
    throw {
      status: 409,
      message: `A integração não pode publicar: status "${labels[row.validation_status] || row.validation_status}". Use "Validar integração" em Integrações.`,
    };
  }
  return row;
}

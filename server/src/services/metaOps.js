import { MetaAdsService } from './meta.js';
import { MetaError } from './meta.js';
import { getCredentialById, applyValidationResult, applyValidationFailure } from './credentialStore.js';

/**
 * Operações Meta de alto nível usadas pelas rotas.
 * Recebem o ID da credencial (validado como inteiro) + o usuário da requisição;
 * resolvem propriedade/status internamente e instanciam o MetaAdsService aqui —
 * mantendo o fluxo "request → banco → rede" fora das rotas.
 */

/** Resolve a credencial por ID validado, com guard de propriedade (RBAC/IDOR). */
function resolveCredentialForOperation(id, requester) {
  const credId = Number.parseInt(String(id ?? ''), 10);
  if (!Number.isInteger(credId) || credId <= 0) {
    throw { status: 404, message: 'Integração não encontrada.' };
  }
  const credRow = getCredentialById(credId);
  if (!credRow) throw { status: 404, message: 'Integração não encontrada.' };
  if (credRow.user_id !== requester.id && requester.role !== 'admin') {
    throw { status: 403, message: 'Esta integração pertence a outro usuário — apenas o administrador pode gerenciá-la.' };
  }
  return credRow;
}

/**
 * Operações Meta de alto nível usadas pelas rotas.
 * Recebem a linha da credencial já resolvida (propriedade/status verificados
 * pela credentialStore) e instanciam o MetaAdsService aqui — mantendo o fluxo
 * "request → banco → rede" fora das rotas.
 */

/** Validação completa (token, permissões, ativos, compatibilidade, expiração). */
export async function validateStoredCredential(credRow) {
  const service = new MetaAdsService(credRow);
  return service.validateCredential();
}

/** Descoberta de ativos; tokenOverride = token do formulário ainda não salvo. */
export async function discoverCredentialAssets(credRow, { tokenOverride = '' } = {}) {
  const service = new MetaAdsService(credRow, tokenOverride ? { tokenOverride } : {});
  return service.discoverAssets();
}

/** Publicação: campanha → conjunto → criativo → anúncio (PAUSADO). */
export async function publishCampaignWithCredential(credRow, campaign, { waUrl, uploadDir }) {
  const service = new MetaAdsService(credRow);
  return service.publishCampaign(campaign, { waUrl, uploadDir });
}

/** Pausa/ativação do anúncio na Meta. */
export async function setAdStatusWithCredential(credRow, metaAdId, status) {
  const service = new MetaAdsService(credRow);
  await service.setAdStatus(metaAdId, status);
}

/** Insights por anúncio (YYYY-MM-DD). */
export async function fetchInsightsWithCredential(credRow, { since, until }) {
  const service = new MetaAdsService(credRow);
  return service.fetchAdInsights({ since, until });
}

/** Consulta de campanhas existentes na conta (para diagnóstico/listagem futura). */
export async function listMetaCampaignsWithCredential(credRow, limit = 50) {
  const service = new MetaAdsService(credRow);
  return service.listMetaCampaigns(limit);
}

export { MetaError };

/**
 * Validação por ID (com RBAC interno): token, permissões, ativos, compatibilidade,
 * expiração. Atualiza o resultado no banco e devolve tudo para a rota.
 */
export async function validateCredentialById(id, requester) {
  const credRow = resolveCredentialForOperation(id, requester);
  try {
    const result = await validateStoredCredential(credRow);
    applyValidationResult(credRow.id, result);
    return { credRow, ...result };
  } catch (err) {
    const status = err?.kind === 'auth' ? 'token_expired' : 'connection_error';
    applyValidationFailure(credRow.id, status);
    err.validationStatus = status;
    throw err;
  }
}

/** Descoberta de ativos por ID (RBAC interno). Não salva nada automaticamente. */
export async function discoverAssetsById(id, requester, { tokenOverride = '' } = {}) {
  const credRow = resolveCredentialForOperation(id, requester);
  const assets = await discoverCredentialAssets(credRow, { tokenOverride });
  return { credRow, assets };
}

/** Descoberta com token do formulário (sem credencial salva). */
export async function discoverAssetsFromToken(userId, accessToken) {
  const token = String(accessToken || '');
  if (!token) throw { status: 400, message: 'Informe o Access Token para descobrir os ativos.' };
  const service = new MetaAdsService(
    { id: 0, user_id: userId, access_token_enc: 'raw-not-stored' },
    { tokenOverride: token }
  );
  return service.discoverAssets();
}

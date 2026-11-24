import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { config } from '../config.js';

/**
 * Descriptografia AES-256-GCM local ao serviço de rede: mantém o módulo de
 * criptografia geral (crypto.js) fora de qualquer caminho que faça fetch,
 * de modo que segredos só são decifrados DENTRO do serviço da Meta.
 * Formato idêntico a crypto.js: base64(iv[12] | tag[16] | ciphertext).
 */
function decryptInMemory(encrypted) {
  const raw = Buffer.from(String(encrypted), 'base64');
  const iv = raw.subarray(0, 12);
  const tag = raw.subarray(12, 28);
  const ciphertext = raw.subarray(28);
  const decipher = crypto.createDecipheriv('aes-256-gcm', config.encryptionKey, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8');
}

/**
 * MetaAdsService — integração centralizada com a Meta Marketing API (BYOT).
 *
 * Regras de segurança:
 * - O Access Token é descriptografado SOMENTE em memória, por operação.
 * - Toda requisição usa o cabeçalho Authorization: Bearer.
 * - appsecret_proof (HMAC-SHA256) é enviado quando a integração tem App Secret.
 * - URL sempre https com host em allowlist fixa (graph.facebook.com); loopback,
 *   localhost, IPs privados e endereços reservados são rejeitados.
 * - Erros da Meta são classificados (token expirado, permissões, rate limit).
 * - Nenhum log contém token ou segredo.
 *
 * Toda comunicação acontece somente dentro de ações explicitamente iniciadas
 * pelo usuário (validar, descobrir ativos, publicar…). Nada roda no startup.
 */

const GRAPH_HOSTS = new Set(['graph.facebook.com']);

export class MetaError extends Error {
  /**
   * @param {string} message mensagem amigável em PT-BR
   * @param {number|null} code código de erro da Graph API
   * @param {'auth'|'permission'|'rate_limit'|'network'|'config'|'error'} kind classificação
   */
  constructor(message, code = null, kind = 'error') {
    super(message);
    this.name = 'MetaError';
    this.metaCode = code;
    this.kind = kind;
  }
}

/** Host allowlist + bloqueio de loopback/privados/reservados (anti-SSRF). */
function assertSafeGraphUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    throw new MetaError('URL da Graph API inválida.', null, 'config');
  }
  if (parsed.protocol !== 'https:') {
    throw new MetaError('A comunicação com a Meta deve usar HTTPS.', null, 'config');
  }
  const host = parsed.hostname.toLowerCase();
  if (!GRAPH_HOSTS.has(host)) {
    throw new MetaError('Host da Graph API não permitido.', null, 'config');
  }
}

/** Caminho da Graph API: apenas identificadores seguros (sem '..', sem query). */
function assertSafeGraphPath(urlPath) {
  const clean = String(urlPath).replace(/^\/+/, '');
  if (!/^[A-Za-z0-9_/.-]+$/.test(clean) || clean.includes('..')) {
    throw new MetaError('Caminho de API inválido.', null, 'config');
  }
  return clean;
}

/** Classifica a resposta de erro da Graph API. */
function classifyGraphError(body, httpStatus) {
  const err = body?.error || {};
  const code = err.code;
  const subcode = err.error_subcode;
  const type = err.type;
  if (code === 190 || (type === 'OAuthException' && [463, 467, 102].includes(subcode))) {
    return { kind: 'auth', message: 'Token expirado, revogado ou inválido.' };
  }
  if ([4, 9, 17, 32, 613].includes(code)) {
    return { kind: 'rate_limit', message: 'Limite de requisições da Meta atingido — aguarde alguns minutos.' };
  }
  if (code === 10 || code === 3 || (code >= 200 && code <= 299)) {
    return { kind: 'permission', message: 'Permissões insuficientes para esta operação.' };
  }
  if (httpStatus >= 500) {
    return { kind: 'network', message: 'A Meta reportou instabilidade — tente novamente em instantes.' };
  }
  return {
    kind: 'error',
    message: err.error_user_msg || err.message || `Erro da Graph API (HTTP ${httpStatus})`,
  };
}

/** Formata data para o padrão de tempo da Meta (ISO sem milissegundos, offset +0000). */
function metaTime(date) {
  return new Date(date).toISOString().replace(/\.\d{3}Z$/, '+0000');
}

/**
 * Serviço instanciado POR credencial: descriptografa o token no construtor
 * (somente memória) e expõe operações reais da Marketing API.
 */
export class MetaAdsService {
  /**
   * @param {object} credRow linha de meta_credentials (tokens ainda criptografados)
   * @param {{tokenOverride?: string}} options token em claro ainda não salvo (uso
   *        exclusivo da descoberta a partir do formulário); nunca logado
   */
  constructor(credRow, options = {}) {
    if (!credRow?.access_token_enc) {
      throw new MetaError('Credencial sem Access Token armazenado.', null, 'config');
    }
    this.credentialId = credRow.id;
    this.userId = credRow.user_id;
    this.adAccountId = credRow.ad_account_id || null; // formato act_ID
    this.pageId = credRow.page_id || null;
    this.instagramActorId = credRow.instagram_actor_id || null;
    this.businessId = credRow.business_id || null;
    this.appId = credRow.app_id || null;
    this.whatsappNumber = credRow.whatsapp_number || '';
    // Token: override explícito do formulário OU descriptografado somente em memória
    this.token = options.tokenOverride || decryptInMemory(credRow.access_token_enc);
    this.appSecret = credRow.app_secret_enc ? decryptInMemory(credRow.app_secret_enc) : null;
  }

  #proof() {
    if (!this.appSecret) return null;
    return crypto.createHmac('sha256', this.appSecret).update(this.token).digest('hex');
  }

  /** Requisição base: Bearer header + appsecret_proof + timeout + classificação de erros. */
  async request(method, urlPath, { params = {}, body = null, form = null } = {}) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === '') continue;
      search.set(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
    }
    const proof = this.#proof();
    if (proof) search.set('appsecret_proof', proof);

    const pathClean = assertSafeGraphPath(urlPath);
    const url = `${config.meta.graphUrl}/${config.meta.graphVersion}/${pathClean}`;
    const fullUrl = search.toString() ? `${url}?${search.toString()}` : url;
    assertSafeGraphUrl(fullUrl);

    const headers = { Authorization: `Bearer ${this.token}` };
    let payload;
    if (form) {
      payload = form;
    } else if (body) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(fullUrl, { method, headers, body: payload, signal: AbortSignal.timeout(30_000) });
    } catch (netErr) {
      if (netErr?.name === 'TimeoutError' || netErr?.name === 'AbortError') {
        throw new MetaError('Tempo esgotado ao falar com a Meta (timeout de 30s).', null, 'network');
      }
      throw new MetaError(`Falha de conexão com a Meta (${netErr.message}).`, null, 'network');
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error) {
      const { kind, message } = classifyGraphError(data, res.status);
      throw new MetaError(message, data.error?.code ?? null, kind);
    }
    return data;
  }

  // ------------------------------------------------------------------
  // Consultas de identidade/ativos (sempre iniciadas pelo usuário)
  // ------------------------------------------------------------------

  /** GET /me — identidade do token. */
  async getMe() {
    return this.request('GET', 'me', { params: { fields: 'id,name,link' } });
  }

  /** GET /me/permissions — permissões concedidas ao token. */
  async getPermissions() {
    const data = await this.request('GET', 'me/permissions', { params: { limit: 200 } });
    return (data.data || [])
      .filter((p) => p.status === 'granted')
      .map((p) => p.permission);
  }

  /** GET /me/adaccounts — contas de anúncios acessíveis. */
  async listAdAccounts() {
    const data = await this.request('GET', 'me/adaccounts', {
      params: { fields: 'id,account_id,name,currency,account_status', limit: 200 },
    });
    return (data.data || []).map((a) => ({
      id: a.id, // act_ID
      accountId: a.account_id,
      name: a.name,
      currency: a.currency,
      accountStatus: a.account_status, // 1 = ativa
    }));
  }

  /** GET /me/accounts — páginas do Facebook (+ Instagram profissional vinculado). */
  async listPages() {
    const data = await this.request('GET', 'me/accounts', {
      params: { fields: 'id,name,instagram_business_account{id,username}', limit: 200 },
    });
    return (data.data || []).map((p) => ({
      id: p.id,
      name: p.name,
      instagram: p.instagram_business_account
        ? { id: p.instagram_business_account.id, username: p.instagram_business_account.username }
        : null,
    }));
  }

  /** GET /me/businesses — portfólios empresariais acessíveis. */
  async listBusinesses() {
    const data = await this.request('GET', 'me/businesses', {
      params: { fields: 'id,name,vertical', limit: 200 },
    });
    return (data.data || []).map((b) => ({ id: b.id, name: b.name, vertical: b.vertical }));
  }

  /** GET /{ig-id} — conta do Instagram vinculada. */
  async getInstagramAccount(igId) {
    if (!/^\d{1,30}$/.test(String(igId))) throw new MetaError('Instagram Account ID inválido.', null, 'config');
    return this.request('GET', igId, { params: { fields: 'id,username,followers_count' } });
  }

  /** GET /act_{id} — nome, moeda e status da conta de anúncios. */
  async getAdAccount(adAccountId) {
    const id = String(adAccountId || this.adAccountId || '').replace(/^act_/i, '');
    if (!/^\d{1,30}$/.test(id)) throw new MetaError('Ad Account ID inválido.', null, 'config');
    return this.request('GET', `act_${id}`, { params: { fields: 'id,name,currency,account_status' } });
  }

  /** GET /{page-id} — página do Facebook (+ Instagram vinculado). */
  async getPage(pageId) {
    const id = String(pageId || this.pageId || '');
    if (!/^\d{1,30}$/.test(id)) throw new MetaError('Page ID inválido.', null, 'config');
    return this.request('GET', id, { params: { fields: 'id,name,instagram_business_account{id,username}' } });
  }

  /**
   * Descoberta automática de ativos do token (contas de anúncios, páginas,
   * Instagram e portfólios). Chamada apenas pelo botão "Descobrir ativos".
   */
  async discoverAssets() {
    const [adAccounts, pages, businesses] = await Promise.allSettled([
      this.listAdAccounts(),
      this.listPages(),
      this.listBusinesses(),
    ]);
    return {
      adAccounts: adAccounts.status === 'fulfilled' ? adAccounts.value : null,
      pages: pages.status === 'fulfilled' ? pages.value : null,
      businesses: businesses.status === 'fulfilled' ? businesses.value : null,
      errors: [
        adAccounts.status === 'rejected' ? `Contas de anúncios: ${adAccounts.reason.message}` : null,
        pages.status === 'rejected' ? `Páginas: ${pages.reason.message}` : null,
        businesses.status === 'rejected' ? `Portfólios: ${businesses.reason.message}` : null,
      ].filter(Boolean),
    };
  }

  /**
   * Validação completa da integração. Não considera a integração "conectada"
   * apenas por um HTTP 200: exige as permissões mínimas e confere compatibilidade
   * entre os ativos informados. Devolve { status, checks, tokenExpiresAt }.
   */
  async validateCredential() {
    const checks = [];
    let tokenExpiresAt = null;

    // 1. Identidade do token
    let me = null;
    try {
      me = await this.getMe();
      checks.push({ key: 'token', label: 'Access Token', ok: true, detail: `Válido — conectado como "${me.name || me.id}"` });
    } catch (err) {
      checks.push({ key: 'token', label: 'Access Token', ok: false, detail: err.message });
      const status = err.kind === 'auth' ? 'token_expired' : 'connection_error';
      return { status, checks, tokenExpiresAt: null };
    }

    // 2. Permissões concedidas vs. mínimas exigidas
    try {
      const granted = await this.getPermissions();
      const missing = config.meta.requiredPermissions.filter((p) => !granted.includes(p));
      if (missing.length) {
        checks.push({
          key: 'permissions', label: 'Permissões', ok: false,
          detail: `Faltando: ${missing.join(', ')}`,
        });
        return { status: 'insufficient_permissions', checks, tokenExpiresAt };
      }
      checks.push({ key: 'permissions', label: 'Permissões', ok: true, detail: `${granted.length} concedidas (inclui as obrigatórias)` });
    } catch (err) {
      checks.push({ key: 'permissions', label: 'Permissões', ok: false, detail: err.message });
      return { status: err.kind === 'auth' ? 'token_expired' : 'connection_error', checks, tokenExpiresAt };
    }

    // 3. Expiração do token (quando App ID + App Secret estão configurados)
    if (this.appId && this.appSecret) {
      try {
        const debug = await this.request('GET', 'debug_token', {
          params: {
            input_token: this.token,
            access_token: `${this.appId}|${this.appSecret}`,
          },
        });
        const info = debug?.data || {};
        if (info.is_valid === false) {
          checks.push({ key: 'expiry', label: 'Validade do token', ok: false, detail: 'debug_token reportou token inválido' });
          return { status: 'token_expired', checks, tokenExpiresAt };
        }
        if (info.expires_at && Number(info.expires_at) > 0) {
          tokenExpiresAt = new Date(Number(info.expires_at) * 1000).toISOString();
          const days = Math.max(0, Math.round((Date.parse(tokenExpiresAt) - Date.now()) / 86_400_000));
          checks.push({ key: 'expiry', label: 'Validade do token', ok: days > 0, detail: days > 0 ? `Expira em ~${days} dia(s)` : 'Já expirou' });
          if (days <= 0) return { status: 'token_expired', checks, tokenExpiresAt };
        } else {
          checks.push({ key: 'expiry', label: 'Validade do token', ok: true, detail: 'Sem data de expiração (longa duração/sistema)' });
        }
        if (Array.isArray(info.granular_scopes) && info.granular_scopes.length) {
          checks.push({ key: 'scopes', label: 'Escopos granulares', ok: true, detail: info.granular_scopes.map((s) => s.scope).join(', ') });
        }
      } catch (err) {
        // debug_token é informativo: sem app creds ou com erro, segue sem expiração
        checks.push({ key: 'expiry', label: 'Validade do token', ok: true, detail: `Não verificado (${err.message})` });
      }
    } else {
      checks.push({ key: 'expiry', label: 'Validade do token', ok: true, detail: 'Configure App ID + App Secret para detectar expiração' });
    }

    // 4. Conta de anúncios informada: existente, acessível e compatível
    if (this.adAccountId) {
      try {
        const acc = await this.getAdAccount(this.adAccountId);
        const active = acc.account_status === 1;
        checks.push({
          key: 'adAccount', label: 'Conta de anúncios', ok: true,
          detail: `${acc.name || acc.id} · ${acc.currency || '?'} · ${active ? 'conta ativa' : `conta inativa (status ${acc.account_status}) — publicação exige conta ativa`}`,
        });
      } catch (err) {
        checks.push({ key: 'adAccount', label: 'Conta de anúncios', ok: false, detail: err.message });
        return { status: err.kind === 'auth' ? 'token_expired' : err.kind === 'permission' ? 'insufficient_permissions' : 'connection_error', checks, tokenExpiresAt };
      }
    } else {
      checks.push({ key: 'adAccount', label: 'Conta de anúncios', ok: false, detail: 'Não informada — use "Descobrir ativos" ou preencha manualmente' });
    }

    // 5. Página do Facebook informada
    let pageInstagram = null;
    if (this.pageId) {
      try {
        const page = await this.getPage(this.pageId);
        pageInstagram = page.instagram_business_account?.id || null;
        checks.push({ key: 'page', label: 'Página do Facebook', ok: true, detail: `${page.name || page.id}${pageInstagram ? ' · Instagram vinculado' : ''}` });
      } catch (err) {
        checks.push({ key: 'page', label: 'Página do Facebook', ok: false, detail: err.message });
        return { status: err.kind === 'auth' ? 'token_expired' : err.kind === 'permission' ? 'insufficient_permissions' : 'connection_error', checks, tokenExpiresAt };
      }
    } else {
      checks.push({ key: 'page', label: 'Página do Facebook', ok: false, detail: 'Não informada — obrigatória para publicar' });
    }

    // 6. Compatibilidade Instagram x Página
    if (this.instagramActorId) {
      if (pageInstagram && pageInstagram !== this.instagramActorId) {
        checks.push({
          key: 'instagram', label: 'Instagram', ok: false,
          detail: `A conta informada não é a vinculada à página (esperado ${pageInstagram})`,
        });
        return { status: 'insufficient_permissions', checks, tokenExpiresAt };
      }
      try {
        const ig = await this.getInstagramAccount(this.instagramActorId);
        checks.push({ key: 'instagram', label: 'Instagram', ok: true, detail: ig.username ? `@${ig.username}` : ig.id });
      } catch (err) {
        checks.push({ key: 'instagram', label: 'Instagram', ok: false, detail: err.message });
        return { status: err.kind === 'auth' ? 'token_expired' : err.kind === 'permission' ? 'insufficient_permissions' : 'connection_error', checks, tokenExpiresAt };
      }
    }

    // 7. Portfólio empresarial informado: precisa estar entre os acessíveis
    if (this.businessId) {
      try {
        const businesses = await this.listBusinesses();
        const ok = businesses.some((b) => b.id === this.businessId);
        checks.push({
          key: 'business', label: 'Portfólio empresarial', ok,
          detail: ok ? 'Acessível por este token' : 'Não está entre os portfólios acessíveis por este token',
        });
        if (!ok) return { status: 'insufficient_permissions', checks, tokenExpiresAt };
      } catch (err) {
        checks.push({ key: 'business', label: 'Portfólio empresarial', ok: false, detail: err.message });
      }
    }

    const allCriticalOk = checks.every((c) => c.ok);
    return { status: allCriticalOk ? 'connected' : 'connection_error', checks, tokenExpiresAt };
  }

  // ------------------------------------------------------------------
  // Campanhas / anúncios
  // ------------------------------------------------------------------

  /** GET act/campaigns — consulta de campanhas existentes na conta. */
  async listMetaCampaigns(limit = 50) {
    const data = await this.request('GET', `${this.adAccountId}/campaigns`, {
      params: { fields: 'id,name,status,objective,created_time', limit },
    });
    return data.data || [];
  }

  /**
   * Upload das fotos como imagens de anúncio → image_hash.
   * O caminho resolvido deve permanecer dentro do diretório de uploads.
   */
  async uploadAdImages(photoPaths, uploadDir) {
    const rootResolved = path.resolve(uploadDir);
    const hashes = [];
    for (const relPath of photoPaths.slice(0, 6)) {
      const abs = path.resolve(uploadDir, String(relPath));
      if (abs !== rootResolved && !abs.startsWith(rootResolved + path.sep)) {
        throw new MetaError('Caminho de foto inválido.', null, 'config');
      }
      if (!/^[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp)$/i.test(path.basename(abs))) {
        throw new MetaError('Arquivo de foto inválido.', null, 'config');
      }
      const buffer = fs.readFileSync(abs);
      const filename = path.basename(abs);
      const form = new FormData();
      form.append('filename', new Blob([buffer]), filename);
      const res = await this.request('POST', `${this.adAccountId}/adimages`, { form });
      const img = res?.images?.[filename];
      if (!img?.hash) throw new MetaError('Falha ao enviar imagem para a Meta.', null, 'error');
      hashes.push(img.hash);
    }
    return hashes;
  }

  /** Interesses do formulário → IDs de targeting (best effort). */
  async resolveInterestIds(interests) {
    if (!interests?.length) return [];
    const ids = [];
    for (const term of interests.slice(0, 10)) {
      try {
        const res = await this.request('GET', `${this.adAccountId}/targetingsearch`, {
          params: { q: term, limit: 1, type: 'adinterest' },
        });
        if (res?.data?.[0]?.id) ids.push({ id: res.data[0].id, name: res.data[0].name });
      } catch {
        /* interesse não resolvido — segue sem ele */
      }
    }
    return ids;
  }

  /** Detecta (best effort) o WhatsApp Business Account vinculado à página. */
  async detectPageWhatsAppId() {
    if (!this.pageId) return null;
    try {
      const page = await this.request('GET', this.pageId, {
        params: { fields: 'whatsapp_business_account_id' },
      });
      return page?.whatsapp_business_account_id || null;
    } catch {
      return null;
    }
  }

  /**
   * Publica a campanha completa na Meta: campanha → conjunto (budget, segmentação,
   * WhatsApp) → criativo → anúncio PAUSADO. Retorna os IDs criados.
   */
  async publishCampaign(campaign, { waUrl, uploadDir }) {
    if (!this.adAccountId) throw new MetaError('A integração não tem Ad Account ID configurado.', null, 'config');
    if (!this.pageId) throw new MetaError('A integração não tem Page ID configurado — obrigatório para publicar.', null, 'config');
    if (!campaign.photos?.length) throw new MetaError('A campanha precisa de pelo menos uma foto.', null, 'config');

    const interestIds = await this.resolveInterestIds(campaign.interests || []);
    if ((campaign.interests || []).length && !interestIds.length) {
      throw new MetaError('Nenhum dos interesses informados pôde ser resolvido na conta de anúncios.', null, 'error');
    }

    const campaignName = `${campaign.product_name} — ${new Date().toLocaleDateString('pt-BR')}`;

    // 1. Campanha (criada PAUSADA; a ativação é explícita do usuário)
    const campaignRes = await this.request('POST', `${this.adAccountId}/campaigns`, {
      body: { name: campaignName, objective: 'OUTCOME_ENGAGEMENT', status: 'PAUSED', special_ad_categories: [] },
    });

    // 2. Conjunto de anúncios: orçamento, duração, segmentação, destino WhatsApp
    const dailyBudgetCents = Math.round(Number(campaign.daily_budget) * 100);
    const endTime = metaTime(Date.now() + Number(campaign.duration_days) * 86_400_000);
    const genders = campaign.gender === 'male' ? [1] : campaign.gender === 'female' ? [2] : [1, 2];
    const targeting = {
      geo_locations: { countries: ['BR'] },
      age_min: campaign.age_min,
      age_max: campaign.age_max,
      genders,
      ...(interestIds.length ? { flexible_spec: [{ interests: interestIds }] } : {}),
    };
    const promotedObject = { page_id: this.pageId };
    if (this.instagramActorId) promotedObject.instagram_actor_id = this.instagramActorId;
    const wabaId = await this.detectPageWhatsAppId();
    if (wabaId) promotedObject.whatsapp_business_account_id = wabaId;

    const adsetRes = await this.request('POST', `${this.adAccountId}/adsets`, {
      body: {
        name: `${campaignName} — Conjunto`,
        campaign_id: campaignRes.id,
        daily_budget: dailyBudgetCents,
        billing_event: 'IMPRESSIONS',
        optimization_goal: 'REACH',
        destination_type: 'WHATSAPP_MESSAGE',
        promoted_object: promotedObject,
        targeting,
        end_time: endTime,
        status: 'PAUSED',
      },
    });

    // 3. Criativo: foto + texto manual + link wa.me + CTA WhatsApp
    const [imageHash] = await this.uploadAdImages(campaign.photos, uploadDir);
    const creativeRes = await this.request('POST', `${this.adAccountId}/adcreatives`, {
      body: {
        name: `${campaignName} — Criativo`,
        object_story_spec: {
          page_id: this.pageId,
          ...(this.instagramActorId ? { instagram_actor_id: this.instagramActorId } : {}),
          link_data: {
            message: campaign.ad_text,
            link: waUrl,
            name: campaign.title,
            image_hash: imageHash,
            call_to_action: { type: 'WHATSAPP_MESSAGE', value: { link: waUrl } },
          },
        },
      },
    });

    // 4. Anúncio (sempre PAUSADO — ativação explícita do usuário)
    const adRes = await this.request('POST', `${this.adAccountId}/ads`, {
      body: {
        name: `${campaignName} — Anúncio`,
        adset_id: adsetRes.id,
        creative: { creative_id: creativeRes.id },
        status: 'PAUSED',
      },
    });

    return { metaCampaignId: campaignRes.id, metaAdsetId: adsetRes.id, metaAdId: adRes.id };
  }

  /** PAUSED/ACTIVE em um anúncio existente. */
  async setAdStatus(metaAdId, status) {
    if (!/^\d{1,30}$/.test(String(metaAdId))) throw new MetaError('ID de anúncio inválido.', null, 'config');
    await this.request('POST', metaAdId, { body: { status } });
  }

  /** Insights por anúncio no intervalo (YYYY-MM-DD), com leads de mensageria. */
  async fetchAdInsights({ since, until }) {
    const data = await this.request('GET', `${this.adAccountId}/insights`, {
      params: {
        level: 'ad',
        fields: 'ad_id,ad_name,impressions,clicks,spend,actions',
        time_range: { since, until },
        limit: 500,
      },
    });
    const leadActions = [
      'onsite_conversion.messaging_conversation_started_7d',
      'messaging_conversation_started_7d',
      'lead',
      'onsite_conversion.lead_grouped',
    ];
    return (data.data || []).map((row) => {
      const actions = row.actions || [];
      const leads = actions
        .filter((a) => leadActions.includes(a.action_type))
        .reduce((sum, a) => sum + Number(a.value || 0), 0);
      return {
        metaAdId: row.ad_id,
        impressions: Number(row.impressions || 0),
        clicks: Number(row.clicks || 0),
        spend: Number(row.spend || 0),
        leads,
      };
    });
  }
}

/**
 * Carrega a credencial com validação de status, pronta para uso.
 * A propriedade (user_id) é verificada pelo chamador (rotas), com RBAC.
 */
export function loadServiceForCredential(credRow, { requireValidated = true, requireEnabled = true } = {}) {
  if (!credRow) throw new MetaError('Integração Meta não encontrada.', null, 'config');
  if (requireEnabled && !credRow.is_active) {
    throw new MetaError('Esta integração está desativada. Habilite-a antes de usar.', null, 'config');
  }
  if (requireValidated && credRow.validation_status !== 'connected') {
    throw new MetaError(
      'A integração não está validada (pendente ou com falha). Use "Validar integração" antes de publicar.',
      null,
      'config'
    );
  }
  return new MetaAdsService(credRow);
}

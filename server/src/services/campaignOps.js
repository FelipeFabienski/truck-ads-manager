import { db } from '../db.js';
import { config } from '../config.js';
import { publishCampaignWithCredential, setAdStatusWithCredential, fetchInsightsWithCredential } from './metaOps.js';
import { resolveCredentialForCampaign, getActiveCredentialForUser } from './credentialStore.js';
import { whatsappUrl } from '../utils/whatsapp.js';

/**
 * Operações de campanha que conversam com a Meta (sempre por ação do usuário):
 * publicar (campanha→conjunto→criativo→anúncio PAUSADO), pausar/ativar e métricas.
 * Guards de propriedade/status/credencial resolvidos internamente; as rotas
 * chamam apenas funções por ID + requester (padrão thin-route).
 */

const CAMPAIGN_SELECT_BY_ID = 'SELECT * FROM campaigns WHERE id = ?';

function loadCampaignForRequest(campaignId, requester) {
  const id = Number.parseInt(String(campaignId ?? ''), 10);
  if (!Number.isInteger(id) || id <= 0) {
    throw { status: 404, message: 'Campanha não encontrada.' };
  }
  const row = db.prepare(CAMPAIGN_SELECT_BY_ID).get(id);
  if (!row) throw { status: 404, message: 'Campanha não encontrada.' };
  if (row.user_id !== requester.id && requester.role !== 'admin') {
    throw { status: 403, message: 'Você não tem acesso a esta campanha.' };
  }
  return row;
}

function toCampaign(row) {
  return {
    id: row.id,
    userId: row.user_id,
    productName: row.product_name,
    color: row.color,
    year: row.year,
    price: row.price,
    km: row.km,
    city: row.city,
    state: row.state,
    sellerName: row.seller_name,
    whatsapp: row.whatsapp,
    dailyBudget: row.daily_budget,
    durationDays: row.duration_days,
    ageMin: row.age_min,
    ageMax: row.age_max,
    gender: row.gender,
    interests: JSON.parse(row.interests || '[]'),
    photos: JSON.parse(row.photos || '[]'),
    title: row.title,
    adText: row.ad_text,
    status: row.status,
    credentialId: row.credential_id || null,
    metaCampaignId: row.meta_campaign_id,
    metaAdsetId: row.meta_adset_id,
    metaAdId: row.meta_ad_id,
    publishedAt: row.published_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function campaignOut(row) {
  return {
    id: row.id,
    userId: row.user_id,
    productName: row.product_name,
    color: row.color,
    year: row.year,
    price: row.price,
    km: row.km,
    city: row.city,
    state: row.state,
    sellerName: row.seller_name,
    whatsapp: row.whatsapp,
    dailyBudget: row.daily_budget,
    durationDays: row.duration_days,
    ageMin: row.age_min,
    ageMax: row.age_max,
    gender: row.gender,
    interests: JSON.parse(row.interests || '[]'),
    photos: JSON.parse(row.photos || '[]'),
    title: row.title,
    adText: row.ad_text,
    status: row.status,
    credentialId: row.credential_id || null,
    metaCampaignId: row.meta_campaign_id,
    metaAdsetId: row.meta_adset_id,
    metaAdId: row.meta_ad_id,
    publishedAt: row.published_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

/** Monta o payload explícito e validado que vai para a Graph API. */
function buildPublishPayload(c, waUrl) {
  const gender = ['all', 'male', 'female'].includes(c.gender) ? c.gender : 'all';
  return {
    product_name: String(c.productName).slice(0, 120),
    interests: (Array.isArray(c.interests) ? c.interests : []).slice(0, 10).map((i) => String(i)),
    daily_budget: Number(c.dailyBudget),
    duration_days: Number(c.durationDays),
    age_min: Number(c.ageMin),
    age_max: Number(c.ageMax),
    gender,
    photos: (Array.isArray(c.photos) ? c.photos : []).slice(0, 6),
    title: String(c.title).slice(0, 90),
    ad_text: String(c.adText).slice(0, 900),
    _whatsappUrl: waUrl,
  };
}

/** POST publish — rascunho → publicado PAUSADO na Meta (via credencial validada). */
export async function publishCampaignById(campaignId, requester) {
  const row = loadCampaignForRequest(campaignId, requester);
  const c = toCampaign(row);
  if (c.status !== 'draft') {
    throw { status: 409, message: 'Esta campanha já foi publicada na Meta.' };
  }

  const credRow = resolveCredentialForCampaign(row, { id: requester.id, role: requester.role });
  if (!credRow.page_id) {
    throw { status: 409, message: 'A integração selecionada não tem Page ID — obrigatório para publicar.' };
  }
  if (!c.photos.length) {
    throw { status: 400, message: 'A campanha precisa de pelo menos uma foto para publicar.' };
  }

  let waUrl;
  try {
    waUrl = whatsappUrl(c.whatsapp, c.productName);
  } catch {
    throw { status: 400, message: 'Número de WhatsApp inválido para o link do anúncio.' };
  }

  const payload = buildPublishPayload(c, waUrl);
  const result = await publishCampaignWithCredential(credRow, payload, { waUrl });

  const now = new Date().toISOString();
  db.prepare(
    "UPDATE campaigns SET status = 'paused', meta_campaign_id = ?, meta_adset_id = ?, meta_ad_id = ?, published_at = ?, updated_at = ? WHERE id = ?"
  ).run(result.metaCampaignId, result.metaAdsetId, result.metaAdId, now, now, row.id);
  return { campaign: campaignOut(db.prepare(CAMPAIGN_SELECT_BY_ID).get(row.id)) };
}

/** POST activate — retoma pausada ou publica+ativa rascunho (anúncio ACTIVE na Meta). */
export async function activateCampaignById(campaignId, requester) {
  const row = loadCampaignForRequest(campaignId, requester);
  const c = toCampaign(row);
  if (c.status === 'active') {
    throw { status: 409, message: 'A campanha já está ativa.' };
  }

  const credRow = resolveCredentialForCampaign(row, { id: requester.id, role: requester.role });
  let metaAdId = c.metaAdId;

  if (c.status === 'draft') {
    if (!credRow.page_id) {
      throw { status: 409, message: 'A integração selecionada não tem Page ID — obrigatório para publicar.' };
    }
    if (!c.photos.length) {
      throw { status: 400, message: 'A campanha precisa de pelo menos uma foto para publicar.' };
    }
    let waUrl;
    try {
      waUrl = whatsappUrl(c.whatsapp, c.productName);
    } catch {
      throw { status: 400, message: 'Número de WhatsApp para o link do anúncio inválido.' };
    }
    const result = await publishCampaignWithCredential(credRow, buildPublishPayload(c, waUrl), { waUrl });
    db.prepare('UPDATE campaigns SET meta_campaign_id = ?, meta_adset_id = ?, meta_ad_id = ?, published_at = ? WHERE id = ?').run(
      result.metaCampaignId, result.metaAdsetId, result.metaAdId, new Date().toISOString(), row.id
    );
    metaAdId = result.metaAdId;
  }

  await setAdStatusWithCredential(credRow, metaAdId, 'ACTIVE');
  db.prepare("UPDATE campaigns SET status = 'active', updated_at = ? WHERE id = ?").run(new Date().toISOString(), row.id);
  return { campaign: campaignOut(db.prepare(CAMPAIGN_SELECT_BY_ID).get(row.id)) };
}

/** POST pause — suspende o anúncio na Meta e localmente. */
export async function pauseCampaignById(campaignId, requester) {
  const row = loadCampaignForRequest(campaignId, requester);
  const c = toCampaign(row);
  if (c.status !== 'active') {
    throw { status: 409, message: 'Apenas campanhas ativas podem ser pausadas.' };
  }

  if (c.metaAdId) {
    const credRow = resolveCredentialForCampaign(row, { id: requester.id, role: requester.role });
    await setAdStatusWithCredential(credRow, c.metaAdId, 'PAUSED');
  }
  db.prepare("UPDATE campaigns SET status = 'paused', updated_at = ? WHERE id = ?").run(new Date().toISOString(), row.id);
  return { campaign: campaignOut(db.prepare(CAMPAIGN_SELECT_BY_ID).get(row.id)) };
}

/** GET metrics agregado por usuário (hoje/7d/30d). */
export async function aggregateMetricsForRequest(requester, period) {
  const emptyTotals = { impressions: 0, clicks: 0, leads: 0, spend: 0, costPerLead: null };
  const rows = db
    .prepare(
      "SELECT * FROM campaigns WHERE meta_ad_id != '' AND status != 'draft'"
    )
    .all()
    .filter((c) => (requester.role === 'admin' ? true : c.user_id === requester.id));

  const campaignCount = rows.length;
  if (!campaignCount) {
    return { totals: { ...emptyTotals }, campaignCount, publishedWithAds: 0, period };
  }

  // Agrupa por credencial: cada credencial é consultada com o próprio token (BYOT)
  const byCredential = new Map();
  for (const c of rows) {
    const credId = c.credential_id || null;
    const key = credId || ('active:' + c.user_id);
    if (!byCredential.has(key)) byCredential.set(key, []);
    byCredential.get(key).push(c);
  }

  const totals = { impressions: 0, clicks: 0, leads: 0, spend: 0 };
  let publishedWithAds = 0;
  let unavailable = null;
  const fmt = (d) => d.toISOString().slice(0, 10);
  const today = new Date();
  const since = period === 'today' ? fmt(today) : fmt(new Date(today.getTime() - (period === '7d' ? 6 : 29) * 86_400_000));

  for (const [key, group] of byCredential) {
    let credRow = null;
    if (String(key).startsWith('active:')) {
      credRow = getActiveCredentialForUser(Number(String(key).slice(7)));
    } else {
      credRow = db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(key);
    }
    if (!credRow || credRow.validation_status !== 'connected' || !credRow.is_active) {
      unavailable = 'Há campanhas publicadas com integração não validada/desativada — sem métricas para elas.';
      continue;
    }
    // RBAC: só usa credenciais do próprio usuário (admin pode usar as dos clientes)
    if (credRow.user_id !== requester.id && requester.role !== 'admin') continue;

    try {
      const ins = await fetchInsightsWithCredential(credRow, { since, until: fmt(today) });
      const byAd = new Map(ins.map((r) => [r.metaAdId, r]));
      for (const c of group) {
        const rowIns = byAd.get(c.meta_ad_id);
        if (!rowIns) continue;
        publishedWithAds += 1;
        totals.impressions += rowIns.impressions;
        totals.clicks += rowIns.clicks;
        totals.leads += rowIns.leads;
        totals.spend += rowIns.spend;
      }
    } catch (err) {
      unavailable = err.message || 'Falha ao consultar métricas na Meta.';
    }
  }

  totals.spend = Math.round(totals.spend * 100) / 100;
  return {
    totals: { ...totals, costPerLead: totals.leads > 0 ? Math.round((totals.spend / totals.leads) * 100) / 100 : null },
    campaignCount,
    publishedWithAds,
    period,
    ...(unavailable ? { unavailable } : {}),
  };
}

/** GET metrics por campanha (hoje/7d/30d), via credencial do dono/admin. */
export async function campaignMetricsById(campaignId, requester, period) {
  const row = loadCampaignForRequest(campaignId, requester);
  const c = toCampaign(row);
  const emptyMetrics = { impressions: 0, clicks: 0, leads: 0, spend: 0, costPerLead: null };

  if (!c.metaAdId || !c.publishedAt) {
    return { metrics: emptyMetrics, published: false, period };
  }

  const credRow = row.credential_id
    ? db.prepare('SELECT * FROM meta_credentials WHERE id = ?').get(row.credential_id)
    : getActiveCredentialForUser(row.user_id);
  if (!credRow || credRow.validation_status !== 'connected' || !credRow.is_active) {
    return { metrics: emptyMetrics, published: true, unavailable: 'Sem integração Meta validada para consultar as métricas.', period };
  }

  const fmt = (d) => d.toISOString().slice(0, 10);
  const today = new Date();
  const since = period === 'today' ? fmt(today) : fmt(new Date(today.getTime() - (period === '7d' ? 6 : 29) * 86_400_000));

  try {
    const rowsIns = await fetchInsightsWithCredential(credRow, { since, until: fmt(today) });
    const ins = rowsIns.find((r) => r.metaAdId === c.metaAdId) || emptyMetrics;
    return {
      metrics: {
        impressions: ins.impressions,
        clicks: ins.clicks,
        leads: ins.leads,
        spend: ins.spend,
        costPerLead: ins.leads > 0 ? Math.round((ins.spend / ins.leads) * 100) / 100 : null,
      },
      published: true,
      period,
    };
  } catch (err) {
    return { metrics: emptyMetrics, published: true, unavailable: err.message || 'Falha ao consultar métricas na Meta.', period };
  }
}

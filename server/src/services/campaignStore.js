import { db } from '../db.js';
import { config } from '../config.js';
import { validateCampaignPayload, validateAdCopy } from '../utils/validate.js';
import path from 'node:path';
import fs from 'node:fs';

/** Camada de dados/lógica de campanhas — rotas ficam finas (thin routes). */

function parseCampaign(row) {
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

/** Campos do formulário → colunas (inclui integração Meta escolhida). */
export function extractCampaignFields(body) {
  let interests = [];
  try {
    const raw = body?.interests;
    interests = typeof raw === 'string' ? JSON.parse(raw || '[]') : Array.isArray(raw) ? raw : [];
    interests = interests.map((i) => String(i).trim()).filter(Boolean).slice(0, 10);
  } catch {
    interests = [] ;
  }
  const credentialId = Number.parseInt(String(body?.credential_id ?? ''), 10);
  return {
    product_name: String(body?.product_name ?? '').trim().slice(0, 120),
    color: String(body?.color ?? '').trim().slice(0, 60),
    year: String(body?.year ?? '').trim().slice(0, 10),
    price: String(body?.price ?? '').trim().slice(0, 20),
    km: String(body?.km ?? '').trim().slice(0, 20),
    city: String(body?.city ?? '').trim().slice(0, 80),
    state: String(body?.state ?? '').trim().slice(0, 2).toUpperCase(),
    seller_name: String(body?.seller_name ?? '').trim().slice(0, 80),
    whatsapp: String(body?.whatsapp ?? '').trim().slice(0, 30),
    daily_budget: body?.daily_budget,
    duration_days: body?.duration_days,
    age_min: body?.age_min,
    age_max: body?.age_max,
    gender: String(body?.gender ?? 'all').slice(0, 10) || 'all',
    interests,
    credentialId: Number.isInteger(credentialId) && credentialId > 0 ? credentialId : null,
  };
}

export function campaignAccess(row, requester) {
  if (row.user_id !== requester.id && requester.role !== 'admin') {
    throw { status: 403, message: 'Você não tem acesso a esta campanha.' };
  }
  return row;
}

export function loadCampaignById(id, requester) {
  const idNum = Number.parseInt(String(id ?? ''), 10);
  if (!Number.isInteger(idNum) || idNum <= 0) {
    throw { status: 404, message: 'Campanha não encontrada.' };
  }
  const row = db.prepare('SELECT * FROM campaigns WHERE id = ?').get(idNum);
  if (!row) throw { status: 404, message: 'Campanha não encontrada.' };
  return campaignAccess(row, requester);
}

export function listCampaignsForRequest(requester, { status, q }) {
  let sql = 'SELECT * FROM campaigns';
  const where = [];
  const params = [];
  if (requester.role !== 'admin') {
    where.push('user_id = ?');
    params.push(requester.id);
  }
  if (status && ['draft', 'paused', 'active'].includes(status)) {
    where.push('status = ?');
    params.push(status);
  }
  if (q) {
    where.push('product_name LIKE ?');
    params.push('%' + String(q).slice(0, 100) + '%');
  }
  if (where.length) sql += ' WHERE ' + where.join(' AND ');
  sql += ' ORDER BY created_at DESC';
  return db.prepare(sql).all(...params).map(parseCampaign);
}

/** Cria rascunho com guard IDOR da integração escolhida. */
export function createCampaignDraft({ requester, fields, photos, title, adText }) {
  const errors = { ...validateCampaignPayload(fields), ...validateAdCopy(title, adText) };
  if (Object.keys(errors).length) {
    return { errors };
  }
  if (!photos.length) {
    return { errors: { photos: 'Envie pelo menos uma foto do produto.' } };
  }

  let credentialId = null;
  if (fields.credentialId) {
    const cred = db.prepare('SELECT id, user_id FROM meta_credentials WHERE id = ?').get(fields.credentialId);
    if (!cred || (cred.user_id !== requester.id && requester.role !== 'admin')) {
      throw { status: 403, message: 'A integração selecionada não pertence a você.' };
    }
    credentialId = fields.credentialId;
  }

  const now = new Date().toISOString();
  const info = db
    .prepare(
      'INSERT INTO campaigns (user_id, product_name, color, year, price, km, city, state, seller_name, whatsapp, daily_budget, duration_days, age_min, age_max, gender, interests, photos, title, ad_text, status, credential_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    )
    .run(
      requester.id, fields.product_name, fields.color, fields.year, fields.price, fields.km, fields.city, fields.state,
      fields.seller_name, fields.whatsapp, fields.daily_budget, fields.duration_days,
      fields.age_min, fields.age_max, fields.gender, JSON.stringify(fields.interests), JSON.stringify(photos),
      title, adText, 'draft', credentialId, now, now
    );
  return { row: db.prepare('SELECT * FROM campaigns WHERE id = ?').get(info.lastInsertRowid) };
}

/** Edita campos/texto/integração (guard IDOR da integração também aqui). */
export function updateCampaignFields(row, body, requester) {
  const current = parseCampaign(row);
  const merged = {
    product_name: body?.product_name !== undefined ? body.product_name : current.productName,
    color: body?.color !== undefined ? body.color : current.color,
    year: body?.year !== undefined ? body.year : current.year,
    price: body?.price !== undefined ? body.price : current.price,
    km: body?.km !== undefined ? body.km : current.km,
    city: body?.city !== undefined ? body.city : current.city,
    state: body?.state !== undefined ? body.state : current.state,
    seller_name: body?.seller_name !== undefined ? body.seller_name : current.sellerName,
    whatsapp: body?.whatsapp !== undefined ? body.whatsapp : current.whatsapp,
    daily_budget: body?.daily_budget !== undefined ? body.daily_budget : current.dailyBudget,
    duration_days: body?.duration_days !== undefined ? body.duration_days : current.durationDays,
    age_min: body?.age_min !== undefined ? body.age_min : current.ageMin,
    age_max: body?.age_max !== undefined ? body.age_max : current.ageMax,
    gender: body?.gender !== undefined ? body.gender : current.gender,
    interests: body?.interests !== undefined ? body.interests : current.interests,
  };
  const fields = extractCampaignFields(merged);
  const title = body?.title !== undefined ? String(body.title).trim().slice(0, 90) : current.title;
  const adText = body?.ad_text !== undefined ? String(body.ad_text).trim().slice(0, 900) : current.adText;
  const errors = { ...validateCampaignPayload(fields), ...validateAdCopy(title, adText) };
  if (Object.keys(errors).length) return { errors };

  let credentialId = current.credentialId;
  if (body?.credential_id !== undefined) {
    const parsed = Number.parseInt(String(body.credential_id ?? ''), 10);
    const wanted = Number.isInteger(parsed) && parsed > 0 ? parsed : null;
    if (wanted) {
      const cred = db.prepare('SELECT id, user_id FROM meta_credentials WHERE id = ?').get(wanted);
      if (!cred || (cred.user_id !== requester.id && requester.role !== 'admin')) {
        throw { status: 403, message: 'A integração selecionada não pertence a você.' };
      }
    }
    credentialId = wanted;
  }

  db.prepare(
    'UPDATE campaigns SET product_name = ?, color = ?, year = ?, price = ?, km = ?, city = ?, state = ?, seller_name = ?, whatsapp = ?, daily_budget = ?, duration_days = ?, age_min = ?, age_max = ?, gender = ?, interests = ?, title = ?, ad_text = ?, credential_id = ?, updated_at = ? WHERE id = ?'
  ).run(
    fields.product_name, fields.color, fields.year, fields.price, fields.km, fields.city, fields.state,
    fields.seller_name, fields.whatsapp, fields.daily_budget, fields.duration_days,
    fields.age_min, fields.age_max, fields.gender, JSON.stringify(fields.interests), title, adText,
    credentialId, new Date().toISOString(), row.id
  );
  return { row: db.prepare('SELECT * FROM campaigns WHERE id = ?').get(row.id) };
}

/** Exclui a campanha e remove as fotos do disco. */
export function deleteCampaignWithPhotos(row) {
  db.prepare('DELETE FROM campaigns WHERE id = ?').run(row.id);
  for (const rel of JSON.parse(row.photos || '[]')) {
    const abs = path.join(config.uploadDir, String(rel));
    if (abs.startsWith(config.uploadDir) && fs.existsSync(abs)) fs.unlink(abs, () => {});
  }
}

export function campaignByIdJson(row) {
  return { campaign: parseCampaign(row) };
}

export { parseCampaign };

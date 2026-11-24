import { Router } from 'express';
import multer from 'multer';
import path from 'node:path';
import fs from 'node:fs';
import { config } from '../config.js';
import { requireAuth } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import {
  extractCampaignFields,
  loadCampaignById,
  listCampaignsForRequest,
  createCampaignDraft,
  updateCampaignFields,
  deleteCampaignWithPhotos,
  parseCampaign,
} from '../services/campaignStore.js';
import { publishCampaignById, activateCampaignById, pauseCampaignById, campaignMetricsById } from '../services/campaignOps.js';
import { audit } from '../services/audit.js';

const router = Router();
router.use(requireAuth);

const photoStorage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(config.uploadDir, 'products');
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname || '').toLowerCase() || '.jpg';
    cb(null, `${Date.now()}-${Math.random().toString(36).slice(2, 10)}${ext}`);
  },
});
const photoUpload = multer({
  storage: photoStorage,
  limits: { fileSize: 10 * 1024 * 1024, files: 6 },
  fileFilter: (req, file, cb) => cb(null, /^image\/(jpeg|png|webp)$/.test(file.mimetype)),
});

/** GET /api/campaigns?status=&q= */
router.get('/', (req, res) => {
  const requester = { id: req.user.id, role: String(req.user.role) };
  res.json({ campaigns: listCampaignsForRequest(requester, { status: req.query.status, q: req.query.q }) });
});

/** POST /api/campaigns — cria rascunho (upload local; rede só ao publicar). */
router.post('/', photoUpload.array('photos', 6), (req, res) => {
  const fields = extractCampaignFields(req.body);
  const title = String(req.body?.title ?? '').trim().slice(0, 90);
  const adText = String(req.body?.ad_text ?? '').trim().slice(0, 900);
  const photos = (req.files || []).map((f) => 'products/' + f.filename);

  try {
    const result = createCampaignDraft({ requester: { id: req.user.id, role: String(req.user.role) }, fields, photos, title, adText });
    if (result.errors) {
      for (const f of req.files || []) fs.unlink(f.path, () => {});
      return res.status(400).json({ error: 'Verifique os campos do formulário.', errors: result.errors });
    }
    audit({ userId: req.user.id, action: 'campaign.created', resourceType: 'campaign', resourceId: result.row.id, ip: req.ip });
    res.status(201).json({ message: 'Campanha criada como rascunho! Revise e publique quando quiser.', campaign: parseCampaign(result.row) });
  } catch (err) {
    for (const f of req.files || []) fs.unlink(f.path, () => {});
    const status = err && err.status ? Number(err.status) : 500;
    res.status(status).json({ error: String(err?.message || 'Erro ao criar campanha.') });
  }
});

/** GET /api/campaigns/:id */
router.get('/:id', (req, res) => {
  try {
    const row = loadCampaignById(req.params.id, { id: req.user.id, role: String(req.user.role) });
    res.json({ campaign: parseCampaign(row) });
  } catch (err) {
    const status = err && err.status ? Number(err.status) : 500;
    res.status(status).json({ error: String(err?.message || 'Erro.') });
  }
});

/** PUT /api/campaigns/:id */
router.put('/:id', (req, res) => {
  try {
    const row = loadCampaignById(req.params.id, { id: req.user.id, role: String(req.user.role) });
    const result = updateCampaignFields(row, req.body, { id: req.user.id, role: String(req.user.role) });
    if (result.errors) return res.status(400).json({ error: 'Verifique os campos do formulário.', errors: result.errors });
    audit({ userId: req.user.id, action: 'campaign.updated', resourceType: 'campaign', resourceId: row.id, ip: req.ip });
    res.json({ message: 'Campanha atualizada!', campaign: parseCampaign(result.row) });
  } catch (err) {
    const status = err && err.status ? Number(err.status) : 500;
    res.status(status).json({ error: String(err?.message || 'Erro.') });
  }
});

/** DELETE /api/campaigns/:id */
router.delete('/:id', (req, res) => {
  try {
    const row = loadCampaignById(req.params.id, { id: req.user.id, role: String(req.user.role) });
    deleteCampaignWithPhotos(row);
    audit({ userId: req.user.id, action: 'campaign.deleted', resourceType: 'campaign', resourceId: row.id, ip: req.ip });
    res.json({ message: 'Campanha excluída.' });
  } catch (err) {
    const status = err && err.status ? Number(err.status) : 500;
    res.status(status).json({ error: String(err?.message || 'Erro.') });
  }
});

/**
 * Operações que conversam com a Meta — executadas SOMENTE por ação explícita do
 * usuário (Publicar / Ativar / Pausar). Guards, RBAC e comunicação real ficam em
 * campaignOps → metaOps → MetaAdsService.
 */
const campaignNetworkRoutes = [
  {
    method: 'post',
    path: '/:id/publish',
    limiter: () => rateLimit('publish', 10),
    run: (campaignId, requester) => publishCampaignById(campaignId, requester),
    okMessage: 'Anúncio publicado na Meta como PAUSADO — revise e ative quando estiver pronto.',
    auditOk: 'campaign.published',
    auditDenied: 'campaign.publish_failed',
  },
  {
    method: 'post',
    path: '/:id/activate',
    limiter: () => rateLimit('publish', 10),
    run: (campaignId, requester) => activateCampaignById(campaignId, requester),
    okMessage: 'Campanha ativa! O anúncio está veiculando no Facebook/Instagram.',
    auditOk: 'campaign.activated',
    auditDenied: 'campaign.activate_failed',
  },
  {
    method: 'post',
    path: '/:id/pause',
    limiter: () => rateLimit('publish', 10),
    run: (campaignId, requester) => pauseCampaignById(campaignId, requester),
    okMessage: 'Campanha pausada.',
    auditOk: 'campaign.paused',
    auditDenied: 'campaign.pause_failed',
  },
];

for (const spec of campaignNetworkRoutes) {
  router.post(spec.path, spec.limiter(), async (req, res) => {
    const requester = { id: req.user.id, role: String(req.user.role) };
    let outcome;
    try {
      outcome = await spec.run(Number.parseInt(String(req.params.id), 10), requester);
    } catch (err) {
      const status = err && err.status ? Number(err.status) : 500;
      if (status >= 500) console.error('Falha em operação de campanha:', err);
      audit({ userId: req.user.id, action: spec.auditDenied, resourceType: 'campaign', resourceId: req.params.id, status: 'error', ip: req.ip });
      return res.status(status).json({ error: String(err?.message || 'Erro inesperado.') });
    }
    audit({ userId: req.user.id, action: spec.auditOk, resourceType: 'campaign', resourceId: outcome.campaign.id, ip: req.ip });
    res.json({ message: spec.okMessage, campaign: outcome.campaign });
  });
}

/** GET /api/campaigns/:id/metrics?period=today|7d|30d */
router.get('/:id/metrics', async (req, res) => {
  const requester = { id: req.user.id, role: String(req.user.role) };
  const period = ['today', '7d', '30d'].includes(req.query.period) ? req.query.period : '7d';
  try {
    const result = await campaignMetricsById(Number.parseInt(String(req.params.id), 10), requester, period);
    res.json(result);
  } catch (err) {
    const status = err && err.status ? Number(err.status) : 500;
    if (status >= 500) console.error('Falha ao buscar métricas:', err);
    res.status(status).json({ error: String(err?.message || 'Erro ao consultar métricas.') });
  }
});

export default router;

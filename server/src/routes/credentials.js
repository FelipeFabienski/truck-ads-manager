import { Router } from 'express';
import { db } from '../db.js';
import { requireAuth, requireAdmin } from '../middlewares/auth.js';
import { rateLimit } from '../middlewares/rateLimit.js';
import {
  validateCredentialById,
  discoverAssetsById,
  discoverAssetsFromToken,
} from '../services/metaOps.js';
import {
  getManageableCredentialOr403,
  getActiveCredentialForUser,
  publicCredentialView,
  insertAdminCredential,
  createCredential,
  updateCredentialFields,
  activateCredentialForOwner,
  setCredentialEnabled,
  deleteCredential,
} from '../services/credentialStore.js';
import { audit } from '../services/audit.js';
import { str } from '../utils/validate.js';

const router = Router();
router.use(requireAuth);

/** Só dígitos; Ad Account sai sempre no formato act_ID (nulo = pendente). */
function normalizeDigits(v) {
  const digits = str(v, 60).replace(/\D/g, '');
  return digits || null;
}

function normalizeActId(v) {
  const digits = str(v, 60).replace(/^act_/i, '').replace(/\D/g, '');
  return digits ? `act_${digits}` : null;
}

/** Campos do formulário → colunas (ativos podem ficar nulos enquanto pendente). */
function extractFields(body) {
  return {
    name: str(body?.name, 80),
    adAccountId: body?.adAccountId !== undefined ? normalizeActId(body.adAccountId) : undefined,
    pageId: body?.pageId !== undefined ? normalizeDigits(body.pageId) : undefined,
    instagramActorId: body?.instagramActorId !== undefined ? normalizeDigits(body.instagramActorId) : undefined,
    businessId: body?.businessId !== undefined ? normalizeDigits(body.businessId) : undefined,
    appId: body?.appId !== undefined ? normalizeDigits(body.appId) : undefined,
    whatsappNumber: str(body?.whatsappNumber, 30),
  };
}

// ---------------------------------------------------------------------------
/** GET /api/credentials?scope=all — lista própria (ou todas, para o admin). */
router.get('/', (req, res) => {
  const wantsAll = req.query.scope === 'all' && req.user.role === 'admin';
  const rows = wantsAll
    ? db.prepare('SELECT * FROM meta_credentials ORDER BY user_id, created_at DESC').all()
    : db.prepare('SELECT * FROM meta_credentials WHERE user_id = ? ORDER BY is_active DESC, created_at DESC').all(req.user.id);
  res.json({ credentials: rows.map((r) => publicCredentialView(r, { includeUser: wantsAll })) });
});

/** GET /api/credentials/active — a integração habilitada do usuário logado. */
router.get('/active', (req, res) => {
  const row = getActiveCredentialForUser(req.user.id);
  res.json({ credential: row ? publicCredentialView(row) : null });
});

/**
 * POST /api/credentials/import-admin — importação inicial da credencial do admin
 * a partir da variável de ambiente temporária META_ADMIN_INITIAL_ACCESS_TOKEN.
 * NÃO valida na Meta (status fica "Pendente de validação"); sem chamadas externas.
 */
router.post('/import-admin', requireAdmin, rateLimit('import-admin', 3), (req, res) => {
  const token = process.env.META_ADMIN_INITIAL_ACCESS_TOKEN || '';
  if (!token) {
    return res.status(409).json({
      error: 'META_ADMIN_INITIAL_ACCESS_TOKEN não está definida no ambiente. Defina-a em server/.env e tente novamente.',
    });
  }
  const name = 'Meta Ads - Administrador';
  const existing = db.prepare('SELECT id FROM meta_credentials WHERE user_id = ? AND name = ?').get(req.user.id, name);
  if (existing) {
    return res.status(409).json({ error: 'A integração "Meta Ads - Administrador" já existe para este administrador.' });
  }
  const row = insertAdminCredential(req.user.id, name, token);
  audit({ userId: req.user.id, action: 'credential.imported', resourceType: 'credential', resourceId: row.id, ip: req.ip });
  res.status(201).json({
    message: 'Integração "Meta Ads - Administrador" importada com status "Pendente de validação".',
    credential: publicCredentialView(row),
  });
});

/** POST /api/credentials — cadastra integração (status inicial: pendente). */
router.post('/', rateLimit('credentials', 10), (req, res) => {
  const accessToken = str(req.body?.accessToken, 600);
  const fields = extractFields(req.body);
  if (!fields.name) return res.status(400).json({ error: 'Informe o nome da integração.', errors: { name: 'Informe o nome da integração.' } });
  if (!accessToken) return res.status(400).json({ error: 'Informe o Access Token.', errors: { accessToken: 'Informe o Access Token.' } });

  const row = createCredential({
    userId: req.user.id,
    name: fields.name,
    accessToken,
    fields,
    appSecret: req.body?.appSecret ? str(req.body.appSecret, 300) : '',
  });

  audit({ userId: req.user.id, action: 'credential.created', resourceType: 'credential', resourceId: row.id, ip: req.ip });
  res.status(201).json({
    message: 'Integração cadastrada com status "Pendente de validação".',
    credential: publicCredentialView(row),
  });
});

/**
 * Operações que conversam com a Meta — executadas SOMENTE por ação explícita do
 * usuário (botões "Validar integração" / "Descobrir ativos"). Registradas via
 * tabela declarativa de operações; a resolução de propriedade/status/RBAC e toda
 * a comunicação real acontecem dentro de cada operação (metaOps → MetaAdsService).
 */
const metaNetworkRoutes = [
  {
    method: 'post',
    path: '/:id/validate',
    limiter: () => rateLimit('validate', 6),
    run: (credentialId, requester, body) => validateCredentialById(credentialId, requester, { freshToken: String(body?.accessToken ?? '') }),
    toResponse: (outcome) => ({
      ok: outcome.status === 'connected',
      status: outcome.status,
      checks: outcome.checks,
    }),
    auditOk: 'credential.validated',
    auditDenied: 'credential.validate_denied',
  },
  {
    method: 'post',
    path: '/:id/discover',
    limiter: () => rateLimit('discover', 6),
    run: (credentialId, requester, body) => discoverAssetsById(credentialId, requester, { tokenOverride: String(body?.accessToken ?? '') }),
    toResponse: (outcome) => outcome.assets,
    auditOk: 'credential.discovered',
    auditDenied: 'credential.discover_failed',
  },
];

for (const spec of metaNetworkRoutes) {
  if (spec.method !== 'post') continue;
  router.post(spec.path, spec.limiter(), async (req, res) => {
    const credentialId = Number.parseInt(String(req.params.id ?? ''), 10);
    if (!Number.isInteger(credentialId) || credentialId <= 0) {
      return res.status(404).json({ error: 'Integração não encontrada.' });
    }
    const requester = { userId: Number(req.user.id), role: String(req.user.role) };

    let outcome;
    try {
      outcome = await spec.run(credentialId, requester, req.body);
    } catch (err) {
      if (err && err.status) return res.status(Number(err.status)).json({ error: String(err.message) });
      audit({ userId: req.user.id, action: spec.auditDenied, resourceType: 'credential', resourceId: credentialId, status: 'error', ip: req.ip });
      return res.status(422).json({ error: String(err.message), status: err ? err.validationStatus : undefined });
    }
    audit({ userId: req.user.id, action: spec.auditOk, resourceType: 'credential', resourceId: outcome.credRow.id, status: outcome.status, ip: req.ip });
    res.json(spec.toResponse(outcome));
  });
}

export default router;

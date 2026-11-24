import { Router } from 'express';
import { requireAuth } from '../middlewares/auth.js';
import { aggregateMetricsForRequest } from '../services/campaignOps.js';

const router = Router();
router.use(requireAuth);

/** GET /api/metrics?period=today|7d|30d — desempenho agregado (BYOT por credencial). */
router.get('/', async (req, res) => {
  const requester = { id: req.user.id, role: String(req.user.role) };
  const period = ['today', '7d', '30d'].includes(req.query.period) ? req.query.period : '7d';
  try {
    const result = await aggregateMetricsForRequest(requester, period);
    res.json(result);
  } catch (err) {
    const status = err && err.status ? Number(err.status) : 500;
    if (status >= 500) console.error('Falha ao buscar métricas agregadas:', err);
    res.status(status).json({ error: String(err?.message || 'Erro ao consultar métricas.') });
  }
});

export default router;

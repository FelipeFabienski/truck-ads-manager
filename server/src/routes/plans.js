import { Router } from 'express';
import { db } from '../db.js';
import { requireAuth } from '../middlewares/auth.js';

const router = Router();
router.use(requireAuth);

/** GET /api/plans — catálogo de planos (estrutura de cobrança futura) */
router.get('/', (req, res) => {
  const rows = db.prepare('SELECT * FROM plans ORDER BY price_cents ASC').all();
  res.json({
    plans: rows.map((p) => ({
      id: p.id,
      name: p.name,
      priceCents: p.price_cents,
      maxCampaigns: p.max_campaigns,
      features: JSON.parse(p.features || '[]'),
    })),
  });
});

/** GET /api/plans/current — plano do usuário logado */
router.get('/current', (req, res) => {
  const user = db.prepare('SELECT plan_id FROM users WHERE id = ?').get(req.user.id);
  const row = user ? db.prepare('SELECT * FROM plans WHERE id = ?').get(user.plan_id) : null;
  res.json({
    plan: row ? { id: row.id, name: row.name, priceCents: row.price_cents, maxCampaigns: row.max_campaigns, features: JSON.parse(row.features || '[]') } : null,
  });
});

/**
 * POST /api/plans/select — associar um plano ao usuário.
 * Estrutura pronta para plugar pagamentos: hoje apenas registra a escolha.
 */
router.post('/select', (req, res) => {
  const plan = db.prepare('SELECT * FROM plans WHERE id = ?').get(req.body?.planId);
  if (!plan) return res.status(404).json({ error: 'Plano não encontrado.' });
  db.prepare('UPDATE users SET plan_id = ? WHERE id = ?').run(plan.id, req.user.id);
  res.json({
    message: `Plano ${plan.name} associado à sua conta. Cobrança online disponível em breve — entraremos em contato.`,
    pendingPayment: true,
  });
});

export default router;

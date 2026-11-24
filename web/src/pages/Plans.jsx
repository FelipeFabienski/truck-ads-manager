import { useEffect, useState } from 'react';
import { api, formatBRL } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import { useToast } from '../components/Toast.jsx';

export default function Plans() {
  const toast = useToast();
  const { refresh } = useAuth();
  const [plans, setPlans] = useState([]);
  const [current, setCurrent] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/api/plans').then((d) => setPlans(d.plans)).catch((err) => toast.error(err.message));
    api.get('/api/plans/current').then((d) => setCurrent(d.plan)).catch(() => {});
  }, [toast]);

  async function select(plan) {
    if (!window.confirm(`Assinar o plano ${plan.name}? (Cobrança online em breve — por enquanto apenas associamos o plano à conta.)`)) return;
    setBusy(true);
    try {
      const data = await api.post('/api/plans/select', { planId: plan.id });
      toast.success(data.message);
      const c = await api.get('/api/plans/current');
      setCurrent(c.plan);
      refresh();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Planos</h1>
          <p className="page-subtitle">
            Escolha o plano ideal para o seu volume de campanhas. Plano atual: <strong>{current?.name || 'Gratuito'}</strong>.
          </p>
        </div>
      </div>

      <div className="plans-grid">
        {plans.map((p) => {
          const isCurrent = current?.id === p.id;
          return (
            <div className={`plan-card ${isCurrent ? 'plan-current' : ''}`} key={p.id}>
              {isCurrent && <span className="plan-tag">Plano atual</span>}
              <h3>{p.name}</h3>
              <div className="plan-price">
                {p.priceCents === 0 ? 'Grátis' : formatBRL(p.priceCents / 100)}
                {p.priceCents > 0 && <small>/mês</small>}
              </div>
              <ul className="plan-features">
                {p.features.map((f) => <li key={f}>✓ {f}</li>)}
              </ul>
              <button
                className={`btn ${isCurrent ? 'btn-ghost' : 'btn-primary'} btn-block`}
                disabled={busy || isCurrent}
                onClick={() => select(p)}
              >
                {isCurrent ? 'Plano atual' : 'Assinar (em breve)'}
              </button>
            </div>
          );
        })}
      </div>

      <div className="info-box">
        💳 A cobrança por assinatura será ativada em breve — esta tela já integra o catálogo de planos e a associação à conta, pronta para receber o provedor de pagamentos.
      </div>
    </div>
  );
}

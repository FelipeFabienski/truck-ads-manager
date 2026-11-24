import { useCallback, useEffect, useState } from 'react';
import { api, formatBRL } from '../api.js';
import { useToast } from '../components/Toast.jsx';

const PERIODS = [
  { key: 'today', label: 'Hoje' },
  { key: '7d', label: 'Últimos 7 dias' },
  { key: '30d', label: 'Últimos 30 dias' },
];

export default function Metrics() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState('7d');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/metrics?period=${period}`);
      setData(res);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [period, toast]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Métricas</h1>
          <p className="page-subtitle">Desempenho agregado dos seus anúncios publicados no Facebook e Instagram.</p>
        </div>
        <div className="period-tabs">
          {PERIODS.map((p) => (
            <button key={p.key} className={`tab ${period === p.key ? 'active' : ''}`} onClick={() => setPeriod(p.key)}>{p.label}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="page-loading"><div className="spinner" /></div>
      ) : data ? (
        <>
          {data.unavailable && <div className="info-box">{data.unavailable}</div>}
          <div className="metrics-grid">
            <div className="metric"><span className="metric-value">{(data.totals.impressions || 0).toLocaleString('pt-BR')}</span><span className="metric-label">Impressões</span></div>
            <div className="metric"><span className="metric-value">{(data.totals.clicks || 0).toLocaleString('pt-BR')}</span><span className="metric-label">Cliques</span></div>
            <div className="metric"><span className="metric-value">{(data.totals.leads || 0).toLocaleString('pt-BR')}</span><span className="metric-label">Leads (conversas)</span></div>
            <div className="metric"><span className="metric-value">{formatBRL(data.totals.spend || 0)}</span><span className="metric-label">Valor gasto</span></div>
            <div className="metric"><span className="metric-value">{data.totals.costPerLead != null ? formatBRL(data.totals.costPerLead) : '—'}</span><span className="metric-label">Custo por lead</span></div>
            <div className="metric"><span className="metric-value">{data.campaignCount}</span><span className="metric-label">Campanhas publicadas</span></div>
          </div>
          {data.campaignCount === 0 && (
            <div className="empty-state">
              <div className="empty-icon">📈</div>
              <h2>Nenhuma campanha publicada ainda</h2>
              <p>As métricas aparecem aqui assim que você publicar sua primeira campanha no Meta.</p>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

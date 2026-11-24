import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, formatBRL, formatDate } from '../api.js';
import StatusBadge from '../components/StatusBadge.jsx';
import { useToast } from '../components/Toast.jsx';

export default function Dashboard() {
  const toast = useToast();
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (q) params.set('q', q);
      const data = await api.get(`/api/campaigns?${params}`);
      setCampaigns(data.campaigns);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [status, q, toast]);

  useEffect(() => {
    const t = setTimeout(load, q ? 350 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  async function action(campaign, act) {
    setBusyId(campaign.id);
    try {
      const data = act === 'delete' ? await api.del(`/api/campaigns/${campaign.id}`) : await api.post(`/api/campaigns/${campaign.id}/${act}`, {});
      toast.success(data.message);
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusyId(null);
      setConfirmDelete(null);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Minhas campanhas</h1>
          <p className="page-subtitle">Crie, publique e acompanhe seus anúncios do Facebook e Instagram.</p>
        </div>
        <Link to="/app/nova-campanha" className="btn btn-primary">➕ Nova campanha</Link>
      </div>

      <div className="filters-bar">
        <input
          className="search-input"
          type="search"
          placeholder="🔍 Buscar por nome do produto..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos os status</option>
          <option value="active">Ativos</option>
          <option value="paused">Pausados</option>
          <option value="draft">Rascunhos</option>
        </select>
      </div>

      {loading ? (
        <div className="page-loading"><div className="spinner" /></div>
      ) : campaigns.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📣</div>
          <h2>Nenhuma campanha encontrada</h2>
          <p>Informe os dados do produto, escreva o texto do anúncio e publique no Facebook e Instagram.</p>
          <Link to="/app/nova-campanha" className="btn btn-primary">Criar primeira campanha</Link>
        </div>
      ) : (
        <div className="campaign-grid">
          {campaigns.map((c) => (
            <div className="campaign-card" key={c.id}>
              <div className="campaign-thumb">
                {c.photos[0] ? <img src={`/uploads/${c.photos[0]}`} alt={c.productName} /> : <span>🖼️</span>}
                <StatusBadge status={c.status} />
              </div>
              <div className="campaign-body">
                <h3 onClick={() => navigate(`/app/campanhas/${c.id}`)} role="button" tabIndex={0}>{c.productName}</h3>
                <p className="campaign-meta">
                  {[c.city && c.state ? `${c.city}/${c.state}` : c.city, c.year, c.color].filter(Boolean).join(' · ') || '—'}
                </p>
                <p className="campaign-budget">
                  <strong>{formatBRL(c.dailyBudget)}</strong>/dia · {c.durationDays} dias
                </p>
                <p className="campaign-date">Criada em {formatDate(c.createdAt)}</p>
                <div className="campaign-actions">
                  <Link className="btn btn-ghost btn-sm" to={`/app/campanhas/${c.id}`}>Abrir</Link>
                  {c.status === 'draft' && (
                    <button className="btn btn-primary btn-sm" disabled={busyId === c.id} onClick={() => action(c, 'publish')}>
                      {busyId === c.id ? '...' : 'Publicar'}
                    </button>
                  )}
                  {c.status === 'paused' && c.metaAdId && (
                    <button className="btn btn-success btn-sm" disabled={busyId === c.id} onClick={() => action(c, 'activate')}>
                      {busyId === c.id ? '...' : 'Ativar'}
                    </button>
                  )}
                  {c.status === 'active' && (
                    <button className="btn btn-warning btn-sm" disabled={busyId === c.id} onClick={() => action(c, 'pause')}>
                      {busyId === c.id ? '...' : 'Pausar'}
                    </button>
                  )}
                  {confirmDelete === c.id ? (
                    <span className="confirm-inline">Confirmar no modal ↓</span>
                  ) : (
                    <button className="btn btn-danger-ghost btn-sm" onClick={() => setConfirmDelete(c.id)}>Excluir</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {confirmDelete !== null && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Excluir campanha?</h3>
            <p>Tem certeza que deseja excluir a campanha <strong>{campaigns.find((c) => c.id === confirmDelete)?.productName}</strong>? Esta ação não pode ser desfeita.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>Cancelar</button>
              <button className="btn btn-danger" disabled={busyId === confirmDelete} onClick={() => action(campaigns.find((c) => c.id === confirmDelete), 'delete')}>
                {busyId === confirmDelete ? 'Excluindo...' : 'Excluir definitivamente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

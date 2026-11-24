import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { api, formatBRL, formatDate } from '../api.js';
import StatusBadge from '../components/StatusBadge.jsx';
import { useToast } from '../components/Toast.jsx';

const PERIODS = [
  { key: 'today', label: 'Hoje' },
  { key: '7d', label: '7 dias' },
  { key: '30d', label: '30 dias' },
];

export default function CampaignDetail() {
  const { id } = useParams();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const [campaign, setCampaign] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [period, setPeriod] = useState('7d');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editingText, setEditingText] = useState(false);
  const [title, setTitle] = useState('');
  const [adText, setAdText] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.get(`/api/campaigns/${id}`);
      setCampaign(data.campaign);
      setTitle(data.campaign.title);
      setAdText(data.campaign.adText);
      if (data.campaign.metaAdId) {
        try {
          const m = await api.get(`/api/campaigns/${id}/metrics?period=${period}`);
          setMetrics(m);
        } catch {
          setMetrics(null);
        }
      } else {
        setMetrics(null);
      }
    } catch (err) {
      toast.error(err.message);
      navigate('/app/dashboard');
    } finally {
      setLoading(false);
    }
  }, [id, period, toast, navigate]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    if (location.state?.justCreated) {
      toast.info('Campanha criada como rascunho! Revise o texto e publique quando quiser.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveText() {
    setBusy(true);
    try {
      const data = await api.put(`/api/campaigns/${id}`, { title, ad_text: adText });
      setCampaign(data.campaign);
      setEditingText(false);
      toast.success('Texto atualizado!');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function action(act) {
    setBusy(true);
    try {
      const data = await api.post(`/api/campaigns/${id}/${act}`, {});
      toast.success(data.message);
      await load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      const data = await api.del(`/api/campaigns/${id}`);
      toast.success(data.message);
      navigate('/app/dashboard');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading || !campaign) return <div className="page-loading"><div className="spinner" /></div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <Link to="/app/dashboard" className="back-link">← Voltar às campanhas</Link>
          <h1>{campaign.productName} <StatusBadge status={campaign.status} /></h1>
          <p className="page-subtitle">
            Criada em {formatDate(campaign.createdAt)}
            {campaign.publishedAt && <> · Publicada em {formatDate(campaign.publishedAt)}</>}
          </p>
        </div>
        <div className="header-actions">
          {campaign.status === 'draft' && (
            <>
              <button className="btn btn-primary" disabled={busy} onClick={() => action('publish')}>🚀 Publicar (pausado)</button>
              <button className="btn btn-success" disabled={busy} onClick={() => action('activate')}>▶ Ativar agora</button>
            </>
          )}
          {campaign.status === 'paused' && campaign.metaAdId && (
            <button className="btn btn-success" disabled={busy} onClick={() => action('activate')}>▶ Ativar campanha</button>
          )}
          {campaign.status === 'active' && (
            <button className="btn btn-warning" disabled={busy} onClick={() => action('pause')}>⏸ Pausar campanha</button>
          )}
          <button className="btn btn-danger-ghost" disabled={busy} onClick={() => setConfirmDelete(true)}>🗑 Excluir</button>
        </div>
      </div>

      {campaign.status === 'paused' && campaign.metaAdId && (
        <div className="info-box">O anúncio está publicado no Facebook/Instagram como <strong>pausado</strong>, por segurança. Revise os dados abaixo e ative quando estiver pronto.</div>
      )}

      <div className="detail-grid">
        <div className="card">
          <h2>Produto</h2>
          <div className="photo-gallery">
            {campaign.photos.map((p, i) => <img key={p} src={`/uploads/${p}`} alt={`Foto ${i + 1}`} />)}
          </div>
          <ul className="detail-list">
            <li><strong>Produto:</strong> {campaign.productName}</li>
            {campaign.color && <li><strong>Cor:</strong> {campaign.color}</li>}
            {campaign.year && <li><strong>Ano:</strong> {campaign.year}</li>}
            {campaign.price && <li><strong>Preço:</strong> R$ {Number(campaign.price).toLocaleString('pt-BR')}</li>}
            {campaign.km && <li><strong>KM:</strong> {campaign.km}</li>}
            <li><strong>Local:</strong> {campaign.city}/{campaign.state}</li>
            <li><strong>Vendedor:</strong> {campaign.sellerName} · 📱 {campaign.whatsapp}</li>
            <li><strong>Orçamento:</strong> {formatBRL(campaign.dailyBudget)}/dia × {campaign.durationDays} dias = {formatBRL(campaign.dailyBudget * campaign.durationDays)}</li>
            <li><strong>Público:</strong> {campaign.ageMin}–{campaign.ageMax} anos · {campaign.gender === 'all' ? 'Todos' : campaign.gender === 'male' ? 'Masculino' : 'Feminino'}{campaign.interests.length ? ` · ${campaign.interests.join(', ')}` : ''}</li>
            {campaign.metaAdId && <li><strong>ID do anúncio no Meta:</strong> {campaign.metaAdId}</li>}
          </ul>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Texto do anúncio</h2>
            <div className="card-actions">
              {!editingText && campaign.status === 'draft' && (
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setEditingText(true)}>✏️ Editar texto</button>
              )}
            </div>
          </div>
          {editingText ? (
            <>
              <div className="field"><label>Título</label><input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
              <div className="field"><label>Texto</label><textarea rows={8} value={adText} onChange={(e) => setAdText(e.target.value)} /></div>
              <div className="row-actions">
                <button className="btn btn-primary btn-sm" disabled={busy} onClick={saveText}>Salvar texto</button>
                <button className="btn btn-ghost btn-sm" onClick={() => { setEditingText(false); setTitle(campaign.title); setAdText(campaign.adText); }}>Cancelar</button>
              </div>
            </>
          ) : (
            <>
              <blockquote className="ad-preview">
                <div className="ad-title">{campaign.title}</div>
                <pre className="ad-text">{campaign.adText}</pre>
              </blockquote>
              <div className="wa-preview">
                <span>📱 Link de contato:</span>
                <a href={`https://wa.me/${campaign.whatsapp.replace(/\D/g, '')}`} target="_blank" rel="noreferrer">WhatsApp do vendedor ↗</a>
              </div>
            </>
          )}
        </div>
      </div>

      {campaign.metaAdId && (
        <div className="card">
          <div className="card-head">
            <h2>Métricas de desempenho</h2>
            <div className="period-tabs">
              {PERIODS.map((p) => (
                <button key={p.key} className={`tab ${period === p.key ? 'active' : ''}`} onClick={() => setPeriod(p.key)}>{p.label}</button>
              ))}
            </div>
          </div>
          {metrics?.unavailable ? (
            <div className="info-box">{metrics.unavailable}</div>
          ) : metrics ? (
            <div className="metrics-grid">
              <div className="metric"><span className="metric-value">{metrics.metrics.impressions.toLocaleString('pt-BR')}</span><span className="metric-label">Impressões</span></div>
              <div className="metric"><span className="metric-value">{metrics.metrics.clicks.toLocaleString('pt-BR')}</span><span className="metric-label">Cliques</span></div>
              <div className="metric"><span className="metric-value">{metrics.metrics.leads.toLocaleString('pt-BR')}</span><span className="metric-label">Leads (conversas)</span></div>
              <div className="metric"><span className="metric-value">{formatBRL(metrics.metrics.spend)}</span><span className="metric-label">Valor gasto</span></div>
              <div className="metric"><span className="metric-value">{metrics.metrics.costPerLead != null ? formatBRL(metrics.metrics.costPerLead) : '—'}</span><span className="metric-label">Custo por lead</span></div>
            </div>
          ) : (
            <div className="page-loading"><div className="spinner" /></div>
          )}
        </div>
      )}

      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Excluir campanha?</h3>
            <p>Tem certeza que deseja excluir <strong>{campaign.productName}</strong>? Esta ação não pode ser desfeita.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setConfirmDelete(false)}>Cancelar</button>
              <button className="btn btn-danger" disabled={busy} onClick={remove}>{busy ? 'Excluindo...' : 'Excluir definitivamente'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

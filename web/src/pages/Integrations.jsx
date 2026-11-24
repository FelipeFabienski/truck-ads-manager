import { useCallback, useEffect, useState } from 'react';
import { api, formatDate } from '../api.js';
import { useToast } from '../components/Toast.jsx';
import IntegrationStatusBadge from '../components/IntegrationStatusBadge.jsx';

const EMPTY = {
  name: '',
  accessToken: '',
  adAccountId: '',
  pageId: '',
  instagramActorId: '',
  businessId: '',
  appId: '',
  appSecret: '',
  whatsappNumber: '',
};

export default function Integrations() {
  const toast = useToast();
  const [credentials, setCredentials] = useState([]);
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [checks, setChecks] = useState(null);
  const [assets, setAssets] = useState(null);
  const [checkTarget, setCheckTarget] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get(showAll ? '/api/credentials?scope=all' : '/api/credentials');
      setCredentials(data.credentials);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [showAll, toast]);

  useEffect(() => {
    load();
  }, [load]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function startNew() {
    setEditingId(null);
    setForm(EMPTY);
    setAssets(null);
    setChecks(null);
    setShowForm(true);
  }

  function startEdit(c) {
    setEditingId(c.id);
    setForm({
      name: c.name,
      accessToken: '',
      adAccountId: c.adAccountId || '',
      pageId: c.pageId || '',
      instagramActorId: c.instagramActorId || '',
      businessId: c.businessId || '',
      appId: c.appId || '',
      appSecret: '',
      whatsappNumber: c.whatsappNumber || '',
    });
    setAssets(null);
    setChecks(null);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      if (editingId) {
        const data = await api.put(`/api/credentials/${editingId}`, form);
        toast.success(data.message);
        setShowForm(false);
      } else {
        const data = await api.post('/api/credentials', form);
        toast.success(data.message);
        setForm(EMPTY);
        setShowForm(false);
        toast.info('Salve e use "Validar integração" e "Descobrir ativos" no cartão criado.');
      }
      load();
    } catch (err) {
      if (err.fieldErrors) Object.values(err.fieldErrors).forEach((m) => toast.error(m));
      else toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  /** Descoberta de ativos: requer o token salvo (ou um novo token digitado no formulário de edição). */
  async function discover(c) {
    setBusy(true);
    try {
      const payload = form.accessToken && editingId === c.id ? { accessToken: form.accessToken } : {};
      const data = await api.post(`/api/credentials/${c.id}/discover`, payload);
      setAssets(data);
      if (data.errors?.length) data.errors.forEach((e) => toast.error(e));
      else toast.success('Ativos encontrados! Escolha nos campos de seleção do formulário.');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  /** Validação REAL na Graph API — só acontece quando você clica. */
  async function validate(c) {
    setBusy(true);
    setCheckTarget(c.id);
    setChecks(null);
    try {
      const data = await api.post(`/api/credentials/${c.id}/validate`, {});
      if (data.ok) toast.success('Integração validada — status "Conectado"!');
      else toast.error('Validação concluída com pendências — veja os detalhes.');
      setChecks(data.checks);
      load();
    } catch (err) {
      toast.error(err.message);
      if (err.data?.checks) setChecks(err.data.checks);
      load();
    } finally {
      setBusy(false);
    }
  }

  async function action(c, act) {
    setBusy(true);
    try {
      const data =
        act === 'delete'
          ? await api.del(`/api/credentials/${c.id}`)
          : await api.post(`/api/credentials/${c.id}/${act}`, {});
      toast.success(data.message);
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  const datalists = (id) => (
    <>
      <datalist id={`adaccounts-${id}`}>
        {(assets?.adAccounts || []).map((a) => (
          <option key={a.id} value={a.id}>{`${a.name} · ${a.currency || ''}`}</option>
        ))}
      </datalist>
      <datalist id={`pages-${id}`}>
        {(assets?.pages || []).map((p) => (
          <option key={p.id} value={p.id}>{`${p.name}`}</option>
        ))}
      </datalist>
      <datalist id={`igs-${id}`}>
        {(assets?.pages || []).filter((p) => p.instagram).map((p) => (
          <option key={p.instagram.id} value={p.instagram.id}>{`@${p.instagram.username} (página ${p.name})`}</option>
        ))}
      </datalist>
      <datalist id={`biz-${id}`}>
        {(assets?.businesses || []).map((b) => (
          <option key={b.id} value={b.id}>{`${b.name}`}</option>
        ))}
      </datalist>
    </>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Integrações Meta</h1>
          <p className="page-subtitle">
            Conecte contas de anúncios do Facebook/Instagram com o seu próprio Access Token (BYOT).
            Tokens são criptografados e nunca exibidos.
          </p>
        </div>
        <div className="header-actions">
          <label className="btn btn-ghost" style={{ cursor: 'pointer' }}>
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} hidden={false} style={{ display: 'none' }} />
            {showAll ? '👁 Vendo todos (admin)' : '👁 Ver todos os clientes'}
          </label>
          <button className="btn btn-primary" onClick={startNew}>➕ Nova integração</button>
        </div>
      </div>

      <div className="info-box">
        <strong>Como funciona:</strong> no <a href="https://business.facebook.com/settings" target="_blank" rel="noreferrer">Meta Business Suite</a>, gere um token com permissões <code>ads_management</code>, <code>pages_read_engagement</code> e <code>pages_manage_ads</code>. Cadastre aqui com os IDs dos ativos (ou use <strong>Descobrir ativos</strong> para preencher automaticamente). A integração nasce <strong>Pendente de validação</strong> — use <strong>Validar integração</strong> para conectar de fato. Só integrações <strong>Conectadas</strong> publicam.
      </div>

      {checks && (
        <div className="card">
          <h2>Resultado da última validação</h2>
          <ul className="checks-list">
            {checks.map((c) => (
              <li key={c.key} className={c.ok ? 'check-ok' : 'check-fail'}>
                <span>{c.ok ? '✅' : '❌'}</span>
                <div><strong>{c.label}:</strong> {c.detail}</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showForm && (
        <form className="card" onSubmit={submit} noValidate>
          <h2>{editingId ? 'Editar integração' : 'Nova integração Meta'}</h2>
          <div className="form-grid">
            <div className="field"><label>Nome da integração *</label>
              <input value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Ex: Minha conta de anúncios" /></div>
            <div className="field"><label>Número do WhatsApp</label>
              <input value={form.whatsappNumber} onChange={(e) => set('whatsappNumber', e.target.value)} placeholder="Opcional (informativo)" /></div>
            <div className="field span-2"><label>Access Token {editingId ? '(deixe vazio para manter o atual — trocar volta para Pendente)' : '*'}</label>
              <input type="password" autoComplete="off" value={form.accessToken} onChange={(e) => set('accessToken', e.target.value)} placeholder="EAAG..." /></div>
            <div className="field"><label>Ad Account ID (act_ID)</label>
              <input list={editingId ? `adaccounts-${editingId}` : undefined} value={form.adAccountId} onChange={(e) => set('adAccountId', e.target.value)} placeholder="act_123456789 ou 123456789" /></div>
            <div className="field"><label>Page ID (Facebook)</label>
              <input list={editingId ? `pages-${editingId}` : undefined} value={form.pageId} onChange={(e) => set('pageId', e.target.value)} placeholder="1234567890" /></div>
            <div className="field"><label>Instagram Account ID (opcional)</label>
              <input list={editingId ? `igs-${editingId}` : undefined} value={form.instagramActorId} onChange={(e) => set('instagramActorId', e.target.value)} placeholder="17841400000000" /></div>
            <div className="field"><label>Business ID (opcional)</label>
              <input list={editingId ? `biz-${editingId}` : undefined} value={form.businessId} onChange={(e) => set('businessId', e.target.value)} placeholder="1234567890" /></div>
            <div className="field"><label>App ID (opcional)</label>
              <input value={form.appId} onChange={(e) => set('appId', e.target.value)} placeholder="Para detectar expiração do token" /></div>
            <div className="field"><label>App Secret (opcional)</label>
              <input type="password" autoComplete="off" value={form.appSecret} onChange={(e) => set('appSecret', e.target.value)} placeholder="Criptografado como o token" /></div>
          </div>
          <div className="row-actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Salvando...' : editingId ? 'Salvar alterações' : 'Cadastrar (Pendente de validação)'}</button>
            <button className="btn btn-ghost" type="button" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
          {editingId && datalists(editingId)}
        </form>
      )}

      {loading ? (
        <div className="page-loading"><div className="spinner" /></div>
      ) : credentials.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🔗</div>
          <h2>Nenhuma integração cadastrada</h2>
          <p>Cadastre um Access Token do Meta Business Suite para publicar campanhas.</p>
        </div>
      ) : (
        <div className="cred-list">
          {credentials.map((c) => (
            <div className={`cred-card ${c.validationStatus === 'connected' && c.isActive ? 'cred-active' : ''}`} key={c.id}>
              <div className="cred-head">
                <div>
                  <h3>
                    {c.name} {c.isActive ? <span className="badge badge-active">Ativa</span> : <span className="badge badge-draft">Desativada</span>}
                  </h3>
                  {showAll && c.owner && <p className="cred-meta">👤 {c.owner.name} ({c.owner.email})</p>}
                  <p className="cred-meta">
                    <IntegrationStatusBadge status={c.validationStatus} isActive={c.isActive} />
                  </p>
                  <p className="cred-meta">
                    Token: <code>{c.tokenMasked}</code>
                    {c.appSecretMasked && <> · App Secret: <code>{c.appSecretMasked}</code></>}
                  </p>
                  <p className="cred-meta">
                    {c.adAccountId && <>Conta: <code>{c.adAccountId}</code> </>}
                    {c.pageId && <>· Página: <code>{c.pageId}</code> </>}
                    {c.instagramActorId && <>· IG: <code>{c.instagramActorId}</code> </>}
                    {c.businessId && <>· Business: <code>{c.businessId}</code></>}
                  </p>
                  <p className="cred-meta">
                    {c.whatsappNumber && <>WhatsApp: {c.whatsappNumber} · </>}
                    Última validação: {c.lastValidatedAt ? formatDate(c.lastValidatedAt) : '—'}
                    {c.tokenExpiresAt && <> · Token expira: {formatDate(c.tokenExpiresAt)}</>}
                  </p>
                </div>
              </div>
              <div className="row-actions">
                {!c.isActive && (
                  <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => action(c, 'activate')}>Tornar ativa</button>
                )}
                <button className="btn btn-success btn-sm" disabled={busy} onClick={() => validate(c)}>✅ Validar integração</button>
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => discover(c)}>🔍 Descobrir ativos</button>
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => startEdit(c)}>Editar</button>
                <button className="btn btn-warning btn-sm" disabled={busy} onClick={() => action(c, 'toggle')}>{c.isActive ? 'Desabilitar' : 'Habilitar'}</button>
                <button className="btn btn-danger-ghost btn-sm" disabled={busy} onClick={() => window.confirm(`Remover a integração "${c.name}"?`) && action(c, 'delete')}>Remover</button>
              </div>
              {datalists(c.id)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

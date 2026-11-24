import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import { useToast } from '../components/Toast.jsx';

const TIMEZONES = [
  'America/Sao_Paulo', 'America/Manaus', 'America/Belem', 'America/Fortaleza', 'America/Recife',
  'America/Bahia', 'America/Campo_Grande', 'America/Cuiaba', 'America/Porto_Velho',
  'America/Noronha', 'America/Rio_Branco',
];

export default function Profile() {
  const toast = useToast();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [form, setForm] = useState(null);
  const [pw, setPw] = useState({ currentPassword: '', newPassword: '', confirm: '' });
  const [pwErrors, setPwErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [deactivatePassword, setDeactivatePassword] = useState('');

  useEffect(() => {
    api
      .get('/api/profile')
      .then((data) =>
        setForm({
          name: data.user.name,
          email: data.user.email,
          company: data.user.company || '',
          phone: data.user.phone || '',
          timezone: data.user.timezone || 'America/Sao_Paulo',
          avatarPath: data.user.avatarPath,
          createdAt: data.user.createdAt,
          emailVerified: data.user.emailVerified,
        })
      )
      .catch((err) => toast.error(err.message));
  }, [toast]);

  async function saveProfile(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await api.put('/api/profile', { name: form.name, company: form.company, phone: form.phone, timezone: form.timezone });
      toast.success(data.message);
      const me = await api.get('/api/auth/me');
      setUser(me.user);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function uploadAvatar(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      toast.error('A foto deve ter no máximo 2MB.');
      return;
    }
    const fd = new FormData();
    fd.append('avatar', file);
    setBusy(true);
    try {
      const data = await api.postForm('/api/profile/avatar', fd);
      toast.success(data.message);
      setForm((f) => ({ ...f, avatarPath: data.avatarPath }));
      const me = await api.get('/api/auth/me');
      setUser(me.user);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(e) {
    e.preventDefault();
    const errs = {};
    if (!pw.currentPassword) errs.currentPassword = 'Informe a senha atual.';
    if (pw.newPassword.length < 8) errs.newPassword = 'A nova senha precisa ter pelo menos 8 caracteres.';
    if (pw.newPassword !== pw.confirm) errs.confirm = 'As senhas não coincidem.';
    setPwErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    try {
      const data = await api.put('/api/profile/password', { currentPassword: pw.currentPassword, newPassword: pw.newPassword });
      toast.success(data.message);
      setPw({ currentPassword: '', newPassword: '', confirm: '' });
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivate() {
    setBusy(true);
    try {
      const data = await api.post('/api/profile/deactivate', { password: deactivatePassword });
      toast.success(data.message);
      navigate('/login');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!form) return <div className="page-loading"><div className="spinner" /></div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Perfil</h1>
          <p className="page-subtitle">Seus dados pessoais, senha e configurações da conta. Email: {form.email} {form.emailVerified && <span className="badge badge-active">verificado</span>}</p>
        </div>
      </div>

      <div className="detail-grid">
        <form className="card" onSubmit={saveProfile}>
          <h2>Dados pessoais</h2>
          <div className="profile-avatar-row">
            <img className="avatar avatar-lg" src={form.avatarPath ? `/uploads/${form.avatarPath}` : defaultAvatar(form.name)} alt="Foto de perfil" />
            <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer' }}>
              📷 Alterar foto
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden onChange={uploadAvatar} />
            </label>
          </div>
          <div className="form-grid">
            <div className="field"><label>Nome completo *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>Nome da empresa</label><input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Ex: Minha Loja LTDA" /></div>
            <div className="field"><label>Telefone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="(11) 3333-3333" /></div>
            <div className="field">
              <label>Fuso horário</label>
              <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
                {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </div>
          </div>
          <div className="row-actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>Salvar alterações</button>
          </div>
        </form>

        <div>
          <form className="card" onSubmit={changePassword}>
            <h2>Alterar senha</h2>
            <div className="field"><label>Senha atual</label><input type="password" value={pw.currentPassword} onChange={(e) => setPw({ ...pw, currentPassword: e.target.value })} autoComplete="current-password" className={pwErrors.currentPassword ? 'invalid' : ''} />
              {pwErrors.currentPassword && <span className="field-error">{pwErrors.currentPassword}</span>}</div>
            <div className="field"><label>Nova senha (mín. 8)</label><input type="password" value={pw.newPassword} onChange={(e) => setPw({ ...pw, newPassword: e.target.value })} autoComplete="new-password" className={pwErrors.newPassword ? 'invalid' : ''} />
              {pwErrors.newPassword && <span className="field-error">{pwErrors.newPassword}</span>}</div>
            <div className="field"><label>Confirmar nova senha</label><input type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} autoComplete="new-password" className={pwErrors.confirm ? 'invalid' : ''} />
              {pwErrors.confirm && <span className="field-error">{pwErrors.confirm}</span>}</div>
            <div className="row-actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>Alterar senha</button>
            </div>
          </form>

          <div className="card danger-zone">
            <h2>Zona de risco</h2>
            <p className="page-subtitle">Desativar sua conta encerra todas as sessões e bloqueia o acesso. Não exclui suas campanhas.</p>
            <button className="btn btn-danger-ghost" onClick={() => setDeactivateOpen(true)}>Desativar minha conta</button>
          </div>
        </div>
      </div>

      {deactivateOpen && (
        <div className="modal-overlay" onClick={() => setDeactivateOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Desativar conta — confirmação</h3>
            <p>Você não poderá mais fazer login com esta conta. Para confirmar, digite sua senha:</p>
            <input type="password" value={deactivatePassword} onChange={(e) => setDeactivatePassword(e.target.value)} placeholder="Sua senha" autoComplete="current-password" />
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setDeactivateOpen(false)}>Cancelar</button>
              <button className="btn btn-danger" disabled={busy || !deactivatePassword} onClick={deactivate}>{busy ? 'Desativando...' : 'Desativar definitivamente'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function defaultAvatar(name) {
  const initial = (name || '?').trim().charAt(0).toUpperCase();
  return `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="#2590eb"/><text x="40" y="52" font-size="36" font-family="Arial" fill="white" text-anchor="middle">${initial}</text></svg>`
  )}`;
}

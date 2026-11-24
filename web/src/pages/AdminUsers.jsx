import { useCallback, useEffect, useState } from 'react';
import { api, formatDate } from '../api.js';
import { useAuth } from '../AuthContext.jsx';
import { useToast } from '../components/Toast.jsx';

const STATUS_LABEL = {
  active: { label: 'Ativo', cls: 'badge-active' },
  inactive: { label: 'Desativado', cls: 'badge-draft' },
  blocked: { label: 'Bloqueado', cls: 'badge-paused' },
};

export default function AdminUsers() {
  const toast = useToast();
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', senha: '', role: 'user' });
  const [errors, setErrors] = useState({});
  const [resetTarget, setResetTarget] = useState(null);
  const [resetSenha, setResetSenha] = useState('');
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ name: '', role: 'user', status: 'active' });

  const load = useCallback(async () => {
    try {
      const data = await api.get('/api/admin/users');
      setUsers(data.users);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  async function createUser(e) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    try {
      const data = await api.post('/api/admin/users', form);
      toast.success(data.message);
      if (data.devEmailLink) {
        window.prompt('Link de confirmação para encaminhar ao usuário (Ctrl+C):', data.devEmailLink);
      }
      setForm({ name: '', email: '', senha: '', role: 'user' });
      setCreating(false);
      load();
    } catch (err) {
      setErrors(err.fieldErrors || {});
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(u, status) {
    setBusy(true);
    try {
      const data = await api.post(`/api/admin/users/${u.id}/status`, { status });
      toast.success(data.message);
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await api.put(`/api/admin/users/${editing}`, editForm);
      toast.success(data.message);
      setEditing(null);
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await api.post(`/api/admin/users/${resetTarget}/password`, { senha: resetSenha });
      toast.success(data.message);
      setResetTarget(null);
      setResetSenha('');
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
          <h1>Usuários</h1>
          <p className="page-subtitle">Gerencie clientes e administradores — cadastro, ativação, bloqueio e senhas.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>➕ Novo usuário</button>
      </div>

      {loading ? (
        <div className="page-loading"><div className="spinner" /></div>
      ) : (
        <div className="card">
          <table className="admin-table">
            <thead>
              <tr><th>Usuário</th><th>Perfil</th><th>Status</th><th>Campanhas</th><th>Integrações</th><th>Criado em</th><th>Ações</th></tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const s = STATUS_LABEL[u.status] || { label: u.status, cls: '' };
                return (
                  <tr key={u.id}>
                    <td><strong>{u.name}</strong><br /><small className="text-muted">{u.email} {u.emailVerified ? '· ✅ verificado' : '· ⏳ pendente'}</small></td>
                    <td>{u.role === 'admin' ? '👑 Admin' : '👤 Cliente'}</td>
                    <td><span className={`badge ${s.cls}`}>{s.label}</span></td>
                    <td>{u.campaignsCount}</td>
                    <td>{u.credentialsCount}</td>
                    <td><small>{formatDate(u.createdAt)}</small></td>
                    <td>
                      <div className="row-actions" style={{ marginTop: 0 }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(u.id); setEditForm({ name: u.name, role: u.role, status: u.status }); }}>Editar</button>
                        {u.status !== 'active' ? (
                          <button className="btn btn-success btn-sm" disabled={busy} onClick={() => changeStatus(u, 'active')}>Ativar</button>
                        ) : (
                          <button className="btn btn-warning btn-sm" disabled={busy || u.id === me?.id} onClick={() => changeStatus(u, 'blocked')}>Bloquear</button>
                        )}
                        <button className="btn btn-ghost btn-sm" onClick={() => setResetTarget(u.id)}>Nova senha</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <div className="modal-overlay" onClick={() => setCreating(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Novo usuário</h3>
            <p className="page-subtitle">Não há cadastro público — apenas o administrador cria contas. O link de confirmação aparecerá após criar.</p>
            <form onSubmit={createUser} noValidate>
              <div className="field"><label>Nome completo</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={errors.name ? 'invalid' : ''} />
                {errors.name && <span className="field-error">{errors.name}</span>}</div>
              <div className="field"><label>Email</label><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={errors.email ? 'invalid' : ''} />
                {errors.email && <span className="field-error">{errors.email}</span>}</div>
              <div className="field"><label>Senha inicial (mín. 8)</label><input type="password" autoComplete="new-password" value={form.senha} onChange={(e) => setForm({ ...form, senha: e.target.value })} className={errors.senha ? 'invalid' : ''} />
                {errors.senha && <span className="field-error">{errors.senha}</span>}</div>
              <div className="field"><label>Perfil</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="user">Cliente</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setCreating(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Criando...' : 'Criar usuário'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editing !== null && (
        <div className="modal-overlay" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Editar usuário</h3>
            <form onSubmit={saveEdit}>
              <div className="field"><label>Nome</label><input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /></div>
              <div className="field"><label>Perfil</label>
                <select value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
                  <option value="user">Cliente</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>
              <div className="field"><label>Status</label>
                <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
                  <option value="active">Ativo</option>
                  <option value="inactive">Desativado</option>
                  <option value="blocked">Bloqueado</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={busy}>Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {resetTarget !== null && (
        <div className="modal-overlay" onClick={() => setResetTarget(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Redefinir senha</h3>
            <p className="page-subtitle">Defina uma nova senha para o usuário. As sessões dele serão encerradas.</p>
            <form onSubmit={resetPassword}>
              <div className="field"><label>Nova senha (mín. 8)</label>
                <input type="password" autoComplete="new-password" value={resetSenha} onChange={(e) => setResetSenha(e.target.value)} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setResetTarget(null)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={busy || resetSenha.length < 8}>Redefinir</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

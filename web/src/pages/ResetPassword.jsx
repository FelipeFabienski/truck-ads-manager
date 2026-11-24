import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { useToast } from '../components/Toast.jsx';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const toast = useToast();
  const navigate = useNavigate();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = {};
    if (password.length < 8) errs.password = 'A senha precisa ter pelo menos 8 caracteres.';
    if (password !== confirm) errs.confirm = 'As senhas não coincidem.';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      await api.post('/api/auth/reset-password', { token, password });
      setDone(true);
      toast.success('Senha redefinida com sucesso!');
      setTimeout(() => navigate('/login', { replace: true }), 2500);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Link inválido</h1>
          <p className="auth-subtitle">Este link de redefinição não é válido. Solicite um novo em "Esqueci minha senha".</p>
          <div className="auth-links"><Link to="/esqueci-senha">Solicitar novo link</Link></div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit} noValidate>
        <div className="auth-logo">📢 Facilitador<span>de Anúncios</span></div>
        <h1>Nova senha</h1>
        <p className="auth-subtitle">Crie uma nova senha para sua conta.</p>
        {done ? (
          <div className="info-box">Senha alterada! Redirecionando para o login...</div>
        ) : (
          <>
            <div className="field">
              <label htmlFor="password">Nova senha (mín. 8 caracteres)</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" className={errors.password ? 'invalid' : ''} />
              {errors.password && <span className="field-error">{errors.password}</span>}
            </div>
            <div className="field">
              <label htmlFor="confirm">Confirmar nova senha</label>
              <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" className={errors.confirm ? 'invalid' : ''} />
              {errors.confirm && <span className="field-error">{errors.confirm}</span>}
            </div>
            <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
              {loading ? 'Salvando...' : 'Redefinir senha'}
            </button>
          </>
        )}
        <div className="auth-links"><Link to="/login">Voltar ao login</Link></div>
      </form>
    </div>
  );
}

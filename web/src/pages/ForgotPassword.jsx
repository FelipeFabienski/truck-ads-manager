import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useToast } from '../components/Toast.jsx';

export default function ForgotPassword() {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await api.post('/api/auth/forgot-password', { email });
      setResult(data);
      toast.success(data.message);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit} noValidate>
        <div className="auth-logo">📢 Facilitador<span>de Anúncios</span></div>
        <h1>Recuperar senha</h1>
        <p className="auth-subtitle">Informe seu email e enviaremos um link temporário (válido por 30 minutos) para criar uma nova senha.</p>

        {result ? (
          <>
            <div className="info-box">{result.message}</div>
            {result.devEmailLink && (
              <div className="dev-email-box">
                <strong>Modo desenvolvimento (sem SMTP):</strong>
                <a href={result.devEmailLink}>Abrir link de redefinição →</a>
              </div>
            )}
            <button type="button" className="btn btn-primary btn-block" onClick={() => { setResult(null); setEmail(''); }}>
              Enviar para outro email
            </button>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@empresa.com.br" />
            </div>
            <button className="btn btn-primary btn-block" type="submit" disabled={loading || !email}>
              {loading ? 'Enviando...' : 'Enviar link de redefinição'}
            </button>
          </>
        )}

        <div className="auth-links"><Link to="/login">Voltar ao login</Link></div>
      </form>
    </div>
  );
}

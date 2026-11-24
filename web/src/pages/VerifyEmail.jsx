import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import { useToast } from '../components/Toast.jsx';

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const toast = useToast();
  const navigate = useNavigate();
  const token = params.get('token') || '';
  const [state, setState] = useState(token ? 'verifying' : 'missing');

  useEffect(() => {
    if (!token) return;
    api
      .post('/api/auth/verify-email', { token })
      .then((data) => {
        setState('success');
        toast.success(data.message || 'Email confirmado!');
        setTimeout(() => navigate('/login', { replace: true }), 2500);
      })
      .catch((err) => {
        setState('error');
        toast.error(err.message);
      });
  }, [token, toast, navigate]);

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>{state === 'success' ? '✅ Email confirmado!' : state === 'error' ? '❌ Link inválido' : '⏳ Confirmando...'}</h1>
        <p className="auth-subtitle">
          {state === 'success'
            ? 'Sua conta está ativa. Redirecionando para o login...'
            : state === 'error'
              ? 'O link pode ter expirado ou já sido usado. Solicite um novo abaixo.'
              : 'Aguarde um momento enquanto confirmamos seu email.'}
        </p>
        {state === 'error' && <div className="auth-links"><Link to="/cadastro">Voltar ao cadastro</Link></div>}
      </div>
    </div>
  );
}

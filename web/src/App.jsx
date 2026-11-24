import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import VerifyEmail from './pages/VerifyEmail.jsx';
import ForgotPassword from './pages/ForgotPassword.jsx';
import ResetPassword from './pages/ResetPassword.jsx';
import Dashboard from './pages/Dashboard.jsx';
import CampaignWizard from './pages/CampaignWizard.jsx';
import CampaignDetail from './pages/CampaignDetail.jsx';
import Metrics from './pages/Metrics.jsx';
import Integrations from './pages/Integrations.jsx';
import Profile from './pages/Profile.jsx';
import Plans from './pages/Plans.jsx';
import AdminUsers from './pages/AdminUsers.jsx';

function Protected({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-loading"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (adminOnly && user.role !== 'admin') return <Navigate to="/app/dashboard" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      {/* Públicas (cadastro público removido — só o admin cria usuários) */}
      <Route path="/login" element={<Login />} />
      <Route path="/verificar-email" element={<VerifyEmail />} />
      <Route path="/esqueci-senha" element={<ForgotPassword />} />
      <Route path="/redefinir-senha" element={<ResetPassword />} />

      {/* Autenticadas */}
      <Route path="/app/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/app/nova-campanha" element={<Protected><CampaignWizard /></Protected>} />
      <Route path="/app/campanhas/:id" element={<Protected><CampaignDetail /></Protected>} />
      <Route path="/app/metricas" element={<Protected><Metrics /></Protected>} />
      <Route path="/app/integracoes" element={<Protected adminOnly><Integrations /></Protected>} />
      <Route path="/app/usuarios" element={<Protected adminOnly><AdminUsers /></Protected>} />
      <Route path="/app/perfil" element={<Protected><Profile /></Protected>} />
      <Route path="/app/planos" element={<Protected><Plans /></Protected>} />

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

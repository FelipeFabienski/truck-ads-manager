import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext.jsx';

const NAV = [
  { to: '/app/dashboard', label: 'Campanhas', icon: '📋' },
  { to: '/app/nova-campanha', label: 'Nova campanha', icon: '➕' },
  { to: '/app/metricas', label: 'Métricas', icon: '📈' },
  { to: '/app/integracoes', label: 'Integrações', icon: '🔗', adminOnly: true },
  { to: '/app/usuarios', label: 'Usuários', icon: '👥', adminOnly: true },
  { to: '/app/planos', label: 'Planos', icon: '💳' },
  { to: '/app/perfil', label: 'Perfil', icon: '👤' },
];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  const items = NAV.filter((i) => !i.adminOnly || user?.role === 'admin');

  return (
    <div className="app-shell">
      <header className="mobile-topbar">
        <button className="icon-btn" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Abrir menu">☰</button>
        <span className="mobile-logo">📢 Facilitador de Anúncios</span>
        <img className="avatar avatar-sm" src={user?.avatarPath ? `/uploads/${user.avatarPath}` : defaultAvatar(user?.name)} alt="Perfil" onError={(e) => (e.target.src = defaultAvatar(user?.name))} />
      </header>

      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`} onClick={() => setMobileOpen(false)}>
        <div className="sidebar-logo">📢 Facilitador<span>de Anúncios</span></div>
        <nav className="sidebar-nav">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <span className="nav-icon">{item.icon}</span> {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-chip" onClick={() => navigate('/app/perfil')}>
            <img className="avatar avatar-sm" src={user?.avatarPath ? `/uploads/${user.avatarPath}` : defaultAvatar(user?.name)} alt="Perfil" onError={(e) => (e.target.src = defaultAvatar(user?.name))} />
            <div>
              <div className="user-chip-name">{user?.name}</div>
              <div className="user-chip-role">{user?.role === 'admin' ? 'Administrador' : 'Usuário'}</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-block" onClick={handleLogout}>Sair</button>
        </div>
      </aside>

      <main className="main-content">{children}</main>
    </div>
  );
}

function defaultAvatar(name) {
  const initial = (name || '?').trim().charAt(0).toUpperCase();
  const bg = '#2590eb';
  return `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="${bg}"/><text x="40" y="52" font-size="36" font-family="Arial" fill="white" text-anchor="middle">${initial}</text></svg>`
  )}`;
}

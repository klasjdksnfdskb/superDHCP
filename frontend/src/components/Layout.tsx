import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/hooks/useAuth';
import { langSwitch } from '@/i18n';
import {
  LayoutDashboard, Network, FileSearch, Tags,
  Users, Settings, LogOut, Server, Languages
} from 'lucide-react';

export default function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();

  const navItems = [
    { path: '/', label: t('nav.dashboard'), icon: LayoutDashboard },
    { path: '/leases', label: t('nav.leases'), icon: FileSearch },
    { path: '/pools', label: t('nav.pools'), icon: Network },
    { path: '/tags', label: t('nav.tags'), icon: Tags },
    { path: '/users', label: t('nav.users'), icon: Users },
    { path: '/settings', label: t('nav.settings'), icon: Settings },
  ];

  const roleLabel = () => {
    switch (user?.role) {
      case 'superadmin': return t('roles.superadmin');
      case 'admin': return t('roles.admin');
      default: return t('roles.viewer');
    }
  };

  const toggleLang = () => {
    const next = i18n.language.startsWith('zh') ? 'en' : 'zh';
    langSwitch(next);
  };

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Server size={22} style={{ display: 'inline', marginRight: 8 }} />
          super<span>DHCP</span>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(({ path, label, icon: Icon }) => (
            <div
              key={path}
              className={`nav-item ${location.pathname === path ? 'active' : ''}`}
              onClick={() => navigate(path)}
            >
              <Icon size={20} />
              {label}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          {/* Language Switch */}
          <button
            className="btn btn-sm"
            onClick={toggleLang}
            style={{ width: '100%', justifyContent: 'center', marginBottom: 8 }}
            title={i18n.language.startsWith('zh') ? 'Switch to English' : '切换到中文'}
          >
            <Languages size={14} />
            {i18n.language.startsWith('zh') ? 'English' : '中文'}
          </button>

          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>
            {user?.display_name || user?.username}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            {roleLabel()}
          </div>
          <button
            className="btn btn-sm"
            onClick={logout}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <LogOut size={14} /> {t('auth.logout')}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="main-content">
        {children}
      </div>
    </div>
  );
}
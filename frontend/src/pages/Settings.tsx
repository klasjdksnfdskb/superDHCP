import { useState, FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/hooks/useAuth';
import { authAPI } from '@/services/api';
import { Key, Shield, Info } from 'lucide-react';

export default function Settings() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');

    if (newPassword.length < 8) {
      setError(t('auth.passwordMinLength'));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t('auth.passwordMismatch'));
      return;
    }

    setLoading(true);
    try {
      await authAPI.changePassword(oldPassword, newPassword);
      setMessage(t('auth.passwordChanged'));
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || t('auth.changePasswordFailed');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const roleLabel = () => {
    switch (user?.role) {
      case 'superadmin': return t('roles.superadmin');
      case 'admin': return t('roles.admin');
      default: return t('roles.viewer');
    }
  };

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('settings.title')}</div>
      </div>

      <div className="page-content" style={{ maxWidth: 640 }}>
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">
              <Info size={16} style={{ marginRight: 8, display: 'inline' }} />
              {t('settings.accountInfo')}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '12px 24px', fontSize: 14 }}>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.username')}</span>
            <span className="mono">{user?.username}</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.displayName')}</span>
            <span>{user?.display_name || '-'}</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.role')}</span>
            <span className="badge" style={{ background: 'var(--accent-glow)', color: 'var(--accent)', width: 'fit-content' }}>
              {roleLabel()}
            </span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.email')}</span>
            <span>{user?.email || '-'}</span>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Key size={16} style={{ marginRight: 8, display: 'inline' }} />
              {t('settings.changePassword')}
            </div>
          </div>

          {message && (
            <div style={{ padding: '8px 12px', background: 'rgba(34,197,94,0.1)', borderRadius: 'var(--radius)', color: 'var(--success)', fontSize: 13, marginBottom: 16 }}>
              {message}
            </div>
          )}
          {error && (
            <div style={{ padding: '8px 12px', background: 'rgba(239,68,68,0.1)', borderRadius: 'var(--radius)', color: 'var(--danger)', fontSize: 13, marginBottom: 16 }}>
              {error}
            </div>
          )}

          <form onSubmit={handleChangePassword}>
            <div className="form-group">
              <label className="form-label">{t('auth.oldPassword')}</label>
              <input className="input" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">{t('auth.newPassword')}</label>
              <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t('users.passwordPlaceholder')} required />
            </div>
            <div className="form-group">
              <label className="form-label">{t('auth.confirmPassword')}</label>
              <input className="input" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
            </div>
            <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: 8 }}>
              <Shield size={14} /> {loading ? `${t('auth.loggingIn')}` : t('auth.changePassword')}
            </button>
          </form>
        </div>

        <div className="card" style={{ marginTop: 24 }}>
          <div className="card-title" style={{ marginBottom: 12 }}>{t('settings.systemInfo')}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '8px 24px', fontSize: 13 }}>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.version')}</span>
            <span className="mono">superDHCP v1.0.0</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.dhcpv4')}</span>
            <span className="badge badge-active">{t('common.enabled')}</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.dhcpv6')}</span>
            <span className="badge badge-active">{t('common.enabled')}</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.targetPlatform')}</span>
            <span>openEuler 22.03+</span>
            <span style={{ color: 'var(--text-muted)' }}>{t('settings.database')}</span>
            <span>PostgreSQL 15+</span>
          </div>
        </div>
      </div>
    </div>
  );
}
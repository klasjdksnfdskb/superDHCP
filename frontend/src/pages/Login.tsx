import { useState, FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/hooks/useAuth';
import { langSwitch } from '@/i18n';
import { Server, Key, User, Languages } from 'lucide-react';

export default function Login() {
  const { t, i18n } = useTranslation();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const toggleLang = () => {
    const next = i18n.language.startsWith('zh') ? 'en' : 'zh';
    langSwitch(next);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err: unknown) {
      let msg = t('auth.loginFailed');
      const e = err as { code?: string; message?: string; response?: { status?: number; data?: { detail?: string } } };
      if (e.code === 'ERR_NETWORK' || e.message?.includes('Network')) {
        msg = t('auth.networkError');
      } else if (e.response?.status === 401) {
        msg = t('auth.loginFailed');
      } else if (e.response?.data?.detail) {
        msg = e.response.data.detail;
      } else if (e.message) {
        msg = e.message;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Language Switch - top right corner */}
      <button
        className="lang-switch-login"
        onClick={toggleLang}
        title={i18n.language.startsWith('zh') ? 'Switch to English' : '切换到中文'}
      >
        <Languages size={14} />
        <span>{i18n.language.startsWith('zh') ? 'EN' : '中文'}</span>
      </button>

      <div className="login-card">
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Server size={48} color="var(--accent)" style={{ marginBottom: 12 }} />
        </div>
        <h1 className="login-title">{t('auth.title')}</h1>
        <p className="login-subtitle">{t('auth.subtitle')}</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">
              <User size={14} style={{ display: 'inline', marginRight: 4 }} />
              {t('auth.username')}
            </label>
            <input
              className="input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('auth.usernamePlaceholder')}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <Key size={14} style={{ display: 'inline', marginRight: 4 }} />
              {t('auth.password')}
            </label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('auth.passwordPlaceholder')}
            />
          </div>

          {error && (
            <div style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 16, textAlign: 'center' }}>
              {error}
            </div>
          )}

          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ width: '100%', padding: '12px 0', fontSize: 15, marginTop: 8 }}
          >
            {loading ? t('auth.loggingIn') : t('auth.login')}
          </button>
        </form>

        <p style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', marginTop: 24 }}>
          {t('auth.defaultAccount')}
        </p>
      </div>
    </div>
  );
}
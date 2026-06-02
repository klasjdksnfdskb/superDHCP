import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usersAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { Key, UserPlus } from 'lucide-react';

interface UserItem {
  id: string;
  username: string;
  display_name?: string;
  email?: string;
  role: string;
  is_active: boolean;
  require_password_change: boolean;
  last_login?: string;
  created_at?: string;
}

export default function UserManagement() {
  const { t } = useTranslation();
  const { user: currentUser, isAdmin } = useAuth();
  const isSuperAdmin = currentUser?.role === 'superadmin';
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showResetPwd, setShowResetPwd] = useState<string | null>(null);

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newDisplayName, setNewDisplayName] = useState('');
  const [newRole, setNewRole] = useState('viewer');
  const [resetPassword, setResetPassword] = useState('');

  const fetchUsers = async () => {
    try {
      const { data } = await usersAPI.list();
      setUsers(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = async () => {
    if (!newUsername || !newPassword) return;
    try {
      await usersAPI.create({
        username: newUsername,
        password: newPassword,
        display_name: newDisplayName,
        role: newRole,
      });
      setShowCreate(false);
      setNewUsername('');
      setNewPassword('');
      setNewDisplayName('');
      setNewRole('viewer');
      fetchUsers();
    } catch (err) {
      console.error(err);
    }
  };

  const handleResetPwd = async () => {
    if (!showResetPwd || !resetPassword) return;
    try {
      await usersAPI.resetPassword(showResetPwd, resetPassword, true);
      setShowResetPwd(null);
      setResetPassword('');
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string, username: string) => {
    if (!confirm(t('users.deleteConfirm', { username }))) return;
    try {
      await usersAPI.delete(id);
      fetchUsers();
    } catch (err) {
      console.error(err);
    }
  };

  const roleLabel = (role: string) => {
    switch (role) {
      case 'superadmin': return { text: t('users.superadmin'), color: 'var(--danger)' };
      case 'admin': return { text: t('users.admin'), color: 'var(--accent)' };
      case 'viewer': return { text: t('users.viewer'), color: 'var(--text-muted)' };
      default: return { text: role, color: 'var(--text-muted)' };
    }
  };

  if (loading) return <div className="empty">{t('common.loading')}</div>;

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('users.title')}</div>
        {isAdmin && (
          <div className="topbar-actions">
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              <UserPlus size={14} /> {t('users.createUser')}
            </button>
          </div>
        )}
      </div>

      <div className="page-content">
        <div className="card">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('users.username')}</th>
                  <th>{t('users.displayName')}</th>
                  <th>{t('users.email')}</th>
                  <th>{t('users.role')}</th>
                  <th>{t('users.status')}</th>
                  <th>{t('users.lastLogin')}</th>
                  <th>{t('users.createdAt')}</th>
                  {isAdmin && <th>{t('common.action')}</th>}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const rl = roleLabel(u.role);
                  return (
                    <tr key={u.id}>
                      <td>
                        <span className="mono" style={{ fontWeight: 600 }}>{u.username}</span>
                        {u.require_password_change && (
                          <span className="badge badge-expired" style={{ marginLeft: 8 }}>{t('users.needChangePwd')}</span>
                        )}
                      </td>
                      <td>{u.display_name || '-'}</td>
                      <td>{u.email || '-'}</td>
                      <td>
                        <span className="badge" style={{ background: 'transparent', color: rl.color, border: `1px solid ${rl.color}` }}>
                          {rl.text}
                        </span>
                      </td>
                      <td>
                        {u.is_active
                          ? <span className="badge badge-active">{t('users.active')}</span>
                          : <span className="badge badge-expired">{t('users.inactive')}</span>}
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {u.last_login ? new Date(u.last_login).toLocaleString() : t('users.neverLogin')}
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {u.created_at ? new Date(u.created_at).toLocaleString() : '-'}
                      </td>
                      {isAdmin && (
                        <td>
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button className="btn btn-sm" onClick={() => setShowResetPwd(u.id)} title={t('users.resetPassword')}>
                              <Key size={12} />
                            </button>
                            {isSuperAdmin && u.username !== currentUser?.username && (
                              <button className="btn btn-sm btn-danger" onClick={() => handleDelete(u.id, u.username)} title={t('common.delete')}>
                                <span>✕</span>
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{t('users.createUserTitle')}</h2>
            <div className="form-group">
              <label className="form-label">{t('users.username')}</label>
              <input className="input" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('users.password')}</label>
              <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('users.displayName')}</label>
              <input className="input" value={newDisplayName} onChange={(e) => setNewDisplayName(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('users.role')}</label>
              <select className="input" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
                {isSuperAdmin && <option value="superadmin">{t('users.superadmin')}</option>}
                <option value="admin">{t('users.admin')}</option>
                <option value="viewer">{t('users.viewer')}</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn" onClick={() => setShowCreate(false)}>{t('common.cancel')}</button>
              <button className="btn btn-primary" onClick={handleCreate}>{t('common.create')}</button>
            </div>
          </div>
        </div>
      )}

      {showResetPwd && (
        <div className="modal-overlay" onClick={() => setShowResetPwd(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{t('users.resetPasswordTitle')}</h2>
            <div className="form-group">
              <label className="form-label">{t('users.newPassword')}</label>
              <input
                className="input"
                type="password"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                placeholder={t('users.passwordPlaceholder')}
              />
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn" onClick={() => setShowResetPwd(null)}>{t('common.cancel')}</button>
              <button className="btn btn-primary" onClick={handleResetPwd}>{t('users.resetPassword')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
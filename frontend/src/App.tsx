import { useTranslation } from 'react-i18next';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import ErrorBoundary from '@/components/ErrorBoundary';
import Layout from '@/components/Layout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import LeaseManagement from '@/pages/LeaseManagement';
import PoolManagement from '@/pages/PoolManagement';
import TagManagement from '@/pages/TagManagement';
import UserManagement from '@/pages/UserManagement';
import Settings from '@/pages/Settings';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const { t } = useTranslation();
  if (loading) return <div className="login-page"><p>{t('common.loading')}</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-page">
        <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
          superDHCP...
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route
        path="/*"
        element={
          <PrivateRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/leases" element={<LeaseManagement />} />
                <Route path="/pools" element={<PoolManagement />} />
                <Route path="/pools/:id" element={<PoolManagement />} />
                <Route path="/tags" element={<TagManagement />} />
                <Route path="/users" element={<UserManagement />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
    </ErrorBoundary>
  );
}
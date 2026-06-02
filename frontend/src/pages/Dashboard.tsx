import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { dashboardAPI } from '@/services/api';
import StatCard from '@/components/StatCard';
import PoolGauge from '@/components/PoolGauge';
import {
  Users, Network, Globe, Clock, Wifi, Radio
} from 'lucide-react';

interface DashboardData {
  total_leases: number;
  active_leases: number;
  expired_leases: number;
  new_today: number;
  v4_active: number;
  v6_stateful: number;
  v6_stateless: number;
  vlan_distribution: Array<{ vlan_id: number; count: number }>;
  pools: Array<{
    id: string;
    name: string;
    vlan_ids: number[];
    stats: {
      total_capacity: number;
      total_used: number;
      total_free: number;
      usage_percent: number;
      subnets: Array<{
        subnet: string;
        netmask: string;
        gateway?: string;
        range: string;
        capacity: number;
        used: number;
        available: number;
        usage_percent: number;
      }>;
    };
  }>;
  pool_summary: {
    count: number;
    total_capacity: number;
    total_used: number;
    total_free: number;
  };
}

export default function Dashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardAPI.stats().then(({ data }) => {
      setData(data);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty">{t('common.loading')}</div>;
  if (!data) return <div className="empty">{t('common.loading')}</div>;

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('dashboard.title')}</div>
        <div className="topbar-actions">
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {t('dashboard.subtitle')}
          </span>
        </div>
      </div>

      <div className="page-content">
        <div className="stats-grid">
          <StatCard
            title={t('dashboard.activeLeases')}
            value={data.active_leases}
            subtitle={t('dashboard.totalLeases', { count: data.total_leases })}
            icon={<Users size={48} />}
            color="var(--accent)"
            trend={{ value: data.new_today > 0 ? 5 : 0, label: t('dashboard.todayNew') }}
          />
          <StatCard
            title={t('dashboard.ipv4Active')}
            value={data.v4_active}
            subtitle={t('dashboard.ipv4Subtitle')}
            icon={<Network size={48} />}
            color="var(--success)"
          />
          <StatCard
            title={t('dashboard.ipv6Stateful')}
            value={data.v6_stateful}
            subtitle={t('dashboard.ipv6StatefulSubtitle')}
            icon={<Globe size={48} />}
            color="var(--info)"
          />
          <StatCard
            title={t('dashboard.ipv6Stateless')}
            value={data.v6_stateless}
            subtitle={t('dashboard.ipv6StatelessSubtitle')}
            icon={<Radio size={48} />}
            color="var(--warning)"
          />
          <StatCard
            title={t('dashboard.todayNew')}
            value={data.new_today}
            subtitle={t('dashboard.todayNewSubtitle')}
            icon={<Clock size={48} />}
            color="var(--success)"
          />
          <StatCard
            title={t('dashboard.poolCount')}
            value={data.pool_summary.count}
            subtitle={t('dashboard.poolCountSubtitle', { count: data.pool_summary.total_capacity })}
            icon={<Wifi size={48} />}
            color="var(--accent)"
          />
        </div>

        <div style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>{t('dashboard.poolUsage')}</h3>
          <div className="stats-grid">
            {data.pools.map((pool) => (
              <PoolGauge
                key={pool.id}
                name={pool.name}
                total_capacity={pool.stats.total_capacity}
                total_used={pool.stats.total_used}
                total_free={pool.stats.total_free}
                usage_percent={pool.stats.usage_percent}
                subnets={pool.stats.subnets}
              />
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>{t('dashboard.vlanDistribution')}</div>
          {data.vlan_distribution.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.vlan_distribution.map((v) => (
                <div key={v.vlan_id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-primary)', minWidth: 80 }}>
                    VLAN {v.vlan_id}
                  </span>
                  <div className="gauge-bar" style={{ flex: 1 }}>
                    <div
                      className="gauge-fill"
                      style={{
                        width: `${Math.min((v.count / data.active_leases) * 300, 100)}%`,
                        background: 'var(--accent)',
                      }}
                    />
                  </div>
                  <span className="mono" style={{ fontSize: 13, color: 'var(--text-secondary)', minWidth: 60, textAlign: 'right' }}>
                    {v.count.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{t('dashboard.noVlanData')}</div>
          )}
        </div>
      </div>
    </div>
  );
}
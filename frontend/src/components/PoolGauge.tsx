import { useTranslation } from 'react-i18next';

interface SubnetInfo {
  subnet: string;
  netmask: string;
  gateway?: string;
  range: string;
  capacity: number;
  used: number;
  available: number;
  usage_percent: number;
}

interface PoolGaugeProps {
  name: string;
  total_capacity: number;
  total_used: number;
  total_free: number;
  usage_percent: number;
  subnets?: SubnetInfo[];
}

export default function PoolGauge({ name, total_capacity, total_used, total_free, usage_percent, subnets }: PoolGaugeProps) {
  const { t } = useTranslation();

  const getColor = (pct: number) => {
    if (pct > 85) return 'var(--danger)';
    if (pct > 65) return 'var(--warning)';
    return 'var(--accent)';
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">{name}</div>
        <span className="badge badge-active">{t('pools.percentUsed', { pct: usage_percent })}</span>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('dashboard.totalUsage')}</span>
          <span className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {total_used.toLocaleString()} / {total_capacity.toLocaleString()}
          </span>
        </div>
        <div className="gauge-bar" style={{ height: 12 }}>
          <div
            className="gauge-fill"
            style={{ width: `${usage_percent}%`, background: getColor(usage_percent) }}
          />
        </div>
        <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
          <span>{t('dashboard.free')}: {total_free.toLocaleString()}</span>
          <span>{t('dashboard.used')}: {total_used.toLocaleString()}</span>
          <span>{t('dashboard.total')}: {total_capacity.toLocaleString()}</span>
        </div>
      </div>

      {subnets && subnets.length > 0 && (
        <div className="gauge-container">
          {subnets.map((s, idx) => (
            <div key={idx} className="gauge-item">
              <div className="gauge-label">
                <div className="mono" style={{ fontSize: 13 }}>{s.subnet}/{s.netmask}</div>
                {s.gateway && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>GW: {s.gateway}</div>
                )}
              </div>
              <div style={{ flex: 1 }}>
                <div className="gauge-bar">
                  <div
                    className="gauge-fill"
                    style={{
                      width: `${s.usage_percent}%`,
                      background: getColor(s.usage_percent),
                    }}
                  />
                </div>
              </div>
              <div className="gauge-stats">
                <div className="mono">{s.available.toLocaleString()} {t('dashboard.free')}</div>
                <div>{s.used.toLocaleString()} {t('dashboard.used')}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
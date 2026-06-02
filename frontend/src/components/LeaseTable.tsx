import { useTranslation } from 'react-i18next';

export interface LeaseItem {
  mac_address: string;
  dhcpv4_address?: string;
  dhcpv6_address?: string;
  dhcpv6_mode?: string;
  dhcpv4_lease_end?: string;
  dhcpv6_lease_end?: string;
  vlan_id?: number;
  hostname?: string;
  state?: string;
  pool_name?: string;
  custom_tag_path?: string;
  option43?: Record<string, unknown>;
}

interface LeaseTableProps {
  leases: LeaseItem[];
  onRelease?: (mac: string) => void;
  isAdmin?: boolean;
}

export default function LeaseTable({ leases, onRelease, isAdmin }: LeaseTableProps) {
  const { t } = useTranslation();

  const stateBadge = (state?: string) => {
    switch (state) {
      case 'active': return <span className="badge badge-active">{t('leases.active')}</span>;
      case 'expired': return <span className="badge badge-expired">{t('leases.expired')}</span>;
      case 'released': return <span className="badge badge-released">{t('leases.released')}</span>;
      default: return <span className="badge">{t('leases.unknown')}</span>;
    }
  };

  const v6ModeLabel = (mode?: string) => {
    switch (mode) {
      case 'stateful': return t('leases.stateful');
      case 'stateless': return t('leases.stateless');
      case 'slaac': return t('leases.slaac');
      default: return mode || '-';
    }
  };

  const formatTime = (iso?: string) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString();
  };

  if (leases.length === 0) {
    return <div className="empty">{t('leases.noLeases')}</div>;
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>{t('leases.macAddress')}</th>
            <th>{t('leases.ipv4')}</th>
            <th>{t('leases.ipv6')}</th>
            <th>{t('leases.v6Mode')}</th>
            <th>{t('leases.v4Expiry')}</th>
            <th>{t('leases.v6Expiry')}</th>
            <th>{t('leases.vlan')}</th>
            <th>{t('leases.pool')}</th>
            <th>{t('leases.org')}</th>
            <th>{t('common.status')}</th>
            {isAdmin && <th>{t('common.action')}</th>}
          </tr>
        </thead>
        <tbody>
          {leases.map((l) => (
            <tr key={l.mac_address}>
              <td className="mono">
                <span style={{ color: 'var(--accent)' }}>{l.mac_address}</span>
                {l.hostname && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{l.hostname}</div>
                )}
              </td>
              <td className="mono">{l.dhcpv4_address || '-'}</td>
              <td className="mono" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {l.dhcpv6_address || '-'}
              </td>
              <td>{l.dhcpv6_mode ? v6ModeLabel(l.dhcpv6_mode) : '-'}</td>
              <td style={{ fontSize: 11 }}>{formatTime(l.dhcpv4_lease_end)}</td>
              <td style={{ fontSize: 11 }}>{formatTime(l.dhcpv6_lease_end)}</td>
              <td>{l.vlan_id ?? '-'}</td>
              <td>{l.pool_name || '-'}</td>
              <td style={{ fontSize: 11, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {l.custom_tag_path || '-'}
              </td>
              <td>{stateBadge(l.state)}</td>
              {isAdmin && (
                <td>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => onRelease?.(l.mac_address)}
                  >
                    {t('common.release')}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
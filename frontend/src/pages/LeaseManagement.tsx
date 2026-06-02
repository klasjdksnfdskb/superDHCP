import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { leasesAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import LeaseTable, { LeaseItem } from '@/components/LeaseTable';
import { Search, Download } from 'lucide-react';

export default function LeaseManagement() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [leases, setLeases] = useState<LeaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [vlanFilter, setVlanFilter] = useState('');

  const fetchLeases = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number | undefined> = {
        page,
        page_size: pageSize,
        sort_by: 'last_updated',
        sort_desc: 'true',
      };
      if (search) params.search = search;
      if (stateFilter) params.state = stateFilter;
      if (vlanFilter) params.vlan_id = Number(vlanFilter);

      const { data } = await leasesAPI.list(params);
      setLeases(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, stateFilter, vlanFilter]);

  useEffect(() => { fetchLeases(); }, [fetchLeases]);

  const handleRelease = async (mac: string) => {
    if (!confirm(t('leases.releaseConfirm', { mac }))) return;
    try {
      await leasesAPI.release(mac);
      fetchLeases();
    } catch (err) {
      console.error(err);
    }
  };

  const handleExport = async () => {
    try {
      const params: Record<string, string | undefined> = {};
      if (stateFilter) params.state = stateFilter;
      if (vlanFilter) params.vlan_id = vlanFilter;

      const { data } = await leasesAPI.exportCsv(params);
      const url = window.URL.createObjectURL(new Blob([data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `dhcp_leases_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('leases.title')}</div>
        <div className="topbar-actions">
          <button className="btn btn-success" onClick={handleExport}>
            <Download size={14} /> {t('leases.exportCsv')}
          </button>
        </div>
      </div>

      <div className="page-content">
        <div className="filters-bar">
          <Search size={16} color="var(--text-muted)" />
          <input
            className="input"
            placeholder={t('leases.searchPlaceholder')}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ minWidth: 240 }}
          />
          <select
            className="input"
            value={stateFilter}
            onChange={(e) => { setStateFilter(e.target.value); setPage(1); }}
            style={{ width: 120 }}
          >
            <option value="">{t('leases.allStates')}</option>
            <option value="active">{t('leases.active')}</option>
            <option value="expired">{t('leases.expired')}</option>
            <option value="released">{t('leases.released')}</option>
          </select>
          <input
            className="input"
            placeholder={t('leases.vlanFilter')}
            value={vlanFilter}
            onChange={(e) => { setVlanFilter(e.target.value); setPage(1); }}
            style={{ width: 120 }}
            type="number"
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {t('leases.totalCount', { count: total })}
          </span>
        </div>

        {loading ? (
          <div className="empty">{t('common.loading')}</div>
        ) : (
          <LeaseTable leases={leases} onRelease={handleRelease} isAdmin={isAdmin} />
        )}

        {totalPages > 1 && (
          <div className="pagination">
            <button className="pagination-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              {t('leases.previous')}
            </button>
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => {
              const p = i + 1 + Math.max(0, page - 5);
              if (p > totalPages) return null;
              return (
                <button key={p} className={`pagination-btn ${p === page ? 'active' : ''}`} onClick={() => setPage(p)}>
                  {p}
                </button>
              );
            })}
            <button className="pagination-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              {t('leases.next')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
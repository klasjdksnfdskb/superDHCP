import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { poolsAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import PoolGauge from '@/components/PoolGauge';
import { Plus, Trash2, Edit2, Network } from 'lucide-react';

interface Pool {
  id: string;
  name: string;
  vlan_ids: number[];
  vlan_fallback: boolean;
  description?: string;
  stats: {
    total_capacity: number;
    total_used: number;
    total_free: number;
    usage_percent: number;
    subnets: Array<Record<string, unknown>>;
  };
}

export default function PoolManagement() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [pools, setPools] = useState<Pool[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [addName, setAddName] = useState('');
  const [addDesc, setAddDesc] = useState('');
  const [addVlans, setAddVlans] = useState('');

  const fetchPools = async () => {
    try {
      const { data } = await poolsAPI.list();
      setPools(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPools(); }, []);

  const handleAdd = async () => {
    if (!addName.trim()) return;
    try {
      await poolsAPI.create({
        name: addName,
        description: addDesc,
        vlan_ids: addVlans ? addVlans.split(',').map(Number) : [],
      });
      setShowAddModal(false);
      setAddName('');
      setAddDesc('');
      setAddVlans('');
      fetchPools();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(t('pools.deleteConfirm', { name }))) return;
    try {
      await poolsAPI.delete(id);
      fetchPools();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="empty">{t('common.loading')}</div>;

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('pools.title')}</div>
        {isAdmin && (
          <div className="topbar-actions">
            <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
              <Plus size={14} /> {t('pools.createPool')}
            </button>
          </div>
        )}
      </div>

      <div className="page-content">
        {pools.length === 0 ? (
          <div className="empty">
            <Network size={48} />
            <p>{t('pools.noPools')}</p>
            {isAdmin && (
              <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
                {t('pools.createFirst')}
              </button>
            )}
          </div>
        ) : (
          <div className="stats-grid">
            {pools.map((pool) => (
              <div key={pool.id} style={{ position: 'relative' }}>
                <PoolGauge
                  name={pool.name}
                  total_capacity={pool.stats.total_capacity}
                  total_used={pool.stats.total_used}
                  total_free={pool.stats.total_free}
                  usage_percent={pool.stats.usage_percent}
                  subnets={pool.stats.subnets as Array<{
                    subnet: string; netmask: string; gateway?: string;
                    range: string; capacity: number; used: number;
                    available: number; usage_percent: number;
                  }>}
                />
                {isAdmin && (
                  <div style={{ position: 'absolute', top: 12, right: 12, display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm" title={t('common.edit')}>
                      <Edit2 size={12} />
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(pool.id, pool.name)} title={t('common.delete')}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                )}
                {pool.vlan_ids && pool.vlan_ids.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {pool.vlan_ids.map((v) => (
                      <span key={v} className="badge" style={{ background: 'var(--accent-glow)', color: 'var(--accent)' }}>
                        VLAN {v}
                      </span>
                    ))}
                  </div>
                )}
                {pool.description && (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                    {pool.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{t('pools.createPool')}</h2>
            <div className="form-group">
              <label className="form-label">{t('pools.poolName')}</label>
              <input className="input" value={addName} onChange={(e) => setAddName(e.target.value)} placeholder={t('pools.poolNamePlaceholder')} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('pools.description')}</label>
              <input className="input" value={addDesc} onChange={(e) => setAddDesc(e.target.value)} placeholder={t('pools.descriptionPlaceholder')} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('pools.bindVlan')}</label>
              <input className="input" value={addVlans} onChange={(e) => setAddVlans(e.target.value)} placeholder={t('pools.vlanPlaceholder')} />
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn" onClick={() => setShowAddModal(false)}>{t('common.cancel')}</button>
              <button className="btn btn-primary" onClick={handleAdd}>{t('common.create')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
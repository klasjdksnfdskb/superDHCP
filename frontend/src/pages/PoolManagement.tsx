import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { poolsAPI, tagsAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import PoolGauge from '@/components/PoolGauge';
import { Plus, Trash2, Edit2, Network, X, Globe } from 'lucide-react';

interface Pool {
  id: string;
  name: string;
  vlan_ids: number[];
  vlan_fallback: boolean;
  tag_id?: string | null;
  tag_name?: string | null;
  description?: string;
  stats: {
    total_capacity: number;
    total_used: number;
    total_free: number;
    usage_percent: number;
    subnets: Array<Record<string, unknown>>;
  };
}

interface Tag {
  id: string;
  name: string;
  slug: string;
  level: number;
  full_path?: string;
}

interface SubnetDraft {
  subnet: string;
  netmask: string;
  gateway: string;
  dns_servers: string;
  range_start: string;
  range_end: string;
  ip_version: number;
  lease_time: string;
  option_data: string;
}

const emptySubnet = (v: number): SubnetDraft => ({
  subnet: '',
  netmask: '',
  gateway: '',
  dns_servers: '',
  range_start: '',
  range_end: '',
  ip_version: v,
  lease_time: '86400',
  option_data: '',
});

export default function PoolManagement() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [pools, setPools] = useState<Pool[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  // Pool form state
  const [addName, setAddName] = useState('');
  const [addDesc, setAddDesc] = useState('');
  const [addVlans, setAddVlans] = useState('');
  const [addTagId, setAddTagId] = useState('');
  const [subnets, setSubnets] = useState<SubnetDraft[]>([emptySubnet(4)]);

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

  const fetchTags = async () => {
    try {
      const { data } = await tagsAPI.list();
      // API returns flat list with level
      setTags(Array.isArray(data) ? data : []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => { fetchPools(); fetchTags(); }, []);

  const resetForm = () => {
    setAddName('');
    setAddDesc('');
    setAddVlans('');
    setAddTagId('');
    setSubnets([emptySubnet(4)]);
  };

  const handleAdd = async () => {
    if (!addName.trim()) return;
    try {
      const payload: Record<string, unknown> = {
        name: addName,
        description: addDesc || undefined,
        vlan_ids: addVlans ? addVlans.split(',').map(Number) : [],
        tag_id: addTagId || undefined,
        domain_name: undefined,
        subnets: subnets
          .filter((sn) => sn.subnet.trim() && sn.range_start.trim())
          .map((sn) => ({
            subnet: sn.subnet.trim(),
            netmask: sn.netmask.trim(),
            gateway: sn.gateway.trim() || undefined,
            dns_servers: sn.dns_servers.trim()
              ? sn.dns_servers.split(',').map((s) => s.trim())
              : undefined,
            range_start: sn.range_start.trim(),
            range_end: sn.range_end.trim(),
            ip_version: sn.ip_version,
            lease_time: sn.lease_time ? parseInt(sn.lease_time, 10) : undefined,
            option_data: sn.option_data.trim() ? JSON.parse(sn.option_data) : undefined,
          })),
      };
      await poolsAPI.create(payload);
      setShowAddModal(false);
      resetForm();
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

  const addSubnetRow = () => setSubnets([...subnets, emptySubnet(4)]);
  const removeSubnetRow = (i: number) => {
    if (subnets.length <= 1) return;
    setSubnets(subnets.filter((_, idx) => idx !== i));
  };
  const updateSubnet = (i: number, key: keyof SubnetDraft, val: string | number) => {
    setSubnets(subnets.map((sn, idx) => idx === i ? { ...sn, [key]: val } : sn));
  };

  const openAddModal = () => {
    resetForm();
    fetchTags();
    setShowAddModal(true);
  };

  if (loading) return <div className="empty">{t('common.loading')}</div>;

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('pools.title')}</div>
        {isAdmin && (
          <div className="topbar-actions">
            <button className="btn btn-primary" onClick={openAddModal}>
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
              <button className="btn btn-primary" onClick={openAddModal}>
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
                {pool.tag_name && (
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--accent)' }}>
                    <Globe size={11} style={{ display: 'inline', marginRight: 3 }} />
                    {pool.tag_name}
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

      {/* ─── Expanded Create Modal ─── */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => { setShowAddModal(false); resetForm(); }}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 680, maxHeight: '85vh', overflow: 'auto' }}>
            <h2 className="modal-title">{t('pools.createPool')}</h2>

            {/* ═══ Section 1: Basic Info ═══ */}
            <fieldset style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
              <legend style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 13, padding: '0 6px' }}>
                {t('pools.poolInfo')}
              </legend>

              <div className="form-group">
                <label className="form-label">{t('pools.poolName')} *</label>
                <input className="input" value={addName} onChange={(e) => setAddName(e.target.value)}
                  placeholder={t('pools.poolNamePlaceholder')} autoFocus />
              </div>

              <div className="form-group">
                <label className="form-label">{t('pools.description')}</label>
                <input className="input" value={addDesc} onChange={(e) => setAddDesc(e.target.value)}
                  placeholder={t('pools.descriptionPlaceholder')} />
              </div>

              <div className="form-group">
                <label className="form-label">{t('pools.orgTag')}</label>
                <select className="input" value={addTagId} onChange={(e) => setAddTagId(e.target.value)}
                  style={{ appearance: 'auto' }}>
                  <option value="">{t('pools.noOrgTag')}</option>
                  {tags.map((tag) => (
                    <option key={tag.id} value={tag.id}>
                      {'\u00A0\u00A0'.repeat(tag.level)}{tag.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">{t('pools.bindVlan')}</label>
                <input className="input" value={addVlans} onChange={(e) => setAddVlans(e.target.value)}
                  placeholder={t('pools.vlanPlaceholder')} />
              </div>
            </fieldset>

            {/* ═══ Section 2: Subnet Config ═══ */}
            <fieldset style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
              <legend style={{ color: 'var(--accent)', fontWeight: 600, fontSize: 13, padding: '0 6px' }}>
                {t('pools.subnetConfig')}
              </legend>

              {subnets.map((sn, i) => (
                <div key={i} style={{
                  border: '1px dashed var(--border)', borderRadius: 6, padding: '10px 12px',
                  marginBottom: 12, background: i % 2 === 0 ? 'var(--bg-secondary)' : 'transparent',
                  position: 'relative'
                }}>
                  {/* IP version toggle */}
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 10 }}>
                    <div style={{ display: 'flex', gap: 0 }}>
                      <button
                        className={sn.ip_version === 4 ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                        style={{ borderRadius: '4px 0 0 4px', padding: '4px 12px' }}
                        onClick={() => updateSubnet(i, 'ip_version', 4)}>IPv4</button>
                      <button
                        className={sn.ip_version === 6 ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                        style={{ borderRadius: '0 4px 4px 0', padding: '4px 12px' }}
                        onClick={() => updateSubnet(i, 'ip_version', 6)}>IPv6</button>
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {t('pools.subnetConfig')} #{i + 1}
                    </span>
                    {subnets.length > 1 && (
                      <button className="btn btn-sm btn-danger" style={{ marginLeft: 'auto', padding: '2px 8px' }}
                        onClick={() => removeSubnetRow(i)} title={t('pools.removeSubnet')}>
                        <X size={12} />
                      </button>
                    )}
                  </div>

                  {/* Row: subnet + netmask */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div className="form-group">
                      <label className="form-label">{t('pools.subnet')}</label>
                      <input className="input" value={sn.subnet} placeholder={t('pools.subnetPlaceholder')}
                        onChange={(e) => updateSubnet(i, 'subnet', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">{t('pools.netmask')}</label>
                      <input className="input" value={sn.netmask} placeholder={t('pools.netmaskPlaceholder')}
                        onChange={(e) => updateSubnet(i, 'netmask', e.target.value)} />
                    </div>
                  </div>

                  {/* Row: gateway + DNS */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div className="form-group">
                      <label className="form-label">{t('pools.gateway')}</label>
                      <input className="input" value={sn.gateway} placeholder={t('pools.gatewayPlaceholder')}
                        onChange={(e) => updateSubnet(i, 'gateway', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">{t('pools.dnsServers')}</label>
                      <input className="input" value={sn.dns_servers} placeholder={t('pools.dnsPlaceholder')}
                        onChange={(e) => updateSubnet(i, 'dns_servers', e.target.value)} />
                    </div>
                  </div>

                  {/* Row: range start + end */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div className="form-group">
                      <label className="form-label">{t('pools.rangeStart')} *</label>
                      <input className="input" value={sn.range_start} placeholder="10.0.0.2"
                        onChange={(e) => updateSubnet(i, 'range_start', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">{t('pools.rangeEnd')} *</label>
                      <input className="input" value={sn.range_end} placeholder="10.0.0.254"
                        onChange={(e) => updateSubnet(i, 'range_end', e.target.value)} />
                    </div>
                  </div>

                  {/* Row: lease time + DHCP options */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div className="form-group">
                      <label className="form-label">{t('pools.leaseTime')}</label>
                      <input className="input" value={sn.lease_time} placeholder={t('pools.leaseTimePlaceholder')}
                        onChange={(e) => updateSubnet(i, 'lease_time', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">{t('pools.dhcpOptions')}</label>
                      <textarea className="input" rows={2} value={sn.option_data} placeholder={t('pools.dhcpOptionsPlaceholder')}
                        onChange={(e) => updateSubnet(i, 'option_data', e.target.value)}
                        style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 11 }} />
                    </div>
                  </div>
                </div>
              ))}

              <button className="btn btn-sm" onClick={addSubnetRow}
                style={{ width: '100%', justifyContent: 'center', padding: '8px 0', borderStyle: 'dashed' }}>
                <Plus size={14} /> {t('pools.addSubnet')}
              </button>
            </fieldset>

            {/* Buttons */}
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button className="btn" onClick={() => { setShowAddModal(false); resetForm(); }}>
                {t('common.cancel')}
              </button>
              <button className="btn btn-primary" onClick={handleAdd} disabled={!addName.trim()}>
                {t('common.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
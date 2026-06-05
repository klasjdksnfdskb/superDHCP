import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { poolsAPI, tagsAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import PoolGauge from '@/components/PoolGauge';
import { Plus, Trash2, Edit2, Network, X, Globe, AlertCircle } from 'lucide-react';

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
  v6_mode: string;
  delegation_prefix: string;
  enable_reservation_v4: boolean;
  reservation_start_v4: string;
  reservation_end_v4: string;
  enable_reservation_v6: boolean;
  reservation_start_v6: string;
  reservation_end_v6: string;
  excludes: Array<{ start: string; end: string; reason: string }>;
}

const emptySubnet = (v: number): SubnetDraft => ({
  subnet: '',
  netmask: v === 4 ? '24' : '64',
  gateway: '',
  dns_servers: '',
  range_start: '',
  range_end: '',
  ip_version: v,
  lease_time: '86400',
  option_data: '',
  v6_mode: 'stateful',
  delegation_prefix: '',
  enable_reservation_v4: false,
  reservation_start_v4: '',
  reservation_end_v4: '',
  enable_reservation_v6: false,
  reservation_start_v6: '',
  reservation_end_v6: '',
  excludes: [],
});

export default function PoolManagement() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [pools, setPools] = useState<Pool[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingTags, setLoadingTags] = useState(false);
  const [tagsError, setTagsError] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  // Pool form state
  const [addName, setAddName] = useState('');
  const [addDesc, setAddDesc] = useState('');
  const [addVlans, setAddVlans] = useState('');
  const [addTagId, setAddTagId] = useState('');
  const [addNtp, setAddNtp] = useState('');
  const [addBootfile, setAddBootfile] = useState('');
  const [addNextServer, setAddNextServer] = useState('');
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
    setLoadingTags(true);
    setTagsError(false);
    try {
      const { data } = await tagsAPI.list();
      setTags(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load tags:', err);
      setTagsError(true);
      setTags([]);
    } finally {
      setLoadingTags(false);
    }
  };

  useEffect(() => { fetchPools(); fetchTags(); }, []);

  const resetForm = () => {
    setAddName('');
    setAddDesc('');
    setAddVlans('');
    setAddTagId('');
    setAddNtp('');
    setAddBootfile('');
    setAddNextServer('');
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
        ntp_servers: addNtp ? addNtp.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        bootfile: addBootfile || undefined,
        next_server: addNextServer || undefined,
        subnets: subnets
          .filter((sn) => sn.subnet.trim())
          .map((sn) => ({
            subnet: sn.subnet.trim(),
            netmask: sn.netmask.trim(),
            gateway: sn.gateway.trim() || undefined,
            dns_servers: sn.dns_servers.trim()
              ? sn.dns_servers.split(',').map((s) => s.trim())
              : undefined,
            range_start: sn.range_start.trim() || undefined,
            range_end: sn.range_end.trim() || undefined,
            ip_version: sn.ip_version,
            lease_time: sn.lease_time ? parseInt(sn.lease_time, 10) : undefined,
            option_data: sn.option_data.trim() ? JSON.parse(sn.option_data) : undefined,
            v6_mode: sn.ip_version === 6 ? sn.v6_mode : undefined,
            delegation_prefix: sn.ip_version === 6 ? sn.delegation_prefix || undefined : undefined,
            enable_reservation: sn.ip_version === 4 ? sn.enable_reservation_v4 : sn.enable_reservation_v6,
            reservation_start: sn.ip_version === 4
              ? (sn.reservation_start_v4.trim() || undefined)
              : (sn.reservation_start_v6.trim() || undefined),
            reservation_end: sn.ip_version === 4
              ? (sn.reservation_end_v4.trim() || undefined)
              : (sn.reservation_end_v6.trim() || undefined),
            excludes: sn.excludes.length > 0
              ? sn.excludes.filter((ex) => ex.start.trim() && ex.end.trim())
                .map((ex) => ({ exclude_start: ex.start.trim(), exclude_end: ex.end.trim(), reason: ex.reason || undefined }))
              : undefined,
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
  const updateSubnet = (i: number, key: keyof SubnetDraft, val: string | number | boolean) => {
    setSubnets(subnets.map((sn, idx) => idx === i ? { ...sn, [key]: val } : sn));
  };

  const openAddModal = async () => {
    resetForm();
    await fetchTags();
    setShowAddModal(true);
  };

  const switchIpVersion = (i: number, version: number) => {
    setSubnets(subnets.map((sn, idx) =>
      idx === i ? { ...emptySubnet(version), subnet: sn.subnet, netmask: sn.netmask } : sn
    ));
  };

  // ── Exclude helpers ──
  const addExcludeRow = (si: number) => {
    setSubnets(subnets.map((sn, idx) =>
      idx === si ? { ...sn, excludes: [...sn.excludes, { start: '', end: '', reason: '' }] } : sn
    ));
  };
  const removeExcludeRow = (si: number, ei: number) => {
    setSubnets(subnets.map((sn, idx) =>
      idx === si ? { ...sn, excludes: sn.excludes.filter((_, j) => j !== ei) } : sn
    ));
  };
  const updateExclude = (si: number, ei: number, key: string, val: string) => {
    setSubnets(subnets.map((sn, idx) =>
      idx === si ? {
        ...sn, excludes: sn.excludes.map((ex, j) => j === ei ? { ...ex, [key]: val } : ex)
      } : sn
    ));
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
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 720, maxHeight: '85vh', overflow: 'auto' }}>
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
                {loadingTags ? (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 0' }}>
                    {t('common.loading')}
                  </div>
                ) : tagsError ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#ef4444', fontSize: 12, padding: '8px 0' }}>
                    <AlertCircle size={14} /> {t('pools.noTagsLoaded')}
                    <button className="btn btn-sm" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11 }}
                      onClick={() => fetchTags()}>{t('common.retry')}</button>
                  </div>
                ) : (
                  <select className="input" value={addTagId} onChange={(e) => setAddTagId(e.target.value)}
                    style={{ appearance: 'auto' }}>
                    <option value="">{t('pools.noOrgTag')}</option>
                    {tags.length === 0 ? (
                      <option value="" disabled>{t('pools.noOrgTags')}</option>
                    ) : (
                      tags.map((tag) => (
                        <option key={tag.id} value={tag.id}>
                          {'\u00A0\u00A0'.repeat(tag.level)}{tag.name}
                        </option>
                      ))
                    )}
                  </select>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">{t('pools.bindVlan')}</label>
                <input className="input" value={addVlans} onChange={(e) => setAddVlans(e.target.value)}
                  placeholder={t('pools.vlanPlaceholder')} />
              </div>

              {/* NTP / PXE 配置 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div className="form-group">
                  <label className="form-label">{t('pools.ntpServers')}</label>
                  <input className="input" value={addNtp} onChange={(e) => setAddNtp(e.target.value)}
                    placeholder={t('pools.ntpPlaceholder')} />
                </div>
                <div className="form-group">
                  <label className="form-label">{t('pools.nextServer')}</label>
                  <input className="input" value={addNextServer} onChange={(e) => setAddNextServer(e.target.value)}
                    placeholder={t('pools.nextServerPlaceholder')} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">{t('pools.bootfile')}</label>
                <input className="input" value={addBootfile} onChange={(e) => setAddBootfile(e.target.value)}
                  placeholder={t('pools.bootfilePlaceholder')} />
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
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', gap: 0 }}>
                      <button
                        className={sn.ip_version === 4 ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                        style={{ borderRadius: '4px 0 0 4px', padding: '4px 14px' }}
                        onClick={() => switchIpVersion(i, 4)}>IPv4</button>
                      <button
                        className={sn.ip_version === 6 ? 'btn btn-sm btn-primary' : 'btn btn-sm'}
                        style={{ borderRadius: '0 4px 4px 0', padding: '4px 14px' }}
                        onClick={() => switchIpVersion(i, 6)}>IPv6</button>
                    </div>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
                      {sn.ip_version === 4 ? t('pools.ipv4Config') : t('pools.ipv6Config')} #{i + 1}
                    </span>
                    {subnets.length > 1 && (
                      <button className="btn btn-sm btn-danger" style={{ marginLeft: 'auto', padding: '2px 8px' }}
                        onClick={() => removeSubnetRow(i)} title={t('pools.removeSubnet')}>
                        <X size={12} />
                      </button>
                    )}
                  </div>

                  {/* ── IPv4 Fields ── */}
                  {sn.ip_version === 4 && (
                    <>
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

                      {/* IPv4 Reservation checkbox */}
                      <div className="form-group" style={{ marginTop: 4 }}>
                        <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12 }}>
                          <input type="checkbox" checked={sn.enable_reservation_v4}
                            onChange={(e) => updateSubnet(i, 'enable_reservation_v4', e.target.checked)}
                            style={{ width: 16, height: 16 }} />
                          {t('pools.enableReservationV4')}
                          <span style={{ color: 'var(--text-muted)', fontSize: 11, fontWeight: 400 }}>
                            — {t('pools.reservationHint')}
                          </span>
                        </label>
                      </div>
                      {sn.enable_reservation_v4 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 8 }}>
                          <div className="form-group">
                            <label className="form-label">{t('pools.reservationStart')}</label>
                            <input className="input" value={sn.reservation_start_v4}
                              placeholder="10.0.0.1"
                              onChange={(e) => updateSubnet(i, 'reservation_start_v4', e.target.value)} />
                          </div>
                          <div className="form-group">
                            <label className="form-label">{t('pools.reservationEnd')}</label>
                            <input className="input" value={sn.reservation_end_v4}
                              placeholder="10.0.0.50"
                              onChange={(e) => updateSubnet(i, 'reservation_end_v4', e.target.value)} />
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* ── IPv6 Fields ── */}
                  {sn.ip_version === 6 && (
                    <>
                      {/* Row: subnet + prefix length */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div className="form-group">
                          <label className="form-label">{t('pools.subnet')}</label>
                          <input className="input" value={sn.subnet} placeholder="2001:db8::"
                            onChange={(e) => updateSubnet(i, 'subnet', e.target.value)} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">{t('pools.prefixLength')}</label>
                          <input className="input" value={sn.netmask} placeholder={t('pools.prefixLengthPlaceholder')}
                            onChange={(e) => updateSubnet(i, 'netmask', e.target.value)} />
                        </div>
                      </div>

                      {/* Row: gateway + DNS */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div className="form-group">
                          <label className="form-label">{t('pools.gateway')}</label>
                          <input className="input" value={sn.gateway} placeholder="2001:db8::1"
                            onChange={(e) => updateSubnet(i, 'gateway', e.target.value)} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">{t('pools.dnsServers')}</label>
                          <input className="input" value={sn.dns_servers} placeholder="2001:4860:4860::8888"
                            onChange={(e) => updateSubnet(i, 'dns_servers', e.target.value)} />
                        </div>
                      </div>

                      {/* IPv6 Mode radio group */}
                      <div className="form-group">
                        <label className="form-label">{t('pools.v6Mode')}</label>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                          {(['stateful', 'stateless', 'pd'] as const).map((mode) => (
                            <label key={mode} style={{
                              display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                              padding: '6px 10px', borderRadius: 6, fontSize: 12,
                              background: sn.v6_mode === mode ? 'var(--accent-glow)' : 'transparent',
                              border: `1px solid ${sn.v6_mode === mode ? 'var(--accent)' : 'var(--border)'}`,
                            }}>
                              <input type="radio" name={`v6mode-${i}`} value={mode}
                                checked={sn.v6_mode === mode}
                                onChange={() => updateSubnet(i, 'v6_mode', mode)}
                                style={{ width: 14, height: 14 }} />
                              {mode === 'stateful' ? t('pools.v6Stateful') : mode === 'stateless' ? t('pools.v6Stateless') : t('pools.v6PD')}
                            </label>
                          ))}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                          {t('pools.v6ModeHint')}
                        </div>
                      </div>

                      {/* PD prefix delegation (conditional) */}
                      {sn.v6_mode === 'pd' && (
                        <div className="form-group">
                          <label className="form-label">{t('pools.v6PDPrefix')}</label>
                          <input className="input" value={sn.delegation_prefix}
                            placeholder={t('pools.v6PDPrefixPlaceholder')}
                            onChange={(e) => updateSubnet(i, 'delegation_prefix', e.target.value)} />
                        </div>
                      )}

                      {/* Range (optional for stateless) */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div className="form-group">
                          <label className="form-label">
                            {t('pools.rangeStart')}
                            {sn.v6_mode === 'stateless' ? '' : ' *'}
                          </label>
                          <input className="input" value={sn.range_start}
                            placeholder={sn.v6_mode === 'stateless' ? '(SLAAC auto)' : '2001:db8::10'}
                            onChange={(e) => updateSubnet(i, 'range_start', e.target.value)} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">{t('pools.rangeEnd')}</label>
                          <input className="input" value={sn.range_end}
                            placeholder={sn.v6_mode === 'stateless' ? '(SLAAC auto)' : '2001:db8::ff'}
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

                      {/* IPv6 Reservation checkbox */}
                      <div className="form-group" style={{ marginTop: 4 }}>
                        <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12 }}>
                          <input type="checkbox" checked={sn.enable_reservation_v6}
                            onChange={(e) => updateSubnet(i, 'enable_reservation_v6', e.target.checked)}
                            style={{ width: 16, height: 16 }} />
                          {t('pools.enableReservationV6')}
                          <span style={{ color: 'var(--text-muted)', fontSize: 11, fontWeight: 400 }}>
                            — {t('pools.reservationHint')}
                          </span>
                        </label>
                      </div>
                      {sn.enable_reservation_v6 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 8 }}>
                          <div className="form-group">
                            <label className="form-label">{t('pools.reservationStart')}</label>
                            <input className="input" value={sn.reservation_start_v6}
                              placeholder="2001:db8::1"
                              onChange={(e) => updateSubnet(i, 'reservation_start_v6', e.target.value)} />
                          </div>
                          <div className="form-group">
                            <label className="form-label">{t('pools.reservationEnd')}</label>
                            <input className="input" value={sn.reservation_end_v6}
                              placeholder="2001:db8::50"
                              onChange={(e) => updateSubnet(i, 'reservation_end_v6', e.target.value)} />
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {/* ── Exclude Ranges (shared for v4/v6) ── */}
                  <div style={{
                    borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 10,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>
                        {t('pools.excludeRanges')}
                      </span>
                      <button className="btn btn-sm" style={{ padding: '2px 8px', fontSize: 11 }}
                        onClick={() => addExcludeRow(i)}>
                        <Plus size={12} /> {t('pools.addExclude')}
                      </button>
                    </div>
                    {sn.excludes.length === 0 ? (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 4 }}>
                        {t('pools.noExcludes')}
                      </div>
                    ) : (
                      sn.excludes.map((ex, ei) => (
                        <div key={ei} style={{
                          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8,
                          alignItems: 'end', marginBottom: 8,
                        }}>
                          <div className="form-group" style={{ margin: 0 }}>
                            <label className="form-label" style={{ fontSize: 10 }}>{t('pools.excludeStart')}</label>
                            <input className="input" value={ex.start}
                              placeholder="10.0.0.100" style={{ fontSize: 11, padding: '4px 6px' }}
                              onChange={(e) => updateExclude(i, ei, 'start', e.target.value)} />
                          </div>
                          <div className="form-group" style={{ margin: 0 }}>
                            <label className="form-label" style={{ fontSize: 10 }}>{t('pools.excludeEnd')}</label>
                            <input className="input" value={ex.end}
                              placeholder="10.0.0.109" style={{ fontSize: 11, padding: '4px 6px' }}
                              onChange={(e) => updateExclude(i, ei, 'end', e.target.value)} />
                          </div>
                          <div className="form-group" style={{ margin: 0 }}>
                            <label className="form-label" style={{ fontSize: 10 }}>{t('pools.excludeReason')}</label>
                            <input className="input" value={ex.reason}
                              placeholder={t('pools.excludeReasonPlaceholder')}
                              style={{ fontSize: 11, padding: '4px 6px' }}
                              onChange={(e) => updateExclude(i, ei, 'reason', e.target.value)} />
                          </div>
                          <button className="btn btn-sm btn-danger"
                            style={{ padding: '4px 8px', fontSize: 11 }}
                            onClick={() => removeExcludeRow(i, ei)}
                            title={t('common.delete')}>
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))
                    )}
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

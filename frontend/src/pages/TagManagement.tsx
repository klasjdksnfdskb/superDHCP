import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { tagsAPI } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import TagTree from '@/components/TagTree';

interface TagNode {
  id: string;
  name: string;
  slug: string;
  level: number;
  full_path: string;
  color?: string;
  children: TagNode[];
}

export default function TagManagement() {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [tree, setTree] = useState<TagNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [parentId, setParentId] = useState('');
  const [tagName, setTagName] = useState('');
  const [tagSlug, setTagSlug] = useState('');
  const [tagDesc, setTagDesc] = useState('');
  const [tagColor, setTagColor] = useState('#3b82f6');

  const fetchTree = async () => {
    try {
      const { data } = await tagsAPI.tree();
      setTree(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTree(); }, []);

  const openAdd = (pid: string) => {
    setEditId(null);
    setParentId(pid);
    setTagName('');
    setTagSlug('');
    setTagDesc('');
    setTagColor('#3b82f6');
    setShowModal(true);
  };

  const openEdit = (id: string) => {
    const find = (nodes: TagNode[]): TagNode | undefined => {
      for (const n of nodes) {
        if (n.id === id) return n;
        const r = find(n.children);
        if (r) return r;
      }
      return undefined;
    };
    const node = find(tree);
    if (node) {
      setEditId(node.id);
      setParentId('');
      setTagName(node.name);
      setTagSlug(node.slug);
      setTagDesc('');
      setTagColor(node.color || '#3b82f6');
      setShowModal(true);
    }
  };

  const handleSave = async () => {
    if (!tagName.trim() || !tagSlug.trim()) return;
    try {
      if (editId) {
        await tagsAPI.update(editId, { name: tagName, slug: tagSlug, description: tagDesc, color: tagColor });
      } else {
        await tagsAPI.create({
          name: tagName,
          slug: tagSlug,
          parent_id: parentId || null,
          description: tagDesc,
          color: tagColor,
        });
      }
      setShowModal(false);
      fetchTree();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('tags.deleteConfirm'))) return;
    try {
      await tagsAPI.delete(id);
      fetchTree();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="empty">{t('common.loading')}</div>;

  return (
    <div>
      <div className="topbar">
        <div className="topbar-title">{t('tags.title')}</div>
        <div className="topbar-actions">
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {t('tags.subtitle')}
          </span>
        </div>
      </div>

      <div className="page-content">
        <div className="card">
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            {t('tags.description')}
          </div>
          <TagTree
            nodes={tree}
            onAdd={openAdd}
            onEdit={openEdit}
            onDelete={handleDelete}
            isAdmin={isAdmin}
          />
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{editId ? t('tags.editTag') : t('tags.createTag')}</h2>
            <div className="form-group">
              <label className="form-label">{t('tags.tagName')}</label>
              <input className="input" value={tagName} onChange={(e) => setTagName(e.target.value)} placeholder={t('tags.tagNamePlaceholder')} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('tags.slug')}</label>
              <input className="input" value={tagSlug} onChange={(e) => setTagSlug(e.target.value)} placeholder={t('tags.slugPlaceholder')} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('pools.description')}</label>
              <input className="input" value={tagDesc} onChange={(e) => setTagDesc(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">{t('tags.tagColor')}</label>
              <input className="input" type="color" value={tagColor} onChange={(e) => setTagColor(e.target.value)} style={{ width: 60, height: 36 }} />
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
              <button className="btn" onClick={() => setShowModal(false)}>{t('common.cancel')}</button>
              <button className="btn btn-primary" onClick={handleSave}>{editId ? t('common.save') : t('common.create')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
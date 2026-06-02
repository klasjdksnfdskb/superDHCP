import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, ChevronDown, Folder, FolderOpen, Plus, Trash2, Edit2 } from 'lucide-react';

interface TagNode {
  id: string;
  name: string;
  slug: string;
  level: number;
  full_path: string;
  color?: string;
  children: TagNode[];
}

interface TagTreeProps {
  nodes: TagNode[];
  onAdd?: (parentId: string) => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  isAdmin?: boolean;
}

function TreeNode({ node, onAdd, onEdit, onDelete, isAdmin, depth = 0 }: {
  node: TagNode;
  onAdd?: (parentId: string) => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  isAdmin?: boolean;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="tag-tree">
      <div className="tag-node" style={{ paddingLeft: depth * 24 }}>
        <span onClick={() => hasChildren && setExpanded(!expanded)} style={{ cursor: hasChildren ? 'pointer' : 'default', display: 'flex', alignItems: 'center' }}>
          {hasChildren ? (
            expanded ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />
          ) : (
            <span style={{ width: 16 }} />
          )}
          {expanded && hasChildren ? (
            <FolderOpen size={16} color={node.color || 'var(--accent)'} style={{ marginLeft: 4 }} />
          ) : (
            <Folder size={16} color={node.color || 'var(--text-muted)'} style={{ marginLeft: 4 }} />
          )}
        </span>
        <div className="tag-dot" style={{ background: node.color || 'var(--accent)' }} />
        <span className="tag-name">{node.name}</span>
        <span className="tag-path">{node.full_path}</span>
        {isAdmin && (
          <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
            <button className="btn btn-sm" onClick={() => onAdd?.(node.id)} title="添加子标签">
              <Plus size={12} />
            </button>
            <button className="btn btn-sm" onClick={() => onEdit?.(node.id)} title="编辑">
              <Edit2 size={12} />
            </button>
            <button className="btn btn-sm btn-danger" onClick={() => onDelete?.(node.id)} title="删除">
              <Trash2 size={12} />
            </button>
          </div>
        )}
      </div>
      {expanded && hasChildren && (
        <div className="tag-children">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              onAdd={onAdd}
              onEdit={onEdit}
              onDelete={onDelete}
              isAdmin={isAdmin}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TagTree({ nodes, onAdd, onEdit, onDelete, isAdmin }: TagTreeProps) {
  const { t } = useTranslation();

  if (nodes.length === 0) {
    return (
      <div className="empty">
        {t('tags.noTags')}
        {isAdmin && (
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={() => onAdd?.('')}>{t('tags.createRoot')}</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {isAdmin && (
        <div style={{ marginBottom: 12 }}>
          <button className="btn btn-primary btn-sm" onClick={() => onAdd?.('')}>
            <Plus size={14} /> {t('tags.createRoot')}
          </button>
        </div>
      )}
      {nodes.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          onAdd={onAdd}
          onEdit={onEdit}
          onDelete={onDelete}
          isAdmin={isAdmin}
          depth={0}
        />
      ))}
    </div>
  );
}
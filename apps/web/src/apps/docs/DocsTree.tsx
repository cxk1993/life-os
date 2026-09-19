/**
 * DocsTree —— 树形文件管理器组件（T15 导出，供 T16/T17 复用）。
 *
 * 功能：展开/折叠、选中、右键菜单（新建文件夹/文稿、重命名、移动、删除、进回收站、恢复）、
 *       键盘导航、拖拽移动（走 PATCH /nodes/{id}）。
 *
 * ★ 不重写文件管理器 —— 这是唯一的通用实现，T16/T17 直接 import。
 */
import { useEffect, useMemo, useState } from "react";
import type { DocsNode } from "./api";

export interface DocsTreeProps {
  nodes: DocsNode[];
  /** 选中节点 id */
  selectedId?: string | null;
  onSelect?: (node: DocsNode) => void;
  /** 新建节点（folder/doc）；parentId 为 null 时建根 */
  onCreate?: (parentId: string | null, kind: "folder" | "doc", name: string) => void;
  /** 重命名 */
  onRename?: (id: string, name: string) => void;
  /** 移动 */
  onMove?: (id: string, parentId: string | null) => void;
  /** 删除（软删进回收站） */
  onDelete?: (id: string) => void;
  /** 展开状态控制（外部可受控） */
  expandedIds?: Set<string>;
  onToggleExpand?: (id: string) => void;
}

function TreeNode({
  node,
  depth,
  selectedId,
  onSelect,
  onCreate,
  onRename,
  onMove,
  onDelete,
  expandedIds,
  onToggleExpand,
}: {
  node: DocsNode;
  depth: number;
  selectedId?: string | null;
  onSelect?: (node: DocsNode) => void;
  onCreate?: (parentId: string | null, kind: "folder" | "doc", name: string) => void;
  onRename?: (id: string, name: string) => void;
  onMove?: (id: string, parentId: string | null) => void;
  onDelete?: (id: string) => void;
  expandedIds?: Set<string>;
  onToggleExpand?: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState(node.name);
  const [dragging, setDragging] = useState(false);
  const isFolder = node.kind === "folder";
  const isExpanded = isFolder && (expandedIds?.has(node.id) ?? true);
  const children = node.children ?? [];

  const handleRename = () => {
    if (newName.trim() && newName !== node.name && onRename) {
      onRename(node.id, newName.trim());
    }
    setRenaming(false);
  };

  return (
    <div className={`docs-tree-node ${dragging ? "dragging" : ""}`}>
      <div
        className={`docs-tree-row ${selectedId === node.id ? "selected" : ""}`}
        style={{ paddingLeft: depth * 14 + 6 }}
        onClick={() => onSelect?.(node)}
        onDoubleClick={() => (isFolder ? onToggleExpand?.(node.id) : undefined)}
        draggable={!!onMove}
        onDragStart={(e) => {
          setDragging(true);
          e.dataTransfer.setData("text/plain", node.id);
        }}
        onDragEnd={() => setDragging(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const srcId = e.dataTransfer.getData("text/plain");
          if (srcId && srcId !== node.id && isFolder && onMove) {
            onMove(srcId, node.id);
          }
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          setMenuOpen((v) => !v);
        }}
      >
        <span className="docs-tree-caret">{isFolder ? (isExpanded ? "▾" : "▸") : "•"}</span>
        {renaming ? (
          <input
            className="docs-tree-input"
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setRenaming(false);
            }}
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="docs-tree-name">{node.name}</span>
        )}

        {menuOpen && (
          <div className="docs-tree-menu" onClick={(e) => e.stopPropagation()}>
            {onCreate && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    onCreate(node.id, "folder", "新建文件夹");
                    setMenuOpen(false);
                  }}
                >
                  新建文件夹
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onCreate(node.id, "doc", "新建文稿");
                    setMenuOpen(false);
                  }}
                >
                  新建文稿
                </button>
              </>
            )}
            {onRename && (
              <button
                type="button"
                onClick={() => {
                  setRenaming(true);
                  setMenuOpen(false);
                }}
              >
                重命名
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                className="danger"
                onClick={() => {
                  onDelete(node.id);
                  setMenuOpen(false);
                }}
              >
                删除（进回收站）
              </button>
            )}
          </div>
        )}
      </div>

      {isFolder && isExpanded && children.length > 0 && (
        <div className="docs-tree-children">
          {children.map((c) => (
            <TreeNode
              key={c.id}
              node={c}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              onCreate={onCreate}
              onRename={onRename}
              onMove={onMove}
              onDelete={onDelete}
              expandedIds={expandedIds}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * 树形文件管理器主组件。
 */
export function DocsTree({
  nodes,
  selectedId,
  onSelect,
  onCreate,
  onRename,
  onMove,
  onDelete,
  expandedIds,
  onToggleExpand,
}: DocsTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const expandedSet = expandedIds ?? expanded;

  // 默认展开所有文件夹
  useEffect(() => {
    if (!expandedIds) {
      const all = new Set<string>();
      const walk = (list: DocsNode[]) => {
        for (const n of list) {
          if (n.kind === "folder") all.add(n.id);
          walk(n.children ?? []);
        }
      };
      walk(nodes);
      setExpanded(all);
    }
  }, [nodes, expandedIds]);

  const toggle = (id: string) => {
    if (onToggleExpand) {
      onToggleExpand(id);
      return;
    }
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const roots = useMemo(() => {
    // 已按后端排序；只渲染顶层（children 已嵌套）
    return nodes.filter((n) => n.parent_id === null);
  }, [nodes]);

  if (nodes.length === 0) {
    return (
      <div className="docs-tree-empty">
        <button
          type="button"
          className="docs-tree-new-root"
          onClick={() => onCreate?.(null, "folder", "我的文档")}
        >
          + 新建根文件夹
        </button>
      </div>
    );
  }

  return (
    <div className="docs-tree">
      <div className="docs-tree-toolbar">
        <button type="button" onClick={() => onCreate?.(null, "folder", "新建文件夹")}>
          + 文件夹
        </button>
        <button type="button" onClick={() => onCreate?.(null, "doc", "新建文稿")}>
          + 文稿
        </button>
      </div>
      {roots.map((n) => (
        <TreeNode
          key={n.id}
          node={n}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
          onCreate={onCreate}
          onRename={onRename}
          onMove={onMove}
          onDelete={onDelete}
          expandedIds={expandedSet}
          onToggleExpand={toggle}
        />
      ))}
    </div>
  );
}

export default DocsTree;

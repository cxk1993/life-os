/**
 * DocsViewer —— txt/md 查看与编辑组件（T15 导出，供 T16/T17 复用）。
 *
 * - txt/md 查看与修改；编辑用原生 <textarea>（10 万字也不卡）。
 * - md 下提供「源码 / 渲染」切换（复用 MarkdownView 的懒加载渲染器）。
 * - 保存回调由父组件接（T15 的 DocsApp 调 PATCH /nodes/{id}/content）。
 */
import { useEffect, useState } from "react";
import MarkdownView from "./MarkdownView";

export interface DocsViewerProps {
  name: string;
  format: string;
  body: string;
  /** 是否正在编辑（默认 true；只读场景传 false） */
  editable?: boolean;
  onSave?: (format: string, body: string) => void;
  onBack?: () => void;
}

export function DocsViewer({
  name,
  format,
  body,
  editable = true,
  onSave,
  onBack,
}: DocsViewerProps) {
  const [text, setText] = useState(body);
  const [fmt, setFmt] = useState(format === "txt" ? "txt" : "md");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setText(body);
    setFmt(format === "txt" ? "txt" : "md");
    setDirty(false);
  }, [body, format]);

  const save = () => {
    if (!onSave) return;
    onSave(fmt, text);
    setDirty(false);
  };

  return (
    <div className="docs-viewer">
      <div className="docs-viewer-header">
        {onBack && (
          <button type="button" className="docs-viewer-back" onClick={onBack}>
            ←
          </button>
        )}
        <span className="docs-viewer-name">{name}</span>
        <div className="docs-viewer-actions">
          <select
            className="docs-viewer-format"
            value={fmt}
            onChange={(e) => {
              setFmt(e.target.value);
              setDirty(true);
            }}
            disabled={!editable}
          >
            <option value="md">md</option>
            <option value="txt">txt</option>
          </select>
          {editable && (
            <button type="button" className="docs-viewer-save" disabled={!dirty} onClick={save}>
              保存
            </button>
          )}
        </div>
      </div>

      {fmt === "md" ? (
        <MarkdownView content={text} defaultMode={editable ? "source" : "render"} />
      ) : (
        <textarea
          className="docs-viewer-textarea"
          value={text}
          readOnly={!editable}
          onChange={(e) => {
            setText(e.target.value);
            setDirty(true);
          }}
          placeholder={editable ? "开始书写…" : ""}
        />
      )}
    </div>
  );
}

export default DocsViewer;

/**
 * MultitabFrame · V6「一窗多页」容器原语（豆包预研 §2 形态的视图侧落地）。
 *
 * 需求来源：主人 ⑫（能力目录/mcp/推送/鉴权一窗标签分组）与 ⑧⑪（习惯/人格/健康
 * 并入成长罗盘多页）。一个原语三处复用：系统窗页组 / 成长罗盘 / 复盘笔记文档三合一。
 *
 * 行为契约（判据见 MultitabFrame.test.tsx，对应豆包预研 §3.3 四条）：
 * - 页签条水平展示全部一级页签；当前页高亮；
 * - 懒挂载：页面内容只在**首次被选中时**挂载（mountedKeys 集合）；
 * - keep-alive：已挂载的页切走不销毁（hidden 保挂载），切回状态不丢；
 * - 键盘可达：页签为 tab/button，aria-selected 标注当前页（对齐 U1-5 a11y 口径）。
 *
 * 本组件是纯视图原语：不读 manifest、不接路由、零契约面——
 * manifest `tabs` 声明（知默 schema 侧）定稿后由调用方把 entry 映射进 content 即可。
 */
import { useCallback, useState } from "react";
import type { ReactNode } from "react";

export interface MultitabPage {
  key: string;
  label: string;
  content: ReactNode;
}

interface Props {
  pages: MultitabPage[];
  /** 初始选中的页 key（默认取第一页）。 */
  initialKey?: string;
  ariaLabel?: string;
}

export default function MultitabFrame({ pages, initialKey, ariaLabel }: Props) {
  const [activeKey, setActiveKey] = useState(
    () => initialKey ?? pages[0]?.key ?? "",
  );
  // 懒挂载 + keep-alive：只有被选中过的页才挂载，挂载后永不移除。
  const [mountedKeys, setMountedKeys] = useState<Set<string>>(
    () => new Set([initialKey ?? pages[0]?.key ?? ""]),
  );

  const select = useCallback(
    (key: string) => {
      setActiveKey(key);
      setMountedKeys((prev) => {
        if (prev.has(key)) return prev;
        const next = new Set(prev);
        next.add(key);
        return next;
      });
    },
    [],
  );

  if (pages.length === 0) return null;

  return (
    <div className="mtab" data-testid="multitab-frame">
      <div className="mtab__tabbar" role="tablist" aria-label={ariaLabel}>
        {pages.map((page) => {
          const active = page.key === activeKey;
          return (
            <button
              key={page.key}
              type="button"
              role="tab"
              aria-selected={active}
              data-testid={`mtab-tab-${page.key}`}
              className={`mtab__tab${active ? " mtab__tab--active" : ""}`}
              onClick={() => select(page.key)}
            >
              {page.label}
            </button>
          );
        })}
      </div>
      <div className="mtab__body">
        {pages.map((page) =>
          mountedKeys.has(page.key) ? (
            <div
              key={page.key}
              role="tabpanel"
              data-testid={`mtab-panel-${page.key}`}
              hidden={page.key !== activeKey}
              className="mtab__panel"
            >
              {page.content}
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
}

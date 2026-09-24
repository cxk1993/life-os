import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/shared/api/client";

/**
 * C′ 里程碑侧栏卡（令54 #6「landmark 第二例」的今天就可见版本，astrbot 提议）。
 *
 * 宿主：成长罗盘窗侧栏（`window.sidecar` 扩展点，attachTo: "dashboard"）。
 * 数据：消费 astrbot 的 `/api/v1/countdown/landmarks?window=365`（服务端已算完日期，
 *       days_until 升序、排除 archived、anniversary 自动滚下一次——前端零日期运算）。
 *
 * 降级三态：
 *  - 加载中  → 不渲染（避免侧栏闪烁空卡）
 *  - 404     → countdown 未安装 → 返回 null（侧栏无贡献，WindowFrame 不显示侧栏）
 *  - 空列表  → 显示「暂无里程碑」空态（与 E5 首例 todo sidecar 同铁律）
 */

export interface Landmark {
  id?: string;
  title: string;
  kind: string;
  on_date?: string;
  days_until: number;
  note?: string;
}

const KIND_LABEL: Record<string, string> = {
  anniversary: "纪念日",
  countdown: "倒计时",
};

export default function LandmarksSidecar() {
  const { data } = useQuery({
    queryKey: ["countdown", "landmarks"],
    queryFn: async (): Promise<Landmark[] | null> => {
      try {
        return await api.get<Landmark[]>("/api/v1/countdown/landmarks?window=365");
      } catch (e) {
        // countdown 未安装 → 端点 404 → 无里程碑卡（侧栏不出现，不算错误）
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    retry: 1,
  });

  // 加载中或 countdown 未安装：都不渲染（避免闪烁 / 幽灵卡）
  if (data === undefined || data === null) return null;

  if (data.length === 0) {
    return (
      <div className="sidecar-card" data-testid="landmarks-sidecar">
        <div className="sidecar-card__title">里程碑</div>
        <div className="sidecar-card__empty">暂无里程碑</div>
      </div>
    );
  }

  return (
    <div className="sidecar-card" data-testid="landmarks-sidecar">
      <div className="sidecar-card__title">里程碑</div>
      <ul className="sidecar-card__list">
        {data.map((lm, i) => (
          <li key={lm.id ?? i} className="sidecar-card__item">
            <span className="sidecar-card__num">{lm.days_until}</span>
            <span className="sidecar-card__lbl"> 天后 · {lm.title}</span>
            <span className="sidecar-card__tag">{KIND_LABEL[lm.kind] ?? lm.kind}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

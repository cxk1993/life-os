/** settings.page 插槽贡献：设置页里的推送分页（复用主界面的完整能力）。 */
import PushApp from "../PushApp";

export default function SettingsPage() {
  return (
    <div className="push-settings">
      <p className="push-meta">
        浏览器 / PWA 推送通道（桌面 Toast 走桥，见日历提醒链路）。配置与订阅管理如下：
      </p>
      <PushApp />
    </div>
  );
}

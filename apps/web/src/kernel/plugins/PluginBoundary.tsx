import { Component, type ReactNode } from "react";

/**
 * 插件级错误边界：某个插件的贡献组件在渲染时抛错，只影响它自己那一小块，
 * 桌面/其它插件照常工作，绝不白屏（与内核 ModuleErrorBoundary 同思路）。
 */
interface PluginBoundaryProps {
  pluginId: string;
  children: ReactNode;
}

interface PluginBoundaryState {
  error?: Error;
}

export class PluginBoundary extends Component<PluginBoundaryProps, PluginBoundaryState> {
  state: PluginBoundaryState = {};

  static getDerivedStateFromError(error: Error): PluginBoundaryState {
    return { error };
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="plugin__error" role="alert">
          <span className="plugin__error-title">插件「{this.props.pluginId}」渲染失败</span>
          <span className="plugin__error-detail">{this.state.error.message}</span>
        </div>
      );
    }
    return this.props.children;
  }
}

/**
 * 待办插件入口（T14 加载器按 manifest.entry = "@apps/todo" 加载）。
 */
import type { ComponentType } from "react";
import TodoApp from "./TodoApp";
import DashboardCard from "./slots/DashboardCard";
import "./todo.css";

const PluginModule = {
  manifestId: "todo",
  Component: TodoApp as ComponentType,
  slots: {
    "dashboard.card": DashboardCard as ComponentType,
  },
};

export default PluginModule;
export { TodoApp, DashboardCard };

/**
 * 课程表插件入口（T14 加载器按 manifest.entry = "@/apps/course" 加载）。
 *
 * ★ 挂载点：schedule 容器的第 4 页（[日程表][待办][学业][课程表]）。
 *   Dock 显隐唯一杠杆 = DOCK_MERGE（kernel/Dock.tsx），已登记 course → schedule，
 *   因此本模块**不会**在底端栏单独出一个按钮。
 */
import type { ComponentType } from "react";
import CourseApp from "./CourseApp";
import "./course.css";

const PluginModule = {
  manifestId: "course",
  Component: CourseApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { CourseApp };

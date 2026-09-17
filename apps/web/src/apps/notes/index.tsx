/**
 * 笔记插件入口（T14 加载器按 manifest.entry = "@apps/notes" 加载）。
 */
import type { ComponentType } from "react";
import NotesApp from "./NotesApp";
import "./notes.css";

const PluginModule = {
  manifestId: "notes",
  Component: NotesApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { NotesApp };

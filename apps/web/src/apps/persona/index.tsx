/**
 * 人格体系插件入口（T14 加载器按 manifest.entry = "@apps/persona" 加载）。
 */
import type { ComponentType } from "react";
import PersonaApp from "./PersonaApp";
import "./persona.css";

const PluginModule = {
  manifestId: "persona",
  Component: PersonaApp as ComponentType,
  slots: {},
};

export default PluginModule;
export { PersonaApp };

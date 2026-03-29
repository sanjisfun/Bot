/// <reference types="vite/client" />

/**
 * Автоматический JSX (`jsx: "react-jsx"`) импортирует `react/jsx-runtime`.
 * Полные типы — из пакета `react` после `npm install`.
 */
declare module "react/jsx-runtime" {
  export function jsx(type: unknown, props: unknown, key?: unknown): unknown;
  export function jsxs(type: unknown, props: unknown, key?: unknown): unknown;
  export const Fragment: unknown;
}

/** Типы из `react-dom` после `npm install` */
declare module "react-dom/client" {
  export interface Root {
    render(node: unknown): void;
    unmount(): void;
  }
  export function createRoot(container: Element | DocumentFragment): Root;
}

/** Минимально для `react` / `React.FC`; полные типы — пакет `react` */
declare module "react" {
  export type FC<P = Record<string, unknown>> = (props: P) => unknown;
  export const StrictMode: (props: { children?: unknown }) => unknown;
}

/**
 * Минимальные типы entry `vite`, если пакет не установлен или TS не резолвит `exports`.
 * Полные типы идут из `node_modules/vite` после `npm install`.
 */
declare module "vite" {
  export function defineConfig(config: UserConfigExport): UserConfigExport;
  export type UserConfigExport = UserConfig | Promise<UserConfig> | (() => UserConfig) | (() => Promise<UserConfig>);
  export interface UserConfig {
    plugins?: PluginOption[];
    resolve?: { alias?: Record<string, string> };
    [key: string]: unknown;
  }
  export type PluginOption =
    | Plugin
    | Plugin[]
    | Promise<Plugin | Plugin[] | null | undefined>
    | null
    | undefined;
  export interface Plugin {
    name?: string;
    [key: string]: unknown;
  }
}

/** Типы, если TS не подхватывает package exports / нет node_modules */
declare module "@tailwindcss/vite" {
  export default function tailwindcss(): import("vite").PluginOption;
}

declare module "@vitejs/plugin-react" {
  export default function react(options?: Record<string, unknown>): import("vite").PluginOption;
}

declare module "vite-plugin-singlefile" {
  export function viteSingleFile(): import("vite").PluginOption;
}

/** Встроенные модули Node (`path`, `url`); полный набор — пакет `@types/node` */
declare module "path" {
  const path: {
    resolve(...paths: string[]): string;
    dirname(p: string): string;
  };
  export default path;
}

declare module "url" {
  export function fileURLToPath(url: string | URL): string;
}

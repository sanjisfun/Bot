/**
 * Типы для https://telegram.org/js/telegram-web-app.js
 * @see https://core.telegram.org/bots/webapps
 */
export {};

declare global {
  interface TelegramThemeParams {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
    header_bg_color?: string;
    accent_text_color?: string;
    section_bg_color?: string;
    section_header_text_color?: string;
    subtitle_text_color?: string;
    destructive_text_color?: string;
  }

  interface TelegramWebApp {
    ready: () => void;
    expand: () => void;
    close: () => void;
    disableVerticalSwipes?: () => void;
    enableVerticalSwipes?: () => void;
    setHeaderColor: (color: string) => void;
    setBackgroundColor: (color: string) => void;
    colorScheme: "light" | "dark";
    themeParams: TelegramThemeParams;
    isExpanded?: boolean;
    onEvent?: (event: "themeChanged" | "viewportChanged" | string, handler: () => void) => void;
    offEvent?: (event: "themeChanged" | "viewportChanged" | string, handler: () => void) => void;
  }

  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

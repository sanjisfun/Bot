import { useEffect, useState } from "react";

function isTelegramApp(): boolean {
  return typeof window !== "undefined" && Boolean(window.Telegram?.WebApp);
}

/**
 * Инициализация Telegram Mini App: тема шапки/фона, разворот на весь экран, отключение вертикальных свайпов.
 */
export function useTelegramWebApp() {
  const [isTelegram] = useState(isTelegramApp);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    tg.ready();
    tg.expand();
    tg.disableVerticalSwipes?.();

    const applyTheme = () => {
      const { themeParams } = tg;
      const bg = themeParams.bg_color;
      const header = themeParams.header_bg_color ?? bg;
      if (bg) tg.setBackgroundColor(bg);
      if (header) tg.setHeaderColor(header);
    };

    applyTheme();
    if (typeof tg.onEvent === "function") {
      tg.onEvent("themeChanged", applyTheme);
      return () => tg.offEvent?.("themeChanged", applyTheme);
    }
  }, []);

  return { isTelegram };
}

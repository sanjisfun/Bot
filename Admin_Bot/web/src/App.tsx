import * as React from "react";
import { useTelegramWebApp } from "./hooks/useTelegramWebApp";
import { cn } from "./utils/cn";

const ShieldIcon: React.FC = () => (
  <svg
    className="h-8 w-8 text-white"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

export default function App() {
  const { isTelegram } = useTelegramWebApp();

  return (
    <div
      className={cn(
        "flex min-h-[100dvh] flex-col items-center justify-center p-6",
        "bg-[var(--tg-theme-bg-color,#f8fafc)]",
        "text-[var(--tg-theme-text-color,#0f172a)]",
        !isTelegram && "bg-gradient-to-br from-slate-50 via-white to-zinc-100 text-slate-900"
      )}
    >
      <div className="max-w-md space-y-6 text-center">
        <div
          className={cn(
            "inline-flex h-16 w-16 items-center justify-center rounded-2xl shadow-lg",
            "bg-gradient-to-br from-violet-500 to-indigo-600 shadow-indigo-200/60",
            isTelegram && "shadow-[var(--tg-theme-button-color,#6366f1)]/25"
          )}
        >
          <ShieldIcon />
        </div>
        <div className="space-y-3">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Admin Guard</h1>
          <p
            className={cn(
              "text-pretty text-[15px] leading-relaxed",
              isTelegram
                ? "text-[var(--tg-theme-hint-color,#64748b)]"
                : "text-slate-600 dark:text-slate-300"
            )}
          >
            {isTelegram
              ? "Панель открыта в Telegram. Здесь позже можно подключить API бота для настроек чатов."
              : "Откройте панель из бота (кнопка Mini App), чтобы получить контекст Telegram и тему оформления."}
          </p>
        </div>
      </div>
    </div>
  );
}

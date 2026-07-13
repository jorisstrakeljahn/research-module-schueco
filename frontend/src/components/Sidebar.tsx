"use client";

import {
  ChevronLeft,
  ChevronRight,
  GitCompareArrows,
  LayoutDashboard,
  Radar,
  Rss,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import LanguageSwitch from "@/components/LanguageSwitch";
import ThemeSwitch from "@/components/ThemeSwitch";
import { useI18n } from "@/lib/i18n";
import { setSidebarCollapsed, useSidebarCollapsed } from "@/lib/sidebar";

const NAV = [
  { href: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/newsfeed", labelKey: "nav.newsfeed", icon: Rss },
  { href: "/radar", labelKey: "nav.radar", icon: Radar },
  { href: "/runs", labelKey: "nav.runs", icon: GitCompareArrows },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const collapsed = useSidebarCollapsed();

  return (
    <aside
      className={`flex h-screen shrink-0 flex-col border-r border-border bg-bg transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      <div
        className={`flex h-14 shrink-0 items-center border-b border-border ${
          collapsed ? "justify-center px-2" : "justify-between px-4"
        }`}
      >
        {!collapsed && (
          <Link href="/" className="truncate text-sm font-semibold tracking-tight text-fg">
            Schüco <span className="text-primary">Trendradar</span>
          </Link>
        )}
        <button
          type="button"
          onClick={() => setSidebarCollapsed(!collapsed)}
          title={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          aria-label={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-faint transition-colors hover:bg-hover hover:text-fg"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className={`flex-1 py-3 ${collapsed ? "px-2" : "px-3"}`}>
        <ul className="space-y-1">
          {NAV.map(({ href, labelKey, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  title={collapsed ? t(labelKey) : undefined}
                  className={`flex items-center gap-2.5 rounded-md text-sm transition-colors ${
                    collapsed ? "justify-center p-2.5" : "px-3 py-2"
                  } ${
                    active
                      ? "bg-primary/12 font-medium text-primary"
                      : "text-muted hover:bg-hover hover:text-fg"
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {!collapsed && <span className="truncate">{t(labelKey)}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {!collapsed && (
        <div className="space-y-2.5 border-t border-border px-3 py-3">
          <ThemeSwitch />
          <LanguageSwitch />
        </div>
      )}
    </aside>
  );
}

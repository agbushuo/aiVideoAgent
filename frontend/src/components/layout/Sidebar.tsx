"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SlidersHorizontal, Settings, ClipboardList } from "lucide-react";

const navIcons = [
  { icon: SlidersHorizontal, key: "presets", href: "/presets" },
  { icon: ClipboardList, key: "tasks", href: "/tasks" },
  { icon: Settings, key: "settings", href: "/settings" },
];

export default function Sidebar() {
  const t = useTranslations("sidebar");
  const pathname = usePathname();

  return (
    <aside className="w-52 border-r border-border bg-surface flex flex-col shrink-0">
      {/* Quick actions */}
      <div className="p-3">
        <Link
          href="/"
          className="flex items-center justify-center gap-2 w-full px-3 py-2 text-sm font-medium bg-brand-600 hover:bg-brand-500 rounded-md transition-colors"
        >
          {t("newTask")}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 space-y-0.5">
        {navIcons.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 text-sm rounded-md transition-colors ${
                isActive
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`}
            >
              <item.icon className="w-4 h-4" />
              {t(item.key)}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border text-[10px] text-zinc-600 text-center">
        VideoAgent v0.2.0
      </div>
    </aside>
  );
}

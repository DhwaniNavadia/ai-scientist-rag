"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  FlaskConical,
  GitCompare,
  Layers,
  Lightbulb,
  Menu,
  RefreshCw,
  Tag,
  Target,
  Upload,
  X,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/contexts/AppContext";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const { currentPaper, setCurrentPaper, papers, demoMode, toggleDemoMode } =
    useApp();

  const navItems = currentPaper
    ? [
        { href: `/${currentPaper}/sections`, label: "Sections", icon: BookOpen },
        { href: `/${currentPaper}/claims`, label: "Claims", icon: Tag },
        { href: `/${currentPaper}/gaps`, label: "Gaps", icon: Target },
        { href: `/${currentPaper}/hypotheses`, label: "Hypotheses", icon: Lightbulb },
        { href: `/${currentPaper}/debate`, label: "Debate", icon: GitCompare },
        { href: `/${currentPaper}/reflection`, label: "Reflection", icon: RefreshCw },
        { href: `/${currentPaper}/cross-paper`, label: "Cross-Paper", icon: Layers },
        { href: `/${currentPaper}/evaluation`, label: "Evaluation", icon: BarChart3 },
      ]
    : [];

  return (
    <>
      <header className="flex md:hidden items-center justify-between border-b border-border bg-card px-4 py-3">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-primary" />
          <span className="font-semibold text-sm">Research Pipeline</span>
          {demoMode && (
            <span className="ml-1 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-900/50 dark:text-amber-400">
              DEMO
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent"
            aria-label="Toggle navigation"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          {/* Drawer */}
          <div className="relative z-50 flex w-64 flex-col bg-card border-r border-border h-full pt-4">
            {/* Paper selector */}
            <div className="px-3 pb-3 border-b border-border">
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                Active Paper
              </label>
              <select
                value={currentPaper ?? ""}
                onChange={(e) => {
                  setCurrentPaper(e.target.value || null);
                  setMobileOpen(false);
                }}
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground"
              >
                <option value="">— select paper —</option>
                {papers.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
              <MobileNavLink
                href="/"
                label="Dashboard"
                icon={Upload}
                active={pathname === "/"}
                onClick={() => setMobileOpen(false)}
              />
              {navItems.map((item) => (
                <MobileNavLink
                  key={item.href}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  active={pathname === item.href}
                  onClick={() => setMobileOpen(false)}
                />
              ))}
            </nav>

            <div className="border-t border-border px-3 py-3">
              <button
                onClick={() => {
                  toggleDemoMode();
                  setMobileOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  demoMode
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
                    : "text-muted-foreground hover:bg-accent"
                )}
              >
                <Zap className="h-4 w-4" />
                {demoMode ? "Demo Mode ON" : "Enable Demo Mode"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function MobileNavLink({
  href,
  label,
  icon: Icon,
  active,
  onClick,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

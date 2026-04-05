"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  FlaskConical,
  GitCompare,
  Layers,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  Tag,
  Target,
  Upload,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/contexts/AppContext";
import { ThemeToggle } from "./ThemeToggle";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
}

function buildNavItems(paper: string): NavItem[] {
  return [
    { href: `/${paper}/sections`, label: "Sections", icon: BookOpen },
    { href: `/${paper}/claims`, label: "Claims", icon: Tag },
    { href: `/${paper}/gaps`, label: "Gaps", icon: Target },
    { href: `/${paper}/hypotheses`, label: "Hypotheses", icon: Lightbulb },
    { href: `/${paper}/debate`, label: "Debate", icon: GitCompare },
    { href: `/${paper}/reflection`, label: "Reflection", icon: RefreshCw },
    { href: `/${paper}/cross-paper`, label: "Cross-Paper", icon: Layers },
    { href: `/${paper}/evaluation`, label: "Evaluation", icon: BarChart3 },
  ];
}

export function Sidebar() {
  const pathname = usePathname();
  const { currentPaper, setCurrentPaper, papers, demoMode, toggleDemoMode } = useApp();

  const navItems = currentPaper ? buildNavItems(currentPaper) : [];

  return (
    <aside className="hidden md:flex md:w-60 flex-col bg-card border-r border-border">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-border">
        <FlaskConical className="h-5 w-5 text-primary" />
        <span className="font-semibold text-sm">Research Pipeline</span>
      </div>

      {/* Paper selector */}
      <div className="px-3 py-3 border-b border-border">
        <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
          Active Paper
        </label>
        <select
          value={currentPaper ?? ""}
          onChange={(e) => setCurrentPaper(e.target.value || null)}
          className={cn(
            "w-full rounded-md border border-input bg-background px-2 py-1.5",
            "text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          )}
        >
          <option value="">— select paper —</option>
          {papers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {/* Home / upload */}
        <NavLink href="/" label="Dashboard" icon={Upload} active={pathname === "/"} />

        {navItems.length > 0 && (
          <>
            <div className="pt-2 pb-1 px-2">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Analysis
              </span>
            </div>
            {navItems.map((item) => (
              <NavLink
                key={item.href}
                href={item.href}
                label={item.label}
                icon={item.icon}
                active={pathname === item.href}
              />
            ))}
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="border-t border-border px-3 py-3 space-y-2">
        {/* Demo mode toggle */}
        <button
          onClick={toggleDemoMode}
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
            demoMode
              ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          )}
        >
          <Zap className="h-4 w-4 flex-shrink-0" />
          <span className="truncate">{demoMode ? "Demo Mode ON" : "Enable Demo Mode"}</span>
        </button>
        {/* Theme Toggle */}
        <div className="flex items-center justify-between px-1">
          <span className="text-xs text-muted-foreground">Theme</span>
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ElementType;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      <Icon className="h-4 w-4 flex-shrink-0" />
      {label}
    </Link>
  );
}

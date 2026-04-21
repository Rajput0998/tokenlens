import { NavLink, Outlet } from "react-router-dom";
import { Home, BarChart3, Lightbulb, Settings, BookOpen } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { useTokenStore } from "@/stores/useTokenStore";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", icon: Home, label: "Live Overview" },
  { to: "/analytics", icon: BarChart3, label: "Analytics" },
  { to: "/insights", icon: Lightbulb, label: "Predictions" },
  { to: "/how-it-works", icon: BookOpen, label: "How It Works" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Layout() {
  const perTool = useTokenStore((s) => s.perTool);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r bg-[hsl(var(--sidebar-bg))] border-[hsl(var(--sidebar-border))]">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5">
          <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" stroke="url(#logo-g)" strokeWidth="2"/>
            <path d="M9 14l3 3 7-7" stroke="url(#logo-g)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <defs>
              <linearGradient id="logo-g" x1="0" y1="0" x2="28" y2="28">
                <stop stopColor="var(--teal)"/>
                <stop offset="1" stopColor="var(--blue)"/>
              </linearGradient>
            </defs>
          </svg>
          <span className="text-lg font-bold text-gradient">TokenLens</span>
        </div>

        {/* Section label */}
        <div className="px-5 pt-2 pb-2">
          <span className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">
            Monitor
          </span>
        </div>

        {/* Nav items */}
        <nav className="flex-1 space-y-0.5 px-3">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                  isActive
                    ? "bg-[var(--sidebar-active-bg)] text-[var(--teal)]"
                    : "text-muted-foreground hover:bg-[var(--sidebar-active-bg)] hover:text-foreground"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[var(--teal)]" />
                  )}
                  <Icon className="h-4 w-4" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Tool status */}
        <div className="border-t border-[hsl(var(--sidebar-border))] px-5 py-3 space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">
            Tools
          </p>
          {perTool.length === 0 ? (
            <p className="text-xs text-muted-foreground">No tools active</p>
          ) : (
            perTool.map((tool) => (
              <div key={tool.tool} className="flex items-center gap-2 text-xs">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    tool.active ? "bg-[var(--green)]" : "bg-muted-foreground/30"
                  )}
                />
                <span className="truncate capitalize">{tool.tool.replace("_", " ")}</span>
              </div>
            ))
          )}
        </div>

        {/* Bottom: monitoring status + theme */}
        <div className="border-t border-[hsl(var(--sidebar-border))] px-5 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--green)] animate-pulse" />
              <span className="text-[11px] text-[var(--green)] font-medium">Monitoring active</span>
            </div>
            <ThemeToggle />
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">v1.0.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}

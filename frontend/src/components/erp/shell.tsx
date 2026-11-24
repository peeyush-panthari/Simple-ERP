/**
 * App chrome: full-height sidebar nav (logo, permission-filtered grouped navigation,
 * and bottom user profile with help/notification icons) maximizing vertical screen
 * space across all ERP pages. Below lg, a compact mobile header and bottom tab bar
 * provide responsive access.
 */

import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { Bell, ChevronDown, LogOut, Menu, User, X } from "lucide-react";
import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { LoadingOverlay, Spinner, TopProgress } from "@/components/erp/ui";
import { GlobalHelpDrawer } from "@/components/erp/help-drawer";
import { useAuth } from "@/lib/auth";
import { groupedNav, mobileTabItems, resolveBreadcrumbs, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

interface SystemStatus {
  checks?: { database?: { healthy?: boolean } };
  modulesDone?: number;
  modulesTotal?: number;
}

function usePlatformStatus() {
  const { api, can } = useAuth();
  const enabled = can("analytics:read");
  const query = useQuery({ queryKey: ["system-status"], queryFn: () => api<SystemStatus>("GET", "/api/v1/system-status"), enabled, staleTime: 60_000, retry: false });
  return { enabled, ...query };
}

function NotificationBell({ degraded }: { degraded: boolean }) {
  const { can } = useAuth();
  const inner = (
    <>
      <Bell size={16} />
      {degraded && <span className="header-pill-badge" />}
    </>
  );
  return can("notification:read") ? (
    <Link to="/notifications" className="header-pill relative" title="Notifications">
      {inner}
    </Link>
  ) : (
    <span className="header-pill relative" title="Notifications">
      {inner}
    </span>
  );
}

/** The signed-in user's menu: Profile (MFA, password) and Logout. */
function ProfileMenu({ side = "top", align = "start" }: { side?: "top" | "bottom" | "left" | "right"; align?: "start" | "center" | "end" }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const name = user?.displayName ?? "";
  const initials = (name || "?").split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
  const roles = user?.roles.map((r) => r.name).join(", ") || "No role";

  const goProfile = () => {
    setOpen(false);
    navigate("/profile");
  };
  const signOut = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
      setOpen(false);
      navigate("/login");
    }
  };
  // Arrow keys move between the two items, like a native menu.
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const items = [...e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')];
    const i = items.indexOf(document.activeElement as HTMLButtonElement);
    items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length]?.focus();
    e.preventDefault();
  };

  return (
    <div className="flex items-center min-w-0">
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button
            type="button"
            className="profile-pill flex-1 min-w-0"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label={`Account menu, ${name}`}
            title="Account"
          >
            <span className="profile-pill-avatar shrink-0">{initials}</span>
            <div className="min-w-0 flex-1 text-left leading-tight">
              <p className="profile-pill-name truncate">{name}</p>
              <p className="profile-pill-role truncate">{roles}</p>
            </div>
            <ChevronDown size={14} className={cn("profile-pill-caret shrink-0 ml-1", open && "profile-pill-caret-open")} aria-hidden />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content side={side} align={align} sideOffset={8} className="profile-menu" role="menu" aria-label="Account menu" onKeyDown={onKeyDown}>
            <div className="profile-menu-head">
              <p className="profile-menu-name">{name}</p>
              <p className="profile-menu-email">{user?.email}</p>
            </div>
            <button type="button" role="menuitem" className="profile-menu-item" onClick={goProfile}>
              <User size={16} aria-hidden />
              <span>
                Profile
                <small>MFA &amp; password</small>
              </span>
            </button>
            <button type="button" role="menuitem" className="profile-menu-item" onClick={signOut} disabled={loggingOut}>
              {loggingOut ? <Spinner size={16} /> : <LogOut size={16} aria-hidden />}
              <span>{loggingOut ? "Logging out…" : "Logout"}</span>
            </button>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </div>
  );
}

function NavLinkItem({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const Icon = item.icon;
  return (
    <NavLink
      to={item.path}
      onClick={onNavigate}
      className={cn("nav-item flex items-center justify-between group", pathname === item.path && "nav-item-active")}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Icon size={16} className={cn("shrink-0", item.badge && "text-amber-500/80")} />
        <span className="truncate">{item.label}</span>
      </div>
      {item.badge && (
        <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded leading-none shrink-0 tracking-tight ml-1.5 bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
          {item.badge}
        </span>
      )}
    </NavLink>
  );
}

const STORAGE_KEY_NAV_COLLAPSED = "simple_erp_collapsed_nav_groups";

function NavGroupSection({
  group,
  items,
  isCollapsed,
  onToggle,
  onNavigate,
  hasActiveChild,
}: {
  group: string;
  items: NavItem[];
  isCollapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  hasActiveChild: boolean;
}) {
  return (
    <div className="nav-group mb-2">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "w-full flex items-center justify-between px-2 py-2 rounded-md text-xs font-semibold tracking-wider uppercase transition-colors select-none",
          "text-[var(--sidebar-foreground)]/85 hover:text-[var(--sidebar-foreground)] hover:bg-[var(--sidebar-accent)]/40 cursor-pointer",
          hasActiveChild && "text-teal-600 dark:text-teal-400 font-bold"
        )}
        aria-expanded={!isCollapsed}
        aria-label={`${group} section, ${isCollapsed ? "collapsed" : "expanded"}`}
      >
        <span className="flex items-center gap-2 truncate">
          {hasActiveChild && isCollapsed && (
            <span className="h-2 w-2 rounded-full bg-teal-500 shrink-0 shadow-xs" title="Active page inside" />
          )}
          <span className="truncate">{group}</span>
        </span>
        <ChevronDown
          size={14}
          className={cn(
            "shrink-0 transition-transform duration-200 opacity-60 ml-2",
            isCollapsed && "-rotate-90"
          )}
        />
      </button>

      {!isCollapsed && (
        <div className="mt-1 space-y-0.5 pl-0.5 animate-in fade-in duration-150">
          {items.map((item) => (
            <NavLinkItem key={item.path} item={item} onNavigate={onNavigate} />
          ))}
        </div>
      )}
    </div>
  );
}

function NavGroups({ onNavigate }: { onNavigate?: () => void }) {
  const { permissions, enabledModules } = useAuth();
  const { pathname } = useLocation();
  const groups = useMemo(() => groupedNav(permissions, enabledModules), [permissions, enabledModules]);

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY_NAV_COLLAPSED);
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  });

  const toggleGroup = (group: string) => {
    setCollapsed((prev) => {
      const current = prev[group] !== undefined ? prev[group] : true;
      const next = { ...prev, [group]: !current };
      try {
        localStorage.setItem(STORAGE_KEY_NAV_COLLAPSED, JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const allCollapsed = groups.length > 0 && groups.every((g) => (collapsed[g.group] !== undefined ? Boolean(collapsed[g.group]) : true));

  const toggleAll = () => {
    const nextState = !allCollapsed;
    const next: Record<string, boolean> = {};
    groups.forEach((g) => {
      next[g.group] = nextState;
    });
    setCollapsed(next);
    try {
      localStorage.setItem(STORAGE_KEY_NAV_COLLAPSED, JSON.stringify(next));
    } catch {}
  };

  return (
    <>
      <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-[var(--sidebar-border)]/40 text-[10px] text-[var(--sidebar-foreground)]/50">
        <span className="font-semibold tracking-wider uppercase text-[9px]">Modules</span>
        <button
          type="button"
          onClick={toggleAll}
          className="hover:text-[var(--sidebar-foreground)] transition-colors hover:underline cursor-pointer"
        >
          {allCollapsed ? "Expand all" : "Collapse all"}
        </button>
      </div>
      {groups.map((g) => {
        const hasActiveChild = g.items.some((item) => item.path === pathname);
        const isCollapsed = collapsed[g.group] !== undefined ? Boolean(collapsed[g.group]) : true;
        return (
          <NavGroupSection
            key={g.group}
            group={g.group}
            items={g.items}
            isCollapsed={isCollapsed}
            onToggle={() => toggleGroup(g.group)}
            onNavigate={onNavigate}
            hasActiveChild={hasActiveChild}
          />
        );
      })}
    </>
  );
}

function BottomTabBar() {
  const { permissions, enabledModules } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  return (
    <nav className="mobile-tabbar">
      {mobileTabItems(permissions, enabledModules).map((item) => {
        const Icon = item.icon;
        return (
          <NavLink key={item.path} to={item.path} className={cn("mobile-tab-item", pathname === item.path && "mobile-tab-item-active")}>
            <Icon size={18} />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
      {/* The bar only has room for four modules - "More" opens the same grouped nav as a full-screen drawer. */}
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Trigger className="mobile-tab-item" type="button">
          <Menu size={18} />
          <span>More</span>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content mobile-nav-drawer" aria-describedby={undefined}>
            <div className="mobile-nav-drawer-header">
              <Dialog.Title className="mobile-nav-drawer-title">Menu</Dialog.Title>
              <Dialog.Close className="mobile-nav-drawer-close" type="button" aria-label="Close menu">
                <X size={18} />
              </Dialog.Close>
            </div>
            <nav className="mobile-nav-drawer-nav">
              <NavGroups onNavigate={() => setOpen(false)} />
            </nav>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </nav>
  );
}

function BreadcrumbTrail() {
  const { pathname } = useLocation();
  const crumbs = useMemo(() => resolveBreadcrumbs(pathname), [pathname]);

  if (crumbs.length === 0) return null;

  return (
    <nav className="breadcrumb-trail" aria-label="breadcrumb">
      <ol>
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;
          return (
            <li key={idx}>
              {crumb.to && !isLast ? (
                <Link to={crumb.to} className="breadcrumb-link">
                  {crumb.label}
                </Link>
              ) : (
                <span className={cn(isLast ? "breadcrumb-current" : "text-[var(--muted-foreground)]")}>
                  {crumb.label}
                </span>
              )}
              {!isLast && <span className="breadcrumb-separator" aria-hidden="true">/</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function Shell({ children, fullWidth = false }: { children: ReactNode; fullWidth?: boolean }) {
  const status = usePlatformStatus();
  const degraded = status.enabled && !status.isPending && !status.isError && !status.data?.checks?.database?.healthy;
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <TopProgress />
      <LoadingOverlay />

      {/* Left Navigation Bar */}
      <aside className="app-sidebar">
        {/* Simple ERP Name and Logo */}
        <div className="flex h-14 shrink-0 items-center px-4 border-b border-[var(--sidebar-border)]">
          <Link to="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity" title="Simple ERP — home">
            <Logo markClass="h-7 w-auto" textClass="app-header-logo-text" subClass="app-header-logo-sub" />
          </Link>
        </div>

        {/* Navigation items */}
        <nav className="app-sidebar-nav flex-1 overflow-y-auto">
          <NavGroups />
        </nav>

        {/* User Account section at bottom with ? and notification icons */}
        <div className="border-t border-[var(--sidebar-border)] p-3 shrink-0 flex flex-col gap-2 bg-[var(--sidebar)]">
          <div className="flex items-center justify-between gap-1.5">
            <div className="min-w-0 flex-1">
              <ProfileMenu side="top" align="start" />
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <GlobalHelpDrawer />
              <NotificationBell degraded={degraded} />
            </div>
          </div>
          {status.enabled && (
            <div className="px-1 text-[10px] text-[var(--sidebar-foreground)]/60 flex items-center justify-between">
              <span className="flex items-center">
                <span className={cn("sidebar-footer-dot inline-block h-1.5 w-1.5 rounded-full mr-1.5", status.data?.checks?.database?.healthy ? "bg-[var(--success)]" : "bg-[var(--warning)]")} />
                {status.data?.modulesDone ?? 0}/{status.data?.modulesTotal ?? 0} modules
              </span>
              <span className="text-[9px] font-mono opacity-60">Simple ERP</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex min-w-0 min-h-0 flex-1 flex-col">
        <main tabIndex={0} id="main-content" aria-label="Main content" className="main-content main-content-mobile-pad focus:outline-none">
          <div className={cn("main-content-inner", fullWidth && "main-content-inner-wide")}>
            <BreadcrumbTrail />
            {children}
          </div>
        </main>
      </div>

      <BottomTabBar />
    </div>
  );
}

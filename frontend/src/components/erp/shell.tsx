/**
 * App chrome: sticky header (logo, global search, notification bell, account
 * menu with Profile and Logout) + permission-filtered, grouped sidebar nav with a live
 * platform-status footer, and below lg a bottom tab bar whose "More" tab opens
 * the full nav as a drawer. Port of the Reflex app's components/shell.py.
 */

import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { Bell, ChevronDown, LogOut, Menu, Search, User, X } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/erp/logo";
import { LoadingOverlay, Spinner, TopProgress } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { groupedNav, mobileTabItems, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

/** Routes a typed identifier to the module page whose prefix it matches (e.g. "PO-3005" -> /procurement). */
const SEARCH_ROUTES: [RegExp, string][] = [
  [/^po-/i, "/procurement"],
  [/^so-/i, "/orders"],
  [/^grn-/i, "/warehouse"],
  [/^(inv|ap|ar)-/i, "/finance"],
  [/^(lr|rfq|dsp)-/i, "/logistics"],
  [/^pty-/i, "/parties"],
];

function GlobalSearch() {
  const [value, setValue] = useState("");
  const navigate = useNavigate();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    const target = SEARCH_ROUTES.find(([re]) => re.test(q))?.[1] ?? "/products";
    setValue("");
    navigate(`${target}?q=${encodeURIComponent(q)}`);
  };
  return (
    <form onSubmit={submit} className="global-search hidden md:flex">
      <Search size={16} className="shrink-0 text-[var(--sidebar-foreground)]/60" />
      <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Search POs, SKUs, parties…" />
      <kbd>⏎</kbd>
    </form>
  );
}

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
function ProfileMenu() {
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
    <div className="ml-auto flex items-center gap-2">
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button type="button" className="profile-pill" aria-haspopup="menu" aria-expanded={open} aria-label={`Account menu, ${name}`} title="Account">
            <span className="profile-pill-avatar">{initials}</span>
            <div className="hidden text-left leading-tight sm:block">
              <p className="profile-pill-name">{name}</p>
              <p className="profile-pill-role">{roles}</p>
            </div>
            <ChevronDown size={14} className={cn("profile-pill-caret", open && "profile-pill-caret-open")} aria-hidden />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content align="end" sideOffset={8} className="profile-menu" role="menu" aria-label="Account menu" onKeyDown={onKeyDown}>
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

function Header({ degraded }: { degraded: boolean }) {
  return (
    <header className="app-header">
      <Link to="/" className="shrink-0 hover:opacity-90" title="Simple ERP — home">
        <Logo markClass="h-7 w-auto" textClass="app-header-logo-text" subClass="app-header-logo-sub" />
      </Link>
      <div className="app-header-divider hidden md:block" />
      <GlobalSearch />
      <NotificationBell degraded={degraded} />
      <ProfileMenu />
    </header>
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
        <span
          className={cn(
            "text-[9px] font-semibold px-1.5 py-0.5 rounded leading-none shrink-0 tracking-tight ml-1.5",
            item.roadmapStage === "medium_term"
              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
              : "bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"
          )}
        >
          {item.badge}
        </span>
      )}
    </NavLink>
  );
}

function NavGroups({ onNavigate }: { onNavigate?: () => void }) {
  const { permissions } = useAuth();
  return (
    <>
      {groupedNav(permissions).map((g) => (
        <div key={g.group} className="nav-group">
          <p className="nav-group-label">{g.group}</p>
          {g.items.map((item) => (
            <NavLinkItem key={item.path} item={item} onNavigate={onNavigate} />
          ))}
        </div>
      ))}
    </>
  );
}

function SidebarFooter({ status }: { status: ReturnType<typeof usePlatformStatus> }) {
  if (!status.enabled) {
    return (
      <div className="sidebar-footer">
        <p>Simple ERP</p>
      </div>
    );
  }
  return (
    <div className="sidebar-footer">
      {status.isPending ? (
        <p className="numeric">checking platform…</p>
      ) : status.isError ? (
        <p className="numeric text-[var(--destructive)]">platform unreachable</p>
      ) : (
        <p className="numeric flex items-center">
          <span className={cn("sidebar-footer-dot", status.data?.checks?.database?.healthy ? "bg-[var(--success)]" : "bg-[var(--warning)]")} />
          {status.data?.modulesDone ?? 0}/{status.data?.modulesTotal ?? 0} modules done
        </p>
      )}
    </div>
  );
}

function BottomTabBar() {
  const { permissions } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  return (
    <nav className="mobile-tabbar">
      {mobileTabItems(permissions).map((item) => {
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

export function Shell({ children, fullWidth = false }: { children: ReactNode; fullWidth?: boolean }) {
  const status = usePlatformStatus();
  const degraded = status.enabled && !status.isPending && !status.isError && !status.data?.checks?.database?.healthy;
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopProgress />
      <LoadingOverlay />
      <Header degraded={degraded} />
      <div className="flex min-w-0 min-h-0 flex-1">
        <aside className="app-sidebar">
          <nav className="app-sidebar-nav">
            <NavGroups />
          </nav>
          <SidebarFooter status={status} />
        </aside>
        <div className="flex min-w-0 min-h-0 flex-1 flex-col">
          <main className="main-content main-content-mobile-pad">
            <div className={cn("main-content-inner", fullWidth && "main-content-inner-wide")}>{children}</div>
          </main>
        </div>
      </div>
      <BottomTabBar />
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3, Box, CalendarDays, FileCheck2, Gauge, Hammer,
  LayoutDashboard, MessageSquare, UserCheck, X, Menu, LogOut,
} from "lucide-react";
import { clearSession, getUser } from "../lib/api";
import ThemeToggle from "./ThemeToggle";

const NAV = {
  estimator: [
    { href: "/review", label: "Requests", icon: MessageSquare },
    { href: "/resources", label: "Resources & Timeline", icon: CalendarDays },
    { href: "/board", label: "Board (view)", icon: Box },
  ],
  engineer: [
    { href: "/my-assignments", label: "My Assignments", icon: Hammer },
    { href: "/board", label: "Projects", icon: Box },
    { href: "/timeline", label: "Timeline (view)", icon: CalendarDays },
  ],
  manager: [
    { href: "/summary", label: "Overview", icon: LayoutDashboard },
    { href: "/review", label: "Requests", icon: MessageSquare },
    { href: "/approvals", label: "Approvals & Release", icon: FileCheck2 },
    { href: "/assign", label: "Assign Engineers", icon: UserCheck },
    { href: "/board", label: "Projects", icon: Box },
    { href: "/timeline", label: "Timeline", icon: CalendarDays },
  ],
  viewer: [
    { href: "/board", label: "Projects (view)", icon: Box },
    { href: "/timeline", label: "Timeline (view)", icon: CalendarDays },
  ],
};

const CLIENT_NAV = [{ href: "/my", label: "My Projects", icon: Box }];

export default function AppShell({ active, title, subtitle, children }) {
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUser(getUser());
    setReady(true);
  }, []);
  if (!ready) return null;          // SSR-safe: render only after mount
  if (!user) {
    if (typeof window !== "undefined") window.location.href = "/login";
    return null;
  }

  const items = user.role === "client" ? CLIENT_NAV : (NAV[user.role] || []);

  const initials = (user.full_name || user.email)
    .split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-sidebar transition-transform lg:static lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-20 items-center gap-3 border-b border-border px-6">
          <Link href="/" className="flex items-center gap-3">
            <img src="/ousus-logo.png" alt="Ousus" className="h-10 w-auto" />
          </Link>
          <button aria-label="Close menu" onClick={() => setMobileOpen(false)} className="ml-auto lg:hidden"><X className="size-4" /></button>
        </div>
        <div className="flex flex-1 flex-col gap-8 px-3 py-6">
          <nav className="flex flex-col gap-1">
            <p className="px-3 pb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Workspace</p>
            {items.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href}
                    className={`flex items-center gap-3 px-3 py-2.5 font-mono text-xs transition-colors ${active === label ? "bg-primary text-primary-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent"}`}>
                <Icon className="size-4" /><span>{label}</span>
              </Link>
            ))}
          </nav>
          {user.role === "client" && (
            <nav className="flex flex-col gap-1">
              <p className="px-3 pb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Services</p>
              <Link href="/request" className="flex items-center gap-3 px-3 py-2.5 font-mono text-xs text-sidebar-foreground hover:bg-sidebar-accent">
                <MessageSquare className="size-4" />New request
              </Link>
            </nav>
          )}
        </div>
        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 px-3 py-3">
            <div className="grid size-7 place-items-center bg-chart-2 font-mono text-xs font-bold text-primary-foreground">{initials}</div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-xs text-sidebar-foreground">{user.full_name}</p>
              <p className="font-mono text-[10px] text-muted-foreground">{user.role}</p>
            </div>
            <button aria-label="Logout" onClick={() => { clearSession(); router.push("/login"); }}>
              <LogOut className="size-4 text-muted-foreground hover:text-foreground" />
            </button>
          </div>
        </div>
      </aside>

      {/* main */}
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-border bg-background/95 px-5 backdrop-blur sm:px-8">
          <div className="flex items-center gap-3">
            <button aria-label="Open menu" onClick={() => setMobileOpen(true)} className="lg:hidden"><Menu className="size-5" /></button>
            <div className="hidden items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground sm:flex">
              <span>Ousus</span><span>/</span><span className="text-foreground">{active}</span>
            </div>
            <div className="font-mono text-xs font-bold sm:hidden">OUSUS / {active}</div>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <div className="hidden items-center gap-2 border-l border-border pl-4 sm:flex">
              <div className="grid size-7 place-items-center bg-chart-2 font-mono text-[10px] font-bold text-primary-foreground">{initials}</div>
            </div>
          </div>
        </header>
        <main className="mx-auto flex max-w-[1440px] flex-col gap-8 p-5 sm:p-8">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2"><span className="size-2 bg-primary" />
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">{active}</p></div>
            <h1 className="font-mono text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{title}</h1>
            {subtitle && <p className="font-mono text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

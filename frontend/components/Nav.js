"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getUser, clearSession } from "../lib/api";

const STAFF_LINKS = [
  { href: "/board", label: "Board", roles: ["engineer", "manager", "viewer"] },
  { href: "/estimate", label: "Estimate", roles: ["engineer", "manager"] },
  { href: "/approvals", label: "Approvals", roles: ["manager"] },
  { href: "/summary", label: "Daily Summary", roles: ["engineer", "manager"] },
];

export default function Nav() {
  const [user, setUser] = useState(null);
  const path = usePathname();
  const router = useRouter();

  useEffect(() => setUser(getUser()), []);

  if (path === "/login" || !user) return null;

  const links = user.role === "client"
    ? [{ href: "/my", label: "My Projects" }]
    : STAFF_LINKS.filter((l) => l.roles.includes(user.role));

  return (
    <nav className="nav">
      <span className="brand">Ousus</span>
      {links.map((l) => (
        <Link key={l.href} href={l.href}
              className={`link ${path === l.href ? "active" : ""}`}>
          {l.label}
        </Link>
      ))}
      <span className="spacer" />
      <span className="badge">{user.role}</span>
      <button className="btn secondary" onClick={() => {
        clearSession();
        router.push("/login");
      }}>Logout</button>
    </nav>
  );
}

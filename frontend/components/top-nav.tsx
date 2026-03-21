"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/planner", label: "Route Planner" },
  { href: "/insights", label: "Insights" },
  { href: "/developer", label: "Developer" },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <header className="top-nav-shell">
      <div className="top-nav container">
        <Link href="/" className="brand-mark" aria-label="RouteWise UK home">
          <span className="brand-kicker">RouteWise</span>
          <span className="brand-main">UK</span>
        </Link>

        <nav className="nav-links" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${active ? "is-active" : ""}`.trim()}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

import type { Metadata } from "next";

import { TopNav } from "../components/top-nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "RouteWise UK",
  description:
    "Plan safer UK journeys with risk scoring powered by STATS19 collision history and MIDAS weather context.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="site-bg" aria-hidden />
        <TopNav />
        <main className="container page-shell">{children}</main>
      </body>
    </html>
  );
}

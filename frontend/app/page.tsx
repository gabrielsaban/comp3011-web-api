import Link from "next/link";

import { API_BASE_URL } from "@/lib/api";
import { HealthPill } from "@/components/health-pill";

const SERVICE_STEPS = [
  {
    title: "Route Risk Scoring",
    detail:
      "Submit route waypoints and get segment-by-segment risk labels informed by accident density, severity, and weather-linked factors.",
  },
  {
    title: "Hotspot Intelligence",
    detail:
      "Query local hotspot cells around a candidate route area before departure to detect concentrated collision history.",
  },
  {
    title: "Operational Insights",
    detail:
      "Use trends and weather-correlation slices to guide fleet policy, schedule decisions, and route planning defaults.",
  },
];

export default function HomePage(): JSX.Element {
  return (
    <section className="reveal" style={{ animationDelay: "0.08s" }}>
      <div className="surface" style={{ padding: "1.4rem" }}>
        <span className="kicker">Road Risk Platform</span>
        <h1 className="headline">RouteWise UK helps teams choose safer road journeys.</h1>
        <p className="subhead">
          Built on UK STATS19 and MIDAS weather data, this interface turns your API into a
          practical planning tool for route selection, risk explanation, and pre-journey
          checks.
        </p>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.8rem",
            marginTop: "1rem",
            flexWrap: "wrap",
          }}
        >
          <HealthPill />
          <span className="mono" style={{ fontSize: "0.82rem", color: "var(--ink-700)" }}>
            API base: {API_BASE_URL}
          </span>
        </div>

        <div style={{ display: "flex", gap: "0.7rem", marginTop: "1.2rem", flexWrap: "wrap" }}>
          <Link href="/planner" className="btn-primary" style={{ display: "inline-block" }}>
            Open Route Planner
          </Link>
          <Link href="/insights" className="btn-secondary" style={{ display: "inline-block" }}>
            View Insights
          </Link>
        </div>
      </div>

      <div className="grid-3" style={{ marginTop: "1rem" }}>
        {SERVICE_STEPS.map((item, index) => (
          <article
            key={item.title}
            className="surface reveal"
            style={{ padding: "1rem", animationDelay: `${0.15 + index * 0.08}s` }}
          >
            <h2 style={{ margin: 0, fontSize: "1.08rem" }}>{item.title}</h2>
            <p style={{ marginBottom: 0, color: "var(--ink-700)", lineHeight: 1.55 }}>
              {item.detail}
            </p>
          </article>
        ))}
      </div>

      <div className="surface" style={{ padding: "1rem", marginTop: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>How the service is used</h3>
        <div className="grid-2">
          <div>
            <p style={{ marginTop: 0, color: "var(--ink-700)", lineHeight: 1.6 }}>
              RouteWise UK is designed for drivers, fleet planners, and operational analysts who
              need fast route-level risk context rather than raw endpoint payloads.
            </p>
            <p style={{ marginBottom: 0, color: "var(--ink-700)", lineHeight: 1.6 }}>
              Start with the planner to score a candidate journey, then move to insights for
              policy-level trend analysis by region and weather conditions.
            </p>
          </div>

          <div className="info-strip">
            <strong>Deployment note:</strong> frontend runs on Vercel and talks to your Railway
            API. If the API badge above is red, check CORS and frontend environment variables.
          </div>
        </div>
      </div>
    </section>
  );
}

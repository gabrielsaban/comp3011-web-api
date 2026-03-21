"use client";

import { FormEvent, useMemo, useState } from "react";

import { API_BASE_URL, callApiPath } from "@/lib/api";

const PRESET_PATHS = [
  "/health",
  "/api/v1/regions",
  "/api/v1/analytics/route-risk/scoring-model",
  "/api/v1/analytics/annual-trend?year_from=2019&year_to=2023",
  "/api/v1/analytics/weather-correlation?metric=precipitation",
  "/api/v1/analytics/hotspots?lat=51.5074&lng=-0.1278&radius_km=10",
];

export default function DeveloperPage(): JSX.Element {
  const [path, setPath] = useState(PRESET_PATHS[0]);
  const [response, setResponse] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const targetUrl = useMemo(() => {
    if (!path) {
      return API_BASE_URL;
    }
    return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  }, [path]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setResponse(null);
    setIsLoading(true);

    try {
      const data = await callApiPath(path);
      setResponse(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "API call failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="reveal" style={{ animationDelay: "0.08s" }}>
      <div className="surface" style={{ padding: "1.2rem" }}>
        <span className="kicker">Endpoint Sandbox</span>
        <h1 style={{ margin: "0.6rem 0 0.7rem" }}>Developer Console</h1>
        <p className="subhead" style={{ marginBottom: "1rem" }}>
          Quickly probe read endpoints from the deployed frontend origin and inspect payload shape
          without leaving the browser.
        </p>

        <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.8rem" }}>
          <div className="control-group">
            <label htmlFor="preset">Preset path</label>
            <select id="preset" value={path} onChange={(event) => setPath(event.target.value)}>
              {PRESET_PATHS.map((preset) => (
                <option key={preset} value={preset}>
                  {preset}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="path">Path (editable)</label>
            <input
              id="path"
              className="mono"
              value={path}
              onChange={(event) => setPath(event.target.value)}
            />
          </div>

          <div className="info-strip">
            Request target: <span className="mono">{targetUrl}</span>
          </div>

          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? "Calling endpoint..." : "Send Request"}
          </button>
        </form>

        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="surface" style={{ padding: "1rem", marginTop: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Response JSON</h2>
        {response ? (
          <pre
            className="mono"
            style={{
              margin: 0,
              background: "#f2f7f5",
              border: "1px solid rgba(19, 33, 29, 0.1)",
              borderRadius: "0.75rem",
              padding: "0.9rem",
              overflowX: "auto",
              fontSize: "0.78rem",
              lineHeight: 1.55,
            }}
          >
            {JSON.stringify(response, null, 2)}
          </pre>
        ) : (
          <p style={{ margin: 0, color: "var(--ink-700)" }}>
            Submit an endpoint call to view JSON output.
          </p>
        )}
      </div>
    </section>
  );
}

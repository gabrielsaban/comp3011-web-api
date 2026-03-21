"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { fetchRouteRisk, fetchRouteRiskScoringModel } from "@/lib/api";
import { clamp, fmtNumber, fmtRisk } from "@/lib/format";
import type { RouteRiskResponse, RouteRiskScoringModelResponse } from "@/lib/types";

const SAMPLE_ROUTE = [
  "51.5074,-0.1278",
  "51.5560,-0.2796",
  "51.6548,-0.3860",
  "51.7520,-0.3360",
].join("\n");

function parseWaypoints(input: string): [number, number][] {
  const parsed = input
    .split(/\n|;/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [latRaw, lngRaw] = line.split(",").map((part) => part.trim());
      const lat = Number(latRaw);
      const lng = Number(lngRaw);
      if (Number.isNaN(lat) || Number.isNaN(lng)) {
        throw new Error(`Invalid waypoint: ${line}`);
      }
      return [lat, lng] as [number, number];
    });

  if (parsed.length < 2) {
    throw new Error("At least two waypoints are required.");
  }

  return parsed;
}

export default function PlannerPage(): JSX.Element {
  const [waypointInput, setWaypointInput] = useState(SAMPLE_ROUTE);
  const [timeOfDay, setTimeOfDay] = useState("08:30");
  const [dayOfWeek, setDayOfWeek] = useState(2);
  const [segmentLengthKm, setSegmentLengthKm] = useState(0.5);
  const [bufferRadiusKm, setBufferRadiusKm] = useState(0.5);

  const [result, setResult] = useState<RouteRiskResponse | null>(null);
  const [model, setModel] = useState<RouteRiskScoringModelResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const scoringModel = await fetchRouteRiskScoringModel();
        if (!cancelled) {
          setModel(scoringModel);
        }
      } catch {
        if (!cancelled) {
          setModel(null);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const summary = result?.data.route_summary;

  const peakSegment = useMemo(() => {
    if (!result || !summary) {
      return null;
    }
    return result.data.segments.find((segment) => segment.segment_id === summary.peak_segment_id) ?? null;
  }, [result, summary]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setResult(null);

    let waypoints: [number, number][];
    try {
      waypoints = parseWaypoints(waypointInput);
    } catch (parseError) {
      setError(parseError instanceof Error ? parseError.message : "Invalid waypoint list.");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetchRouteRisk({
        waypoints,
        options: {
          time_of_day: timeOfDay,
          day_of_week: dayOfWeek,
          segment_length_km: segmentLengthKm,
          buffer_radius_km: bufferRadiusKm,
        },
      });
      setResult(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Route scoring failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="reveal" style={{ animationDelay: "0.08s" }}>
      <div className="surface" style={{ padding: "1.2rem" }}>
        <span className="kicker">Automated Journey Scoring</span>
        <h1 style={{ margin: "0.6rem 0 0.7rem" }}>Route Planner</h1>
        <p className="subhead" style={{ marginBottom: "1rem" }}>
          Input waypoints and get a weighted risk profile per route segment with clear causal
          factors.
        </p>

        <form onSubmit={onSubmit} className="grid-2" style={{ alignItems: "start" }}>
          <div className="control-group">
            <label htmlFor="waypoints">Waypoints (`lat,lng` per line)</label>
            <textarea
              id="waypoints"
              className="mono"
              value={waypointInput}
              onChange={(event) => setWaypointInput(event.target.value)}
              rows={9}
              placeholder="51.5074,-0.1278"
            />
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setWaypointInput(SAMPLE_ROUTE)}
              >
                Load Sample
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gap: "0.8rem" }}>
            <div className="control-group">
              <label htmlFor="time">Time of day</label>
              <input
                id="time"
                type="time"
                value={timeOfDay}
                onChange={(event) => setTimeOfDay(event.target.value)}
                required
              />
            </div>

            <div className="control-group">
              <label htmlFor="day">Day of week</label>
              <select
                id="day"
                value={dayOfWeek}
                onChange={(event) => setDayOfWeek(Number(event.target.value))}
              >
                <option value={1}>Monday</option>
                <option value={2}>Tuesday</option>
                <option value={3}>Wednesday</option>
                <option value={4}>Thursday</option>
                <option value={5}>Friday</option>
                <option value={6}>Saturday</option>
                <option value={7}>Sunday</option>
              </select>
            </div>

            <div className="control-group">
              <label htmlFor="segment-length">Segment length (km)</label>
              <input
                id="segment-length"
                type="number"
                min={0.1}
                max={2}
                step={0.1}
                value={segmentLengthKm}
                onChange={(event) => setSegmentLengthKm(Number(event.target.value))}
              />
            </div>

            <div className="control-group">
              <label htmlFor="buffer-radius">Buffer radius (km)</label>
              <input
                id="buffer-radius"
                type="number"
                min={0.1}
                max={5}
                step={0.1}
                value={bufferRadiusKm}
                onChange={(event) => setBufferRadiusKm(Number(event.target.value))}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={isLoading}>
              {isLoading ? "Scoring route..." : "Score Route"}
            </button>

            {error && <p className="error-text">{error}</p>}
          </div>
        </form>
      </div>

      {summary && (
        <section className="grid-3" style={{ marginTop: "1rem" }}>
          <article className="surface" style={{ padding: "0.95rem" }}>
            <h2 style={{ margin: 0, fontSize: "1rem" }}>Aggregate Risk</h2>
            <p className="mono" style={{ fontSize: "1.4rem", margin: "0.35rem 0 0" }}>
              {fmtRisk(summary.aggregate_risk_score)} ({summary.risk_label})
            </p>
          </article>
          <article className="surface" style={{ padding: "0.95rem" }}>
            <h2 style={{ margin: 0, fontSize: "1rem" }}>Distance + Segments</h2>
            <p className="mono" style={{ fontSize: "1.4rem", margin: "0.35rem 0 0" }}>
              {summary.total_distance_km.toFixed(1)} km / {summary.segment_count}
            </p>
          </article>
          <article className="surface" style={{ padding: "0.95rem" }}>
            <h2 style={{ margin: 0, fontSize: "1rem" }}>Peak Segment</h2>
            <p className="mono" style={{ fontSize: "1.4rem", margin: "0.35rem 0 0" }}>
              #{summary.peak_segment_id} ({fmtRisk(summary.peak_segment_risk)})
            </p>
          </article>
        </section>
      )}

      {peakSegment && (
        <div className="info-strip" style={{ marginTop: "1rem" }}>
          Segment #{peakSegment.segment_id} is the current route bottleneck with
          {" "}
          <strong>{fmtNumber(peakSegment.nearby_accidents)}</strong> nearby accidents in the
          selected buffer.
        </div>
      )}

      {result && (
        <div className="surface" style={{ padding: "1rem", marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Segment Breakdown</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Segment</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Length</th>
                  <th>Accidents</th>
                  <th>Speed Limit</th>
                  <th>Clusters</th>
                </tr>
              </thead>
              <tbody>
                {result.data.segments.map((segment) => (
                  <tr key={segment.segment_id}>
                    <td>#{segment.segment_id}</td>
                    <td>{segment.risk_label}</td>
                    <td>
                      <div className="score-bar" style={{ width: "9rem", marginBottom: "0.2rem" }}>
                        <span style={{ width: `${clamp(segment.risk_score) * 100}%` }} />
                      </div>
                      <span className="mono">{fmtRisk(segment.risk_score)}</span>
                    </td>
                    <td>{segment.length_km.toFixed(2)} km</td>
                    <td>{fmtNumber(segment.nearby_accidents)}</td>
                    <td>{segment.dominant_speed_limit ?? "-"}</td>
                    <td>{segment.nearby_cluster_ids.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {model && (
        <div className="surface" style={{ padding: "1rem", marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Scoring Model</h2>
          <p className="mono" style={{ marginTop: 0 }}>{model.data.formula}</p>

          <div className="grid-2">
            <div>
              <h3 style={{ marginTop: 0, fontSize: "0.98rem" }}>Weights</h3>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--ink-700)" }}>
                {Object.entries(model.data.weights).map(([key, value]) => (
                  <li key={key}>
                    <span className="mono">{key}</span>: {value}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 style={{ marginTop: 0, fontSize: "0.98rem" }}>Risk bands</h3>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--ink-700)" }}>
                {Object.entries(model.data.risk_labels).map(([range, label]) => (
                  <li key={range}>
                    <span className="mono">{range}</span>: {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

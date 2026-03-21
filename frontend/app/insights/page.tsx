"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  fetchAnnualTrend,
  fetchHotspots,
  fetchRegions,
  fetchWeatherCorrelation,
} from "@/lib/api";
import { fmtNumber, fmtPct } from "@/lib/format";
import type {
  AnnualTrendResponse,
  HotspotsResponse,
  RegionSummary,
  WeatherCorrelationResponse,
} from "@/lib/types";

export default function InsightsPage(): JSX.Element {
  const [regions, setRegions] = useState<RegionSummary[]>([]);
  const [regionId, setRegionId] = useState<string>("");
  const [yearFrom, setYearFrom] = useState(2019);
  const [yearTo, setYearTo] = useState(2023);
  const [metric, setMetric] = useState<"temperature" | "precipitation" | "visibility" | "wind_speed">(
    "precipitation"
  );

  const [lat, setLat] = useState(51.5074);
  const [lng, setLng] = useState(-0.1278);
  const [radiusKm, setRadiusKm] = useState(10);
  const [severity, setSeverity] = useState<string>("");

  const [annualTrend, setAnnualTrend] = useState<AnnualTrendResponse | null>(null);
  const [weatherCorrelation, setWeatherCorrelation] = useState<WeatherCorrelationResponse | null>(null);
  const [hotspots, setHotspots] = useState<HotspotsResponse | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadRegions = async () => {
      try {
        const response = await fetchRegions();
        if (!cancelled) {
          setRegions(response.data);
        }
      } catch {
        if (!cancelled) {
          setRegions([]);
        }
      }
    };

    void loadRegions();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRegionId = useMemo(() => {
    if (!regionId) {
      return undefined;
    }
    return Number(regionId);
  }, [regionId]);

  const loadAnalytics = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const [trend, weather, hotspotData] = await Promise.all([
        fetchAnnualTrend({
          yearFrom,
          yearTo,
          regionId: selectedRegionId,
        }),
        fetchWeatherCorrelation({
          metric,
          regionId: selectedRegionId,
        }),
        fetchHotspots({
          lat,
          lng,
          radiusKm,
          severity: severity ? Number(severity) : undefined,
        }),
      ]);

      setAnnualTrend(trend);
      setWeatherCorrelation(weather);
      setHotspots(hotspotData);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load analytics.");
      setAnnualTrend(null);
      setWeatherCorrelation(null);
      setHotspots(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadAnalytics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadAnalytics();
  };

  return (
    <section className="reveal" style={{ animationDelay: "0.08s" }}>
      <div className="surface" style={{ padding: "1.2rem" }}>
        <span className="kicker">Operational Analytics</span>
        <h1 style={{ margin: "0.6rem 0 0.7rem" }}>Insights Dashboard</h1>
        <p className="subhead" style={{ marginBottom: "1rem" }}>
          Compare region trends, weather-linked severity bands, and local hotspot concentration in
          one live view.
        </p>

        <form onSubmit={onSubmit} className="grid-3" style={{ alignItems: "end" }}>
          <div className="control-group">
            <label htmlFor="region">Region filter</label>
            <select
              id="region"
              value={regionId}
              onChange={(event) => setRegionId(event.target.value)}
            >
              <option value="">All regions</option>
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="year-from">Year from</label>
            <input
              id="year-from"
              type="number"
              min={2019}
              max={2023}
              value={yearFrom}
              onChange={(event) => setYearFrom(Number(event.target.value))}
            />
          </div>

          <div className="control-group">
            <label htmlFor="year-to">Year to</label>
            <input
              id="year-to"
              type="number"
              min={2019}
              max={2023}
              value={yearTo}
              onChange={(event) => setYearTo(Number(event.target.value))}
            />
          </div>

          <div className="control-group">
            <label htmlFor="metric">Weather metric</label>
            <select
              id="metric"
              value={metric}
              onChange={(event) =>
                setMetric(event.target.value as "temperature" | "precipitation" | "visibility" | "wind_speed")
              }
            >
              <option value="precipitation">Precipitation</option>
              <option value="temperature">Temperature</option>
              <option value="visibility">Visibility</option>
              <option value="wind_speed">Wind speed</option>
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="lat">Hotspot center latitude</label>
            <input
              id="lat"
              type="number"
              step={0.0001}
              value={lat}
              onChange={(event) => setLat(Number(event.target.value))}
            />
          </div>

          <div className="control-group">
            <label htmlFor="lng">Hotspot center longitude</label>
            <input
              id="lng"
              type="number"
              step={0.0001}
              value={lng}
              onChange={(event) => setLng(Number(event.target.value))}
            />
          </div>

          <div className="control-group">
            <label htmlFor="radius">Radius (km)</label>
            <input
              id="radius"
              type="number"
              min={1}
              max={100}
              step={1}
              value={radiusKm}
              onChange={(event) => setRadiusKm(Number(event.target.value))}
            />
          </div>

          <div className="control-group">
            <label htmlFor="severity">Severity filter (hotspots)</label>
            <select
              id="severity"
              value={severity}
              onChange={(event) => setSeverity(event.target.value)}
            >
              <option value="">All</option>
              <option value="1">Fatal</option>
              <option value="2">Serious</option>
              <option value="3">Slight</option>
            </select>
          </div>

          <button type="submit" className="btn-primary" disabled={isLoading}>
            {isLoading ? "Refreshing..." : "Refresh Insights"}
          </button>
        </form>

        {error && <p className="error-text" style={{ marginBottom: 0 }}>{error}</p>}
      </div>

      {annualTrend && (
        <div className="surface" style={{ padding: "1rem", marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Annual Trend</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Accidents</th>
                  <th>Casualties</th>
                  <th>Fatal casualties</th>
                  <th>Change %</th>
                </tr>
              </thead>
              <tbody>
                {annualTrend.data.map((row) => (
                  <tr key={row.year}>
                    <td>{row.year}</td>
                    <td>{fmtNumber(row.accidents)}</td>
                    <td>{fmtNumber(row.casualties)}</td>
                    <td>{fmtNumber(row.fatal_casualties)}</td>
                    <td>{row.change_pct === null ? "-" : fmtPct(row.change_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid-2" style={{ marginTop: "1rem" }}>
        <div className="surface" style={{ padding: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Weather Correlation</h2>
          {weatherCorrelation?.data.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Band</th>
                    <th>Total</th>
                    <th>Fatal rate</th>
                    <th>Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {weatherCorrelation.data.slice(0, 10).map((row) => (
                    <tr key={`${row.band}-${row.band_range}`}>
                      <td>
                        {row.band}
                        <div style={{ color: "var(--ink-700)", fontSize: "0.8rem" }}>{row.band_range}</div>
                      </td>
                      <td>{fmtNumber(row.total_accidents)}</td>
                      <td>{fmtPct(row.fatal_rate_pct)}</td>
                      <td>{fmtPct(row.coverage_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ margin: 0, color: "var(--ink-700)" }}>No weather correlation data for this filter.</p>
          )}
        </div>

        <div className="surface" style={{ padding: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Hotspot Cells</h2>
          {hotspots?.data.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Cell (lat,lng)</th>
                    <th>Total</th>
                    <th>Fatal</th>
                    <th>Serious</th>
                  </tr>
                </thead>
                <tbody>
                  {hotspots.data.slice(0, 12).map((cell) => (
                    <tr key={`${cell.cell_lat}-${cell.cell_lng}`}>
                      <td className="mono">
                        {cell.cell_lat.toFixed(4)}, {cell.cell_lng.toFixed(4)}
                      </td>
                      <td>{fmtNumber(cell.accident_count)}</td>
                      <td>{fmtNumber(cell.fatal_count)}</td>
                      <td>{fmtNumber(cell.serious_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ margin: 0, color: "var(--ink-700)" }}>No hotspot cells found for this area.</p>
          )}
        </div>
      </div>
    </section>
  );
}

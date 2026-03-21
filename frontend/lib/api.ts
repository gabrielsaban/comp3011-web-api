import type {
  AnnualTrendResponse,
  ApiErrorShape,
  HealthResponse,
  HotspotsResponse,
  RegionCollectionResponse,
  RouteRiskRequest,
  RouteRiskResponse,
  RouteRiskScoringModelResponse,
  WeatherCorrelationResponse,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function toQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    search.set(key, String(value));
  }
  return search.toString();
}

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as ApiErrorShape;
      if (body.error?.message) {
        message = body.error.message;
      }
    } catch {
      // Ignore JSON parse failure and keep status-based message.
    }
    throw new ApiRequestError(message, response.status);
  }

  return (await response.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function fetchRegions(): Promise<RegionCollectionResponse> {
  return request<RegionCollectionResponse>("/api/v1/regions");
}

export async function fetchRouteRiskScoringModel(): Promise<RouteRiskScoringModelResponse> {
  return request<RouteRiskScoringModelResponse>("/api/v1/analytics/route-risk/scoring-model");
}

export async function fetchRouteRisk(payload: RouteRiskRequest): Promise<RouteRiskResponse> {
  return request<RouteRiskResponse>("/api/v1/analytics/route-risk", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAnnualTrend(options: {
  yearFrom: number;
  yearTo: number;
  regionId?: number;
}): Promise<AnnualTrendResponse> {
  const query = toQueryString({
    year_from: options.yearFrom,
    year_to: options.yearTo,
    region_id: options.regionId,
  });
  return request<AnnualTrendResponse>(`/api/v1/analytics/annual-trend?${query}`);
}

export async function fetchWeatherCorrelation(options: {
  metric: "temperature" | "precipitation" | "visibility" | "wind_speed";
  regionId?: number;
}): Promise<WeatherCorrelationResponse> {
  const query = toQueryString({
    metric: options.metric,
    region_id: options.regionId,
  });
  return request<WeatherCorrelationResponse>(`/api/v1/analytics/weather-correlation?${query}`);
}

export async function fetchHotspots(options: {
  lat: number;
  lng: number;
  radiusKm: number;
  severity?: number;
}): Promise<HotspotsResponse> {
  const query = toQueryString({
    lat: options.lat,
    lng: options.lng,
    radius_km: options.radiusKm,
    severity: options.severity,
  });
  return request<HotspotsResponse>(`/api/v1/analytics/hotspots?${query}`);
}

export async function callApiPath(path: string): Promise<unknown> {
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return request<unknown>(normalised);
}

export { API_BASE_URL };

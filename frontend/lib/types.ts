export type RegionSummary = {
  id: number;
  name: string;
  local_authority_count: number;
};

export type RegionCollectionResponse = {
  data: RegionSummary[];
};

export type RouteRiskRequest = {
  waypoints: [number, number][];
  options?: {
    time_of_day?: string;
    day_of_week?: number;
    segment_length_km?: number;
    buffer_radius_km?: number;
  };
};

export type RouteSummary = {
  total_distance_km: number;
  segment_count: number;
  aggregate_risk_score: number;
  risk_label: string;
  peak_segment_risk: number;
  peak_segment_id: number;
  clusters_intersected: number;
};

export type RouteRiskSegment = {
  segment_id: number;
  start: [number, number];
  end: [number, number];
  length_km: number;
  risk_score: number;
  risk_label: string;
  nearby_accidents: number;
  nearby_cluster_ids: number[];
  dominant_speed_limit: number | null;
  factors: {
    accident_density: number;
    severity_score: number;
    time_risk: number;
    speed_limit_risk: number;
    cluster_proximity: number;
  };
};

export type RouteRiskResponse = {
  data: {
    route_summary: RouteSummary;
    segments: RouteRiskSegment[];
  };
  query: {
    waypoint_count: number;
    segment_length_km: number;
    buffer_radius_km: number;
    time_of_day: string;
    day_of_week: number;
  };
};

export type RouteRiskScoringModelResponse = {
  data: {
    formula: string;
    weights: Record<string, number>;
    factor_descriptions: Record<string, string>;
    risk_labels: Record<string, string>;
  };
};

export type AnnualTrendRow = {
  year: number;
  accidents: number;
  casualties: number;
  fatal_casualties: number;
  change_pct: number | null;
};

export type AnnualTrendResponse = {
  data: AnnualTrendRow[];
  query: {
    year_from: number | null;
    year_to: number | null;
    region_id: number | null;
    local_authority_id: number | null;
  };
};

export type WeatherCorrelationRow = {
  band: string;
  band_range: string;
  total_accidents: number;
  fatal: number;
  serious: number;
  slight: number;
  fatal_rate_pct: number;
  coverage_pct: number;
};

export type WeatherCorrelationResponse = {
  data: WeatherCorrelationRow[];
  query: {
    metric: string;
    date_from: string | null;
    date_to: string | null;
    region_id: number | null;
  };
};

export type HotspotCell = {
  cell_lat: number;
  cell_lng: number;
  accident_count: number;
  fatal_count: number;
  serious_count: number;
};

export type HotspotsResponse = {
  data: HotspotCell[];
  query: {
    lat: number;
    lng: number;
    radius_km: number;
    severity: number | null;
    date_from: string | null;
    date_to: string | null;
  };
};

export type HealthResponse = {
  status: string;
};

export type ApiErrorShape = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown[];
  };
};

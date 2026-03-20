from __future__ import annotations

DEFAULT_SEGMENT_LENGTH_KM = 0.5
MIN_SEGMENT_LENGTH_KM = 0.1
MAX_SEGMENT_LENGTH_KM = 2.0

DEFAULT_BUFFER_RADIUS_KM = 0.5
MIN_BUFFER_RADIUS_KM = 0.1
MAX_BUFFER_RADIUS_KM = 5.0

ACCIDENT_DENSITY_WEIGHT = 0.35
SEVERITY_WEIGHT = 0.30
TIME_RISK_WEIGHT = 0.15
SPEED_LIMIT_WEIGHT = 0.10
CLUSTER_PROXIMITY_WEIGHT = 0.10

ROUTE_RISK_WEIGHTS: dict[str, float] = {
    "accident_density": ACCIDENT_DENSITY_WEIGHT,
    "severity_score": SEVERITY_WEIGHT,
    "time_risk": TIME_RISK_WEIGHT,
    "speed_limit_risk": SPEED_LIMIT_WEIGHT,
    "cluster_proximity": CLUSTER_PROXIMITY_WEIGHT,
}

ROUTE_RISK_FORMULA = (
    "risk_score = w1*accident_density + w2*severity_score + w3*time_risk + "
    "w4*speed_limit_risk + w5*cluster_proximity"
)

FACTOR_DESCRIPTIONS: dict[str, str] = {
    "accident_density": (
        "Accidents per km^2 within the segment buffer, normalised against the cached P99 density."
    ),
    "severity_score": ("Severity-weighted mean: (3*fatal + 2*serious + 1*slight) / (3 * total)."),
    "time_risk": (
        "Cached accidents-by-time cell for the requested day/hour, normalised "
        "against the maximum cached heatmap cell."
    ),
    "speed_limit_risk": (
        "Fatal-rate percentage for the dominant nearby speed limit, normalised "
        "against the maximum cached speed fatal rate."
    ),
    "cluster_proximity": (
        "1.0 inside any cluster radius; otherwise decays linearly to 0.0 by 2km "
        "beyond the nearest cluster edge."
    ),
}

RISK_LABEL_BANDS: tuple[tuple[float, str], ...] = (
    (0.2, "Very Low"),
    (0.4, "Low"),
    (0.6, "Moderate"),
    (0.8, "High"),
    (1.01, "Critical"),
)

RISK_LABEL_RANGES: dict[str, str] = {
    "0.0-0.2": "Very Low",
    "0.2-0.4": "Low",
    "0.4-0.6": "Moderate",
    "0.6-0.8": "High",
    "0.8-1.0": "Critical",
}


def risk_label_for_score(score: float) -> str:
    bounded = max(0.0, min(score, 1.0))
    for upper_bound, label in RISK_LABEL_BANDS:
        if bounded <= upper_bound:
            return label
    return "Critical"

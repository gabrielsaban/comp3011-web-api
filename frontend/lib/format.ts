export function fmtNumber(value: number, maxFractionDigits = 0): string {
  return new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: maxFractionDigits,
  }).format(value);
}

export function fmtPct(value: number, maxFractionDigits = 1): string {
  return `${value.toFixed(maxFractionDigits)}%`;
}

export function fmtRisk(value: number): string {
  return value.toFixed(3);
}

export function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

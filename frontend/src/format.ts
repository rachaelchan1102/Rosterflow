const DATE_FMT = new Intl.DateTimeFormat("en-CA", { weekday: "short", month: "short", day: "numeric" });
const MONTH_FMT = new Intl.DateTimeFormat("en-CA", { month: "long", year: "numeric" });

/** "2026-10-03" → a local Date at midnight (not UTC, which would shift the day west of Greenwich). */
export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatDate(iso: string): string {
  return DATE_FMT.format(parseDate(iso));
}

export function formatMonth(yyyyMm: string): string {
  return MONTH_FMT.format(parseDate(`${yyyyMm}-01`));
}

export function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

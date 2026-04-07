import type { Tone } from "./types";

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatMetric(value: unknown, digits = 3): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function compactId(value: string): string {
  if (value.length <= 14) return value;
  return `${value.slice(0, 6)}…${value.slice(-6)}`;
}

export function statusTone(status: string): Tone {
  const normalized = status.toLowerCase();
  if (["completed", "ready", "ok"].includes(normalized)) return "success";
  if (["failed", "error", "cancelled"].includes(normalized)) return "danger";
  if (["cancel_requested", "retrying", "degraded"].includes(normalized)) return "warning";
  if (["running", "queued", "starting"].includes(normalized)) return "info";
  return "neutral";
}

export function labelFromStatus(status: string): string {
  return status.split("_").join(" ");
}

export function groupCountByStatus(items: Array<{ status: string }>): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
}

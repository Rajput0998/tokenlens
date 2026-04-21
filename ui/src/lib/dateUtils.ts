/**
 * Shared date/time utilities for consistent UTC → local time conversion.
 *
 * The backend stores and returns timestamps in UTC. Python's datetime.isoformat()
 * does NOT append a "Z" suffix, so JavaScript's Date constructor interprets
 * them as local time — causing displayed times to appear in UTC.
 *
 * toUtcDate() solves this by forcing UTC parsing when no timezone indicator is present.
 */

/** Parse an ISO string as UTC, even if it lacks a Z/+offset suffix. */
export function toUtcDate(iso: string): Date {
  const trimmed = iso.trim();
  // Already has timezone indicator: Z, or +HH:MM / -HH:MM at the end
  const hasTimezone = /Z$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed);
  return new Date(hasTimezone ? trimmed : trimmed + "Z");
}

/** Format a UTC ISO string as local time (e.g. "02:30 PM") */
export function formatLocalTime(
  iso: string | null | undefined,
  fallback = "—"
): string {
  if (!iso) return fallback;
  try {
    return toUtcDate(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return fallback;
  }
}

/** Format a UTC ISO string as local date (e.g. "Apr 21, 2026") */
export function formatLocalDate(
  iso: string | null | undefined,
  fallback = "—"
): string {
  if (!iso) return fallback;
  try {
    return toUtcDate(iso).toLocaleDateString([], {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return fallback;
  }
}

/** Format a UTC ISO string as local date + time (e.g. "Apr 21, 02:30 PM") */
export function formatLocalDateTime(
  iso: string | null | undefined,
  fallback = "—"
): string {
  if (!iso) return fallback;
  try {
    return toUtcDate(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return fallback;
  }
}

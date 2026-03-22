/**
 * NLYT — Unified Date Formatting Utility
 * 
 * RULE: Backend stores & returns UTC ISO strings (ending with 'Z').
 * Frontend converts to the user's local timezone for display.
 * 
 * This module is the SINGLE source of truth for date formatting.
 * Every page MUST use these functions instead of inline Date formatting.
 */

const USER_TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

/**
 * Format a UTC ISO string as a full French datetime.
 * Example: "lundi 24 mars 2026 à 01:04"
 */
export function formatDateTimeFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  const datePart = d.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: USER_TIMEZONE,
  });
  const timePart = d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: USER_TIMEZONE,
  });
  return `${datePart} à ${timePart}`;
}

/**
 * Format a UTC ISO string as a compact French datetime (for cards/lists).
 * Example: "lundi 24 mars 2026, 01:04"
 */
export function formatDateTimeCompactFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  return d.toLocaleString('fr-FR', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: USER_TIMEZONE,
  });
}

/**
 * Format time only: "01:04"
 */
export function formatTimeFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  return d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: USER_TIMEZONE,
  });
}

/**
 * Format date only (short): "lun. 24 mars"
 */
export function formatDateShortFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  return d.toLocaleDateString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: USER_TIMEZONE,
  });
}

/**
 * Format date only (long): "lundi 24 mars 2026"
 */
export function formatDateLongFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  return d.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: USER_TIMEZONE,
  });
}

/**
 * Format a full evidence/event timestamp: "lundi 24 mars 2026 à 01:04:32"
 */
export function formatEvidenceDateFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  const datePart = d.toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: USER_TIMEZONE,
  });
  const timePart = d.toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: USER_TIMEZONE,
  });
  return `${datePart} à ${timePart}`;
}

/**
 * Format a relative date for display (e.g. "Accepté le 24 mars 2026 à 01:04")
 */
export function formatActionDateFr(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;
  return d.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: USER_TIMEZONE,
  });
}

/**
 * Convert a <input type="datetime-local"> value to UTC ISO string.
 * datetime-local gives values in the user's local timezone (e.g. "2026-03-24T01:04").
 * We convert to UTC for the backend.
 */
export function localInputToUTC(localDatetimeValue) {
  if (!localDatetimeValue) return '';
  const d = new Date(localDatetimeValue);
  if (isNaN(d.getTime())) return localDatetimeValue;
  return d.toISOString(); // e.g. "2026-03-24T00:04:00.000Z"
}

/**
 * Convert a UTC ISO string back to a value suitable for <input type="datetime-local">.
 * This is needed when editing an appointment — the input expects local time format.
 */
export function utcToLocalInput(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  // Format as YYYY-MM-DDTHH:MM in local time
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Parse a UTC ISO string to a Date object. Returns null if invalid.
 */
export function parseUTC(isoString) {
  if (!isoString) return null;
  const d = new Date(isoString);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Get the user's timezone name (e.g. "Europe/Paris")
 */
export function getUserTimezone() {
  return USER_TIMEZONE;
}

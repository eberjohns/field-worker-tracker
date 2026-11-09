/**
 * Format minutes as HH:MM
 * e.g. 510 -> "08:30", 0 -> "00:00"
 */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || isNaN(minutes)) {
    return "-";
  }
  const isNeg = minutes < 0;
  const abs = Math.abs(minutes);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  const padH = String(h).padStart(2, "0");
  const padM = String(m).padStart(2, "0");
  return `${isNeg ? "-" : ""}${padH}:${padM}`;
}

/**
 * Format signed variation in minutes
 * e.g. -30 -> "-00:30", +30 -> "+00:30", 0 -> "00:00"
 */
export function formatSignedMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || isNaN(minutes)) {
    return "-";
  }
  if (minutes === 0) {
    return "00:00";
  }
  const isNeg = minutes < 0;
  const abs = Math.abs(minutes);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  const padH = String(h).padStart(2, "0");
  const padM = String(m).padStart(2, "0");
  return `${isNeg ? "-" : "+"}${padH}:${padM}`;
}

/**
 * Format time string (either "HH:MM:SS" or ISO timestamp) to "HH:MM"
 */
export function formatTime(timeStr: string | null | undefined): string {
  if (!timeStr) return "-";
  if (timeStr.includes("T")) {
    const d = new Date(timeStr);
    if (isNaN(d.getTime())) return "-";
    const h = String(d.getUTCHours()).padStart(2, "0");
    const m = String(d.getUTCMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }
  const parts = timeStr.split(":");
  if (parts.length >= 2) {
    return `${parts[0].padStart(2, "0")}:${parts[1].padStart(2, "0")}`;
  }
  return timeStr;
}

/**
 * Format date string "YYYY-MM-DD"
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  try {
    const [y, m, d] = dateStr.split("-").map(Number);
    const date = new Date(Date.UTC(y, m - 1, d));
    return date.toLocaleDateString("en-GB", {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return dateStr;
  }
}


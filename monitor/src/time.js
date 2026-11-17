export const TIME_ZONE = "America/Bogota";

const CLOCK = new Intl.DateTimeFormat("en-GB", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const SHORT = new Intl.DateTimeFormat("en-GB", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

// Colombia time (UTC-5, no daylight saving) of a unix time in seconds, as HH:MM:SS.
export function colombiaTime(unixSeconds) {
  return CLOCK.format(new Date(unixSeconds * 1000));
}

// The same as HH:MM, for the chart axes.
export function colombiaShort(unixSeconds) {
  return SHORT.format(new Date(unixSeconds * 1000));
}

export function durationText(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = String(total % 60).padStart(2, "0");
  return minutes + ":" + rest;
}

/** Which tactical-brief band matches local wall clock (v1 fixed windows). */
export type TacticalBandKey = "morning" | "afternoon" | "evening";

export function activeTacticalBand(now: Date): TacticalBandKey {
  const h = now.getHours();
  if (h >= 17) return "evening";
  if (h >= 12) return "afternoon";
  return "morning";
}

export const TACTICAL_BAND_LABEL: Record<TacticalBandKey, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

import { LondonEvent } from "../types";
import { clamp } from "./utils";

export function estimateCrowdAndSentiment(event: LondonEvent) {
  // Future adapter seam: replace with social sentiment feeds, booking velocity,
  // venue occupancy, anonymised mobility data, and public safety/crowd signals.
  const density = clamp((event.expectedAttendance / event.capacity) * 100);
  const overcrowdingRisk = clamp(Math.max(0, density - 78) * 2.2);
  const label = density > 88 ? "packed" : density > 70 ? "busy" : density > 45 ? "balanced" : "quiet";

  return {
    crowdDensity: density,
    sentimentScore: event.sentimentEstimate,
    socialEnergy: event.socialEnergy,
    overcrowdingRisk,
    label
  };
}

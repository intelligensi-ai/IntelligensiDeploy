import { knownLocations, mockCityConditions } from "../data/mockCityConditions";
import { CityConditions, LondonEvent, TravelEstimate } from "../types";
import { clamp, haversineKm } from "./utils";

const sharedTransportBoost = (a: string[], b: string[]) => {
  const joinedA = a.map((item) => item.toLowerCase());
  const joinedB = b.map((item) => item.toLowerCase());
  if (joinedA.some((hub) => joinedB.includes(hub))) return -12;
  if (joinedA.includes("elizabeth line") && joinedB.includes("elizabeth line")) return -14;
  if (joinedA.includes("northern") && joinedB.includes("northern")) return -7;
  if (joinedA.includes("jubilee") && joinedB.includes("jubilee")) return -6;
  if (joinedA.includes("central") && joinedB.includes("central")) return -6;
  return 0;
};

export function estimateTravel(
  startLocationName: string,
  event: LondonEvent,
  conditions: CityConditions = mockCityConditions
): TravelEstimate {
  // Future adapter seam: replace this heuristic with TfL Journey Planner,
  // OpenStreetMap routing, Google Maps, or a local graph model of Tube and rail links.
  const start =
    knownLocations.find((location) => location.name.toLowerCase() === startLocationName.toLowerCase()) ||
    knownLocations[0];
  const distance = haversineKm(start, event.location);
  const networkEffect = start.networkBias + event.location.networkBias + sharedTransportBoost(start.transportHubs, event.location.transportHubs);
  const affectedDisruptions = conditions.disruptions.filter((disruption) =>
    disruption.affectedHubs.some((hub) =>
      [...start.transportHubs, ...event.location.transportHubs, event.location.name]
        .map((item) => item.toLowerCase())
        .includes(hub.toLowerCase())
    )
  );
  const disruptionPenalty = affectedDisruptions.reduce((sum, item) => sum + item.severity * 18, 0);
  const orbitalPenalty = Math.abs(start.lng - event.location.lng) > 0.12 && Math.abs(start.lat - event.location.lat) > 0.035 ? 8 : 0;
  const riverPenalty = start.lat > 51.51 && event.location.lat < 51.49 ? 7 : 0;
  const base = 16 + distance * 7.2 + networkEffect + disruptionPenalty + orbitalPenalty + riverPenalty;
  const travelMinutes = clamp(base, 8, 95);
  const changes = travelMinutes < 22 ? 0 : travelMinutes < 42 ? 1 : travelMinutes < 65 ? 2 : 3;
  const reliability = clamp(92 - affectedDisruptions.reduce((sum, item) => sum + item.severity * 55, 0) - changes * 4);
  const effort = travelMinutes < 30 ? "low" : travelMinutes <= 60 ? "medium" : "high";
  const routeSummary =
    sharedTransportBoost(start.transportHubs, event.location.transportHubs) < -8
      ? "Direct high-connectivity route, likely Tube or Elizabeth line led"
      : changes <= 1
        ? "Simple cross-London route with one main interchange"
        : "Non-linear route with multiple interchanges despite London proximity";

  return {
    travelMinutes,
    changes,
    reliability,
    disruptionWarnings: affectedDisruptions.map((item) => item.message),
    effort,
    routeSummary,
    mode: travelMinutes < 18 ? "walk-mix" : travelMinutes < 48 ? "tube" : "rail"
  };
}

import { mockCityConditions } from "../data/mockCityConditions";
import { CityConditions, LondonEvent, WeatherImpact } from "../types";
import { clamp } from "./utils";

const zoneForEvent = (event: LondonEvent) => {
  if (event.location.lat < 51.49) return "south";
  if (event.location.lng > -0.055) return "east";
  if (event.location.lng < -0.15) return "west";
  if (event.location.lat > 51.528) return "north";
  return "central";
};

export function estimateWeatherImpact(
  event: LondonEvent,
  conditions: CityConditions = mockCityConditions
): WeatherImpact {
  // Future adapter seam: replace mock zones with Open-Meteo, Met Office, or venue-local forecasts.
  const baseline = conditions.weatherByZone[zoneForEvent(event)] || conditions.weatherByZone.central;
  const eventPenalty = event.outdoor
    ? baseline.weatherPenalty + event.weatherSensitivity * (baseline.rainRisk / 100) * 0.55
    : baseline.weatherPenalty * (event.weatherSensitivity / 100);

  return {
    ...baseline,
    outdoorSuitability: clamp(baseline.outdoorSuitability - (event.outdoor ? eventPenalty * 0.4 : 0)),
    weatherPenalty: clamp(eventPenalty)
  };
}

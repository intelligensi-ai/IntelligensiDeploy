import {
  CrowdSentiment,
  LondonEvent,
  LocationPoint,
  ParsedIntent,
  TravelEstimate,
  WeatherImpact
} from "../types";

// Future integration adapters. The prototype deliberately uses local simulated
// data today, but these function boundaries are where live services can attach.

export async function fetchEventbriteEvents(_intent: ParsedIntent): Promise<LondonEvent[]> {
  throw new Error("Eventbrite adapter not configured for the local prototype.");
}

export async function fetchLondonOpenDataEvents(_intent: ParsedIntent): Promise<LondonEvent[]> {
  throw new Error("London open data adapter not configured for the local prototype.");
}

export async function fetchTfLJourneyEstimate(
  _from: LocationPoint,
  _to: LocationPoint,
  _timeIso: string
): Promise<TravelEstimate> {
  throw new Error("TfL adapter not configured for the local prototype.");
}

export async function fetchOpenMeteoWeather(_location: LocationPoint): Promise<WeatherImpact> {
  throw new Error("Open-Meteo adapter not configured for the local prototype.");
}

export async function fetchVenueSentiment(_event: LondonEvent): Promise<CrowdSentiment> {
  throw new Error("Sentiment adapter not configured for the local prototype.");
}

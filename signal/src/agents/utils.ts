import { AgentTrace, EventCategory, LondonEvent, ParsedIntent, PriorityWeights } from "../types";

export const clamp = (value: number, min = 0, max = 100) =>
  Math.max(min, Math.min(max, Math.round(value)));

export const defaultPriorityWeights: PriorityWeights = {
  networking: 55,
  entertainment: 45,
  lowCost: 45,
  lowEffort: 45,
  culturalValue: 35,
  professionalRelevance: 50,
  socialCompatibility: 35,
  learningOpportunity: 40,
  novelty: 35
};

export const categoryKeywords: Record<EventCategory, string[]> = {
  "ai-tech": ["ai", "artificial intelligence", "ml", "machine learning", "robotics", "tech"],
  business: ["business", "startup", "founder", "investor", "network", "pitch", "fintech"],
  culture: ["culture", "cultural", "art", "museum", "music", "jazz", "gallery", "exhibition"],
  nightlife: ["nightlife", "comedy", "pub", "bar", "after work", "night out", "social"],
  sports: ["sports", "football", "premier league", "screening"],
  gaming: ["gaming", "game", "esports", "playtest"],
  community: ["community", "public", "civic", "open data", "festival", "food"],
  education: ["conference", "education", "talk", "briefing", "forum", "learning", "policy"]
};

export const profileKeywords = [
  "investors",
  "founders",
  "senior engineers",
  "engineers",
  "creatives",
  "students",
  "tourists",
  "professionals",
  "gamers",
  "sports fans",
  "dating",
  "social",
  "policy",
  "public services",
  "mentors",
  "operators"
];

export function textIncludesAny(text: string, words: string[]) {
  const lower = text.toLowerCase();
  return words.some((word) => lower.includes(word));
}

export function scoreTextMatch(textParts: string[], desiredTerms: string[]) {
  if (desiredTerms.length === 0) return 55;
  const haystack = textParts.join(" ").toLowerCase();
  const matches = desiredTerms.filter((term) => haystack.includes(term.toLowerCase()));
  const partials = desiredTerms.filter((term) =>
    term
      .toLowerCase()
      .split(/\s+/)
      .some((token) => token.length > 3 && haystack.includes(token))
  );
  return clamp(35 + matches.length * 22 + partials.length * 8, 0, 100);
}

export function eventTextParts(event: LondonEvent) {
  return [
    event.name,
    event.category,
    event.location.name,
    event.location.borough,
    event.description,
    ...event.tags,
    ...event.attendeeProfile,
    ...event.desiredMatches
  ];
}

export function dateFitsIntent(event: LondonEvent, intent: ParsedIntent) {
  const date = new Date(event.startTime);
  const day = date.getDay();
  const hour = date.getHours();

  if (intent.dateWindow === "this-weekend") {
    return day === 0 || day === 6;
  }

  if (intent.dateWindow === "tonight" || intent.dateWindow === "after-work") {
    return event.startTime.startsWith("2026-05-28") && hour >= 17;
  }

  return true;
}

export function timingSuitability(event: LondonEvent, intent: ParsedIntent) {
  const hour = new Date(event.startTime).getHours();
  if (intent.dateWindow === "after-work") {
    return clamp(100 - Math.abs(hour - 18.5) * 14);
  }
  if (intent.dateWindow === "tonight") {
    return clamp(95 - Math.max(0, hour - 20) * 8);
  }
  if (intent.dateWindow === "this-weekend") {
    return clamp(80 + (hour >= 11 && hour <= 20 ? 12 : -10));
  }
  return 75;
}

export function haversineKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const earthRadiusKm = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const x =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.sin(dLng / 2) * Math.sin(dLng / 2) * Math.cos(lat1) * Math.cos(lat2);
  return earthRadiusKm * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}

export function makeTrace(
  agent: string,
  summary: string,
  details?: string,
  status: AgentTrace["status"] = "success"
): AgentTrace {
  return { agent, summary, details, status };
}

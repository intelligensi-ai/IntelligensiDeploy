import { mockEvents } from "../data/mockEvents";
import { AgentTrace, LondonEvent, ParsedIntent } from "../types";
import { dateFitsIntent, eventTextParts, makeTrace, scoreTextMatch, textIncludesAny } from "./utils";

export function estimateIntentRelevance(event: LondonEvent, intent: ParsedIntent) {
  const textParts = eventTextParts(event);
  const attendeeScore = scoreTextMatch(textParts, intent.desiredAttendees);
  const categoryScore = intent.categories.length
    ? intent.categories.includes(event.category)
      ? 88
      : textIncludesAny(textParts.join(" "), intent.categories)
        ? 55
        : 28
    : 58;
  const priorityBoost =
    (intent.priorities.networking / 100) * event.networkingValue * 0.18 +
    (intent.priorities.culturalValue / 100) * (event.category === "culture" ? 20 : 0) +
    (intent.priorities.learningOpportunity / 100) * event.learningValue * 0.12 +
    (intent.priorities.novelty / 100) * event.novelty * 0.08;

  return Math.round(Math.min(100, categoryScore * 0.45 + attendeeScore * 0.4 + priorityBoost));
}

export function discoverEvents(
  intent: ParsedIntent,
  events: LondonEvent[] = mockEvents
): { events: LondonEvent[]; trace: AgentTrace } {
  // Future adapter seam: replace mockEvents with Eventbrite, Meetup-style sources,
  // London Datastore, venue listing APIs, or web search enrichment.
  const timedEvents = events.filter((event) => dateFitsIntent(event, intent));
  const scored = timedEvents
    .map((event) => ({ event, score: estimateIntentRelevance(event, intent) }))
    .filter(({ score }) => score >= (intent.categories.length || intent.desiredAttendees.length ? 38 : 0))
    .sort((a, b) => b.score - a.score);

  const selected = scored.length ? scored.slice(0, 14).map(({ event }) => event) : timedEvents.slice(0, 14);
  return {
    events: selected,
    trace: makeTrace(
      "Event Discovery Agent",
      `Found ${selected.length} candidate events from ${timedEvents.length} time-compatible London listings.`,
      "Mock event corpus now. Replaceable with Eventbrite, Meetup, venue listings, London Datastore, and City of London open data."
    )
  };
}

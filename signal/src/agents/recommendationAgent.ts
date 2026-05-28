import { mockCityConditions } from "../data/mockCityConditions";
import { mockEvents } from "../data/mockEvents";
import {
  AgentTrace,
  CityConditions,
  EventRecommendation,
  LondonEvent,
  ParsedIntent,
  WorthItJudgement
} from "../types";
import { estimateAttendeeRelevance } from "./attendeeRelevanceAgent";
import { estimateCost } from "./costAgent";
import { discoverEvents, estimateIntentRelevance } from "./eventDiscoveryAgent";
import { estimateCrowdAndSentiment } from "./sentimentAgent";
import { estimateTravel } from "./transportAgent";
import { clamp, makeTrace, timingSuitability } from "./utils";
import { estimateWeatherImpact } from "./weatherAgent";

const judgementFor = (overall: number, travelMinutes: number, intentRelevance: number): WorthItJudgement => {
  if (overall >= 84) return "Strong yes";
  if (overall >= 74 && intentRelevance >= 72) return "Yes, if networking is your priority";
  if (overall >= 70 && travelMinutes < 30) return "Yes, if convenience is your priority";
  if (overall >= 62 && travelMinutes > 60) return "Maybe, but travel effort is high";
  if (overall >= 58) return "Better alternative available";
  return "Not recommended tonight";
};

const scoreTravel = (minutes: number, reliability: number, tolerance: number) =>
  clamp(100 - minutes * 1.05 + reliability * 0.22 + (minutes <= tolerance ? 12 : -10));

const scoreCrowd = (density: number, overcrowdingRisk: number) =>
  clamp(86 - Math.abs(density - 72) * 0.55 - overcrowdingRisk * 0.35);

export function scoreEvent(
  event: LondonEvent,
  intent: ParsedIntent,
  conditions: CityConditions = mockCityConditions
): EventRecommendation {
  const travel = estimateTravel(intent.startLocation, event, conditions);
  const weather = estimateWeatherImpact(event, conditions);
  const cost = estimateCost(event, travel, intent);
  const sentiment = estimateCrowdAndSentiment(event);
  const attendee = estimateAttendeeRelevance(event, intent);
  const intentRelevance = estimateIntentRelevance(event, intent);
  const timing = timingSuitability(event, intent);
  const travelScore = scoreTravel(travel.travelMinutes, travel.reliability, intent.travelToleranceMinutes);
  const crowdScore = scoreCrowd(sentiment.crowdDensity, sentiment.overcrowdingRisk);
  const weatherScore = clamp(100 - weather.weatherPenalty);
  const networkingPotential = clamp(event.networkingValue * (intent.priorities.networking / 85));

  const overall = clamp(
    intentRelevance * 0.25 +
      attendee.score * 0.2 +
      travelScore * 0.15 +
      cost.costScore * 0.1 +
      timing * 0.1 +
      sentiment.sentimentScore * 0.1 +
      weatherScore * 0.05 +
      crowdScore * 0.05
  );

  const confidence = clamp(
    intent.confidence * 0.32 +
      attendee.confidence * 0.26 +
      travel.reliability * 0.18 +
      event.sentimentEstimate * 0.12 +
      (cost.budgetFit ? 88 : 62) * 0.12
  );

  const tradeOffs = [
    travel.travelMinutes > intent.travelToleranceMinutes
      ? `Travel is above your stated tolerance at ${travel.travelMinutes} minutes.`
      : `Travel is within tolerance at ${travel.travelMinutes} minutes.`,
    cost.budgetFit
      ? `Estimated total cost is within budget at GBP${cost.estimatedTotalCost}.`
      : `Estimated total cost is above budget at GBP${cost.estimatedTotalCost}.`,
    sentiment.overcrowdingRisk > 25
      ? `Crowd risk is elevated because projected density is ${sentiment.crowdDensity}%.`
      : `Crowd level looks ${sentiment.label}, not a major downside.`
  ];

  const judgement = judgementFor(overall, travel.travelMinutes, intentRelevance);
  const explanation =
    `${event.name} scores ${overall}/100 because it matches ${intent.goal.toLowerCase()} with ` +
    `${attendee.score}/100 attendee relevance, ${travel.effort} travel effort, and a ` +
    `${cost.budgetFit ? "healthy" : "strained"} budget fit.`;

  const trace: AgentTrace[] = [
    makeTrace(
      "Transport Agent",
      `${travel.travelMinutes} minutes from ${intent.startLocation}; ${travel.effort} effort.`,
      `${travel.routeSummary}. ${travel.disruptionWarnings[0] || "No major disruption warnings."}`,
      travel.effort === "high" ? "warning" : "success"
    ),
    makeTrace(
      "Weather Agent",
      `${weather.condition}; ${weather.rainRisk}% rain risk.`,
      event.outdoor
        ? `Outdoor event weather suitability is ${weather.outdoorSuitability}/100.`
        : "Indoor event has limited weather exposure."
    ),
    makeTrace(
      "Cost Agent",
      cost.budgetFit ? "Within budget." : "Above budget.",
      `Ticket GBP${cost.ticketPrice}, travel GBP${cost.estimatedTravelCost}, food/drink GBP${cost.estimatedFoodDrink}.`
    ),
    makeTrace(
      "Attendee Relevance Agent",
      `${attendee.score}/100 attendee relevance.`,
      attendee.explanation
    ),
    makeTrace(
      "Recommendation Agent",
      `${judgement}: Signal Score ${overall}/100.`,
      "Weighted model: relevance 25%, attendee fit 20%, travel 15%, cost 10%, timing 10%, sentiment 10%, weather 5%, crowd 5%."
    )
  ];

  return {
    event,
    scores: {
      overall,
      intentRelevance,
      attendeeRelevance: attendee.score,
      travelEffort: travelScore,
      costFit: cost.costScore,
      timingSuitability: timing,
      sentiment: sentiment.sentimentScore,
      weather: weatherScore,
      crowdSuitability: crowdScore,
      networkingPotential,
      confidence
    },
    travel,
    weather,
    cost,
    sentiment,
    attendee,
    judgement,
    explanation,
    tradeOffs,
    trace
  };
}

export function buildRecommendations(
  intent: ParsedIntent,
  events: LondonEvent[] = mockEvents,
  conditions: CityConditions = mockCityConditions
): { recommendations: EventRecommendation[]; trace: AgentTrace[] } {
  const discovery = discoverEvents(intent, events);
  const recommendations = discovery.events
    .map((event) => scoreEvent(event, intent, conditions))
    .sort((a, b) => b.scores.overall - a.scores.overall);

  return {
    recommendations,
    trace: [
      makeTrace(
        "Intent Agent",
        `Detected ${intent.categories.length ? intent.categories.join(", ") : "open category"} intent from ${intent.startLocation}.`,
        `Budget GBP${intent.budget}, time window ${intent.dateWindow}, desired attendees: ${
          intent.desiredAttendees.join(", ") || "not specified"
        }.`
      ),
      discovery.trace,
      ...(recommendations[0]?.trace || [])
    ]
  };
}

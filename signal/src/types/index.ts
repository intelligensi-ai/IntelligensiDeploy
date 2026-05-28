export type EventCategory =
  | "ai-tech"
  | "business"
  | "culture"
  | "nightlife"
  | "sports"
  | "gaming"
  | "community"
  | "education";

export type EffortClass = "low" | "medium" | "high";

export type WorthItJudgement =
  | "Strong yes"
  | "Yes, if networking is your priority"
  | "Yes, if convenience is your priority"
  | "Maybe, but travel effort is high"
  | "Better alternative available"
  | "Not recommended tonight";

export interface LocationPoint {
  name: string;
  borough: string;
  lat: number;
  lng: number;
  transportHubs: string[];
  networkBias: number;
}

export interface LondonEvent {
  id: string;
  name: string;
  category: EventCategory;
  location: LocationPoint;
  startTime: string;
  endTime: string;
  price: number;
  estimatedFoodDrink: number;
  tags: string[];
  description: string;
  expectedAttendance: number;
  capacity: number;
  attendeeProfile: string[];
  desiredMatches: string[];
  networkingValue: number;
  sentimentEstimate: number;
  socialEnergy: number;
  weatherSensitivity: number;
  novelty: number;
  learningValue: number;
  source: string;
  outdoor: boolean;
}

export interface PriorityWeights {
  networking: number;
  entertainment: number;
  lowCost: number;
  lowEffort: number;
  culturalValue: number;
  professionalRelevance: number;
  socialCompatibility: number;
  learningOpportunity: number;
  novelty: number;
}

export interface ParsedIntent {
  rawText: string;
  goal: string;
  categories: EventCategory[];
  desiredAttendees: string[];
  dateWindow: "tonight" | "this-weekend" | "after-work" | "any";
  startLocation: string;
  budget: number;
  travelToleranceMinutes: number;
  priorities: PriorityWeights;
  compareMode: boolean;
  confidence: number;
  missingContext: string[];
}

export interface TravelEstimate {
  travelMinutes: number;
  changes: number;
  reliability: number;
  disruptionWarnings: string[];
  effort: EffortClass;
  routeSummary: string;
  mode: "tube" | "rail" | "bus" | "walk-mix";
}

export interface WeatherImpact {
  condition: string;
  rainRisk: number;
  temperatureC: number;
  outdoorSuitability: number;
  weatherPenalty: number;
}

export interface CostImpact {
  ticketPrice: number;
  estimatedTravelCost: number;
  estimatedFoodDrink: number;
  estimatedTotalCost: number;
  budgetFit: boolean;
  costScore: number;
}

export interface CrowdSentiment {
  crowdDensity: number;
  sentimentScore: number;
  socialEnergy: number;
  overcrowdingRisk: number;
  label: string;
}

export interface AttendeeRelevance {
  score: number;
  explanation: string;
  confidence: number;
  matchedProfiles: string[];
}

export interface ScoreBreakdown {
  overall: number;
  intentRelevance: number;
  attendeeRelevance: number;
  travelEffort: number;
  costFit: number;
  timingSuitability: number;
  sentiment: number;
  weather: number;
  crowdSuitability: number;
  networkingPotential: number;
  confidence: number;
}

export interface AgentTrace {
  agent: string;
  status: "success" | "warning" | "info";
  summary: string;
  details?: string;
}

export interface EventRecommendation {
  event: LondonEvent;
  scores: ScoreBreakdown;
  travel: TravelEstimate;
  weather: WeatherImpact;
  cost: CostImpact;
  sentiment: CrowdSentiment;
  attendee: AttendeeRelevance;
  judgement: WorthItJudgement;
  explanation: string;
  tradeOffs: string[];
  trace: AgentTrace[];
}

export interface CityConditions {
  generatedAt: string;
  cityMood: string;
  weatherByZone: Record<string, WeatherImpact>;
  disruptions: Array<{
    affectedHubs: string[];
    severity: number;
    message: string;
  }>;
  baselineTravelCost: number;
}

export interface UserProfile {
  name: string;
  email: string;
  phone: string;
  homeLocation: string;
  workLocation: string;
  budgetPreference: number;
  interests: string[];
  networkingGoals: string[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  timestamp: string;
}

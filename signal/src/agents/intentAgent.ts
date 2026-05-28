import { knownLocations } from "../data/mockCityConditions";
import { EventCategory, ParsedIntent, UserProfile } from "../types";
import { categoryKeywords, defaultPriorityWeights, profileKeywords, textIncludesAny } from "./utils";

const detectCategories = (text: string): EventCategory[] => {
  const found = Object.entries(categoryKeywords)
    .filter(([, words]) => textIncludesAny(text, words))
    .map(([category]) => category as EventCategory);

  if (text.includes("network") || text.includes("investor") || text.includes("founder")) {
    return Array.from(new Set([...found, "business"]));
  }

  return found;
};

const detectBudget = (text: string, profile?: UserProfile) => {
  const budgetMatch = text.match(
    /(?:under|below|less than|max|maximum|budget|spend|cost|keep).*?(?:gbp|\u00a3)?\s*(\d{1,3})/i
  );
  const looseMoney = text.match(/(?:gbp|\u00a3)\s*(\d{1,3})/i);
  if (budgetMatch) return Number(budgetMatch[1]);
  if (looseMoney) return Number(looseMoney[1]);
  return profile?.budgetPreference || 35;
};

const detectStartLocation = (text: string, profile?: UserProfile) => {
  const lower = text.toLowerCase();
  const explicitLocation = knownLocations.find((location) => lower.includes(location.name.toLowerCase()));
  if (explicitLocation) return explicitLocation.name;

  if (profile?.workLocation && (lower.includes("after work") || lower.includes("from work"))) {
    return profile.workLocation;
  }

  if (profile?.homeLocation) return profile.homeLocation;
  return "Aldgate";
};

const detectDateWindow = (text: string): ParsedIntent["dateWindow"] => {
  if (text.includes("weekend") || text.includes("saturday") || text.includes("sunday")) return "this-weekend";
  if (text.includes("after work") || text.includes("after-work")) return "after-work";
  if (text.includes("tonight") || text.includes("this evening")) return "tonight";
  return "any";
};

const detectAttendees = (text: string, profile?: UserProfile) => {
  const found = profileKeywords.filter((term) => text.includes(term));
  const expanded = [...found];
  if (text.includes("investor")) expanded.push("investors");
  if (text.includes("founder")) expanded.push("founders");
  if (text.includes("engineer")) expanded.push("engineers");
  if (text.includes("ai")) expanded.push("ai");
  if (text.includes("culture") || text.includes("cultural")) expanded.push("creatives");
  if (profile?.networkingGoals.length) expanded.push(...profile.networkingGoals.map((item) => item.toLowerCase()));
  return Array.from(new Set(expanded));
};

export function parseIntent(rawText: string, profile?: UserProfile): ParsedIntent {
  const text = rawText.toLowerCase().trim();
  const categories = detectCategories(text);
  const desiredAttendees = detectAttendees(text, profile);
  const budget = detectBudget(text, profile);
  const dateWindow = detectDateWindow(text);
  const startLocation = detectStartLocation(text, profile);
  const priorities = { ...defaultPriorityWeights };

  if (textIncludesAny(text, ["network", "investor", "founder", "meet people", "co-founder"])) {
    priorities.networking = 95;
    priorities.professionalRelevance = 88;
  }
  if (textIncludesAny(text, ["senior engineer", "technical", "ai", "robotics", "cyber"])) {
    priorities.learningOpportunity += 18;
    priorities.professionalRelevance += 16;
  }
  if (textIncludesAny(text, ["not too expensive", "cheap", "free", "budget", "under", "low cost"])) {
    priorities.lowCost = 92;
  }
  if (textIncludesAny(text, ["easy to get", "near", "low effort", "quick", "close", "travel"])) {
    priorities.lowEffort = 90;
  }
  if (textIncludesAny(text, ["cultural", "culture", "museum", "art", "music", "jazz"])) {
    priorities.culturalValue = 92;
    priorities.entertainment = 78;
  }
  if (textIncludesAny(text, ["social", "dating", "meet new people", "nightlife"])) {
    priorities.socialCompatibility = 82;
    priorities.entertainment = 80;
  }
  if (textIncludesAny(text, ["novel", "new", "different", "immersive"])) {
    priorities.novelty = 86;
  }

  const missingContext: string[] = [];
  if (!text) missingContext.push("goal");
  if (!categories.length && !desiredAttendees.length) missingContext.push("event type or desired attendees");
  if (!startLocation) missingContext.push("starting location");

  const travelToleranceMinutes = textIncludesAny(text, ["across london", "worth travelling", "do not mind travelling"])
    ? 75
    : priorities.lowEffort > 80
      ? 40
      : 60;

  return {
    rawText,
    goal:
      rawText ||
      "Find a worthwhile London event based on my interests, budget, travel effort, and city conditions.",
    categories,
    desiredAttendees,
    dateWindow,
    startLocation,
    budget,
    travelToleranceMinutes,
    priorities,
    compareMode: text.includes("compare") || text.includes("alternative") || text.includes("which event"),
    confidence: Math.min(96, 55 + categories.length * 10 + desiredAttendees.length * 5 + (budget ? 8 : 0)),
    missingContext
  };
}

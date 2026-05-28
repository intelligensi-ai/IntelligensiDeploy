import { LondonEvent, ParsedIntent } from "../types";
import { eventTextParts, scoreTextMatch } from "./utils";

export function estimateAttendeeRelevance(event: LondonEvent, intent: ParsedIntent) {
  const desired = intent.desiredAttendees.length
    ? intent.desiredAttendees
    : intent.categories.length
      ? intent.categories
      : ["professionals", "social"];
  const score = scoreTextMatch(eventTextParts(event), desired);
  const haystack = eventTextParts(event).join(" ").toLowerCase();
  const matchedProfiles = desired.filter((term) => haystack.includes(term.toLowerCase()));
  const explanation = matchedProfiles.length
    ? `Audience likely includes ${matchedProfiles.slice(0, 4).join(", ")}.`
    : "Audience profile is adjacent but not a direct match to the stated intent.";

  return {
    score,
    explanation,
    confidence: Math.min(95, 58 + matchedProfiles.length * 10 + event.attendeeProfile.length * 2),
    matchedProfiles
  };
}

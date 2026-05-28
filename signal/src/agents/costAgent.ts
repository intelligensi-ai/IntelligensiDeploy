import { LondonEvent, ParsedIntent, TravelEstimate } from "../types";
import { clamp } from "./utils";

export function estimateCost(event: LondonEvent, travel: TravelEstimate, intent: ParsedIntent) {
  const estimatedTravelCost = travel.travelMinutes > 65 ? 6.8 : travel.travelMinutes > 35 ? 4.9 : 3.4;
  const estimatedTotalCost = event.price + estimatedTravelCost + event.estimatedFoodDrink;
  const budgetFit = estimatedTotalCost <= intent.budget;
  const overBudgetPenalty = budgetFit ? 0 : (estimatedTotalCost - intent.budget) * 2.6;
  const preferenceBoost = intent.priorities.lowCost > 80 && event.price === 0 ? 12 : 0;
  const costScore = clamp(100 - (estimatedTotalCost / Math.max(intent.budget, 1)) * 36 - overBudgetPenalty + preferenceBoost);

  return {
    ticketPrice: event.price,
    estimatedTravelCost,
    estimatedFoodDrink: event.estimatedFoodDrink,
    estimatedTotalCost: Math.round(estimatedTotalCost * 10) / 10,
    budgetFit,
    costScore
  };
}

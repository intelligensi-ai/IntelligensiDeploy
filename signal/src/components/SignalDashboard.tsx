import { useMemo, useState } from "react";
import { parseIntent } from "../agents/intentAgent";
import { buildRecommendations } from "../agents/recommendationAgent";
import { mockCityConditions } from "../data/mockCityConditions";
import { AgentTrace, ChatMessage, EventRecommendation, ParsedIntent, UserProfile } from "../types";
import { AgentTracePanel } from "./AgentTracePanel";
import { ChatSidebar } from "./ChatSidebar";
import { EventCard } from "./EventCard";
import { EventComparison } from "./EventComparison";
import { LondonMap } from "./LondonMap";
import { ScoreBreakdown } from "./ScoreBreakdown";

const initialPrompt =
  "I want to meet AI investors and senior engineers tonight after work. I'm travelling from Aldgate and I want to keep the total cost under GBP30.";

const defaultProfile: UserProfile = {
  name: "Demo User",
  email: "demo@intelligensi.ai",
  phone: "",
  homeLocation: "Shoreditch",
  workLocation: "Aldgate",
  budgetPreference: 30,
  interests: ["AI", "startups", "culture"],
  networkingGoals: ["investors", "founders", "senior engineers"]
};

const makeMessage = (role: ChatMessage["role"], text: string): ChatMessage => ({
  id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  role,
  text,
  timestamp: new Date().toISOString()
});

function assistantSummary(recommendations: EventRecommendation[], intent: ParsedIntent) {
  const top = recommendations[0];
  if (!top) {
    return "I could not find a strong match in the current simulated London event set. Try broadening the category, budget, or time window.";
  }
  const ask =
    intent.missingContext.length > 0
      ? ` I assumed ${intent.startLocation}, GBP${intent.budget}, and ${intent.dateWindow}.`
      : "";
  return `${top.judgement}: ${top.event.name} is ranked first with Signal Score ${top.scores.overall}/100. It has ${top.scores.attendeeRelevance}/100 attendee relevance, ${top.travel.travelMinutes} minutes travel from ${intent.startLocation}, and an estimated total cost of GBP${top.cost.estimatedTotalCost}.${ask}`;
}

export function SignalDashboard() {
  const [profile, setProfile] = useState(defaultProfile);
  const [intent, setIntent] = useState(() => parseIntent(initialPrompt, defaultProfile));
  const initialRun = useMemo(() => buildRecommendations(parseIntent(initialPrompt, defaultProfile)), []);
  const [recommendations, setRecommendations] = useState(initialRun.recommendations);
  const [trace, setTrace] = useState(initialRun.trace);
  const [selectedId, setSelectedId] = useState(initialRun.recommendations[0]?.event.id);
  const [compareIds, setCompareIds] = useState(initialRun.recommendations.slice(0, 3).map((item) => item.event.id));
  const [messages, setMessages] = useState<ChatMessage[]>([
    makeMessage("assistant", "Signal is ready. The demo intent is already ranked using simulated London events and city conditions."),
    makeMessage("user", initialPrompt),
    makeMessage("assistant", assistantSummary(initialRun.recommendations, parseIntent(initialPrompt, defaultProfile)))
  ]);
  const [registrationNotice, setRegistrationNotice] = useState("");

  const selectedRecommendation =
    recommendations.find((recommendation) => recommendation.event.id === selectedId) || recommendations[0];

  const runSignal = (text: string, nextProfile = profile, appendUserMessage = true) => {
    const nextIntent = parseIntent(text, nextProfile);
    const nextRun = buildRecommendations(nextIntent);
    setIntent(nextIntent);
    setRecommendations(nextRun.recommendations);
    setTrace(nextRun.trace);
    setSelectedId(nextRun.recommendations[0]?.event.id);
    setCompareIds(nextRun.recommendations.slice(0, 3).map((item) => item.event.id));
    setRegistrationNotice("");
    setMessages((current) => [
      ...current,
      ...(appendUserMessage ? [makeMessage("user", text)] : []),
      makeMessage("assistant", assistantSummary(nextRun.recommendations, nextIntent))
    ]);
  };

  const updateProfile = (nextProfile: UserProfile) => {
    setProfile(nextProfile);
    const nextIntent = parseIntent(intent.rawText, nextProfile);
    const nextRun = buildRecommendations(nextIntent);
    setIntent(nextIntent);
    setRecommendations(nextRun.recommendations);
    setTrace(nextRun.trace);
    setSelectedId((current) =>
      nextRun.recommendations.some((recommendation) => recommendation.event.id === current)
        ? current
        : nextRun.recommendations[0]?.event.id
    );
  };

  const toggleCompare = (eventId: string) => {
    setCompareIds((current) =>
      current.includes(eventId)
        ? current.filter((id) => id !== eventId)
        : [...current, eventId].slice(-3)
    );
  };

  const handleRegister = (recommendation: EventRecommendation) => {
    const notice = `${recommendation.event.name} registration simulated for ${profile.name || "this profile"}. No personal data was submitted.`;
    setRegistrationNotice(notice);
    setMessages((current) => [...current, makeMessage("assistant", notice)]);
  };

  const visibleTrace: AgentTrace[] = selectedRecommendation
    ? [trace[0], trace[1], ...selectedRecommendation.trace].filter(
        (item): item is AgentTrace => Boolean(item)
      )
    : trace;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <div className="brand-mark">S</div>
          <div>
            <h1>Intelligensi.ai Signal</h1>
            <p>Speak your intent. Let the city answer.</p>
          </div>
        </div>
        <div className="header-stats">
          <span>London</span>
          <strong>{mockCityConditions.cityMood}</strong>
        </div>
      </header>

      <main className="dashboard-grid">
        <div className="left-stack">
          <LondonMap
            recommendations={recommendations}
            selectedId={selectedRecommendation?.event.id}
            startLocation={intent.startLocation}
            onSelect={setSelectedId}
          />

          <section className="recommendation-strip">
            <div className="section-head">
              <div>
                <p className="eyebrow">Ranked recommendations</p>
                <h2>Best options for this intent</h2>
              </div>
              <span className="simulated-badge">Decision-support estimate</span>
            </div>
            <div className="event-card-grid">
              {recommendations.slice(0, 6).map((recommendation) => (
                <EventCard
                  key={recommendation.event.id}
                  recommendation={recommendation}
                  selected={recommendation.event.id === selectedRecommendation?.event.id}
                  compareChecked={compareIds.includes(recommendation.event.id)}
                  onSelect={() => setSelectedId(recommendation.event.id)}
                  onCompareToggle={() => toggleCompare(recommendation.event.id)}
                  onRegister={() => handleRegister(recommendation)}
                />
              ))}
            </div>
            {registrationNotice && <div className="registration-notice">{registrationNotice}</div>}
          </section>

          <EventComparison recommendations={recommendations} compareIds={compareIds} />
        </div>

        <div className="right-stack">
          <ChatSidebar
            messages={messages}
            intent={intent}
            profile={profile}
            onSubmit={runSignal}
            onProfileChange={updateProfile}
          />
          <ScoreBreakdown recommendation={selectedRecommendation} />
          <AgentTracePanel trace={visibleTrace} />
        </div>
      </main>

      <footer className="app-footer">
        Signal Score is an estimated decision-support score based on simulated city, event, travel, and user intent data.
      </footer>
    </div>
  );
}

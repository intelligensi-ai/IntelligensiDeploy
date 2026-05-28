import { EventRecommendation } from "../types";

interface EventComparisonProps {
  recommendations: EventRecommendation[];
  compareIds: string[];
}

const metricRows = [
  { key: "scores.overall", label: "Overall Signal Score" },
  { key: "scores.attendeeRelevance", label: "Attendee relevance" },
  { key: "scores.travelEffort", label: "Lowest travel burden" },
  { key: "scores.networkingPotential", label: "Networking potential" },
  { key: "scores.costFit", label: "Best value" },
  { key: "scores.confidence", label: "Confidence" }
];

const getValue = (recommendation: EventRecommendation, key: string) => {
  const [objectKey, valueKey] = key.split(".") as ["scores", keyof EventRecommendation["scores"]];
  return recommendation[objectKey][valueKey];
};

export function EventComparison({ recommendations, compareIds }: EventComparisonProps) {
  const compared = recommendations.filter((item) => compareIds.includes(item.event.id)).slice(0, 3);
  const fallback = recommendations.slice(0, 3);
  const items = compared.length >= 2 ? compared : fallback;
  const best = items[0];

  if (!items.length) return null;

  return (
    <section className="comparison-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Comparison mode</p>
          <h2>Tonight's alternatives</h2>
        </div>
        <span className="simulated-badge">{items.length} events</span>
      </div>

      <p className="comparison-summary">
        Best recommendation: <strong>{best.event.name}</strong>. It has the strongest match to your intent,
        {best.travel.effort === "high" ? " but travel needs thought" : " manageable travel effort"}, and
        {best.scores.attendeeRelevance > 78 ? " high attendee relevance." : " a balanced trade-off profile."}
      </p>

      <div className="comparison-table">
        <div className="comparison-row header-row">
          <span>Metric</span>
          {items.map((item) => (
            <strong key={item.event.id}>{item.event.name}</strong>
          ))}
        </div>
        {metricRows.map((row) => {
          const rowBest = Math.max(...items.map((item) => getValue(item, row.key)));
          return (
            <div className="comparison-row" key={row.key}>
              <span>{row.label}</span>
              {items.map((item) => {
                const value = getValue(item, row.key);
                return (
                  <strong className={value === rowBest ? "winner" : ""} key={item.event.id}>
                    {value}
                  </strong>
                );
              })}
            </div>
          );
        })}
      </div>
    </section>
  );
}

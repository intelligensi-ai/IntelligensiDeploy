import type { CSSProperties } from "react";
import { eventCategoryColors, eventCategoryLabels } from "../data/mockEvents";
import { EventRecommendation } from "../types";

interface EventCardProps {
  recommendation: EventRecommendation;
  selected: boolean;
  compareChecked: boolean;
  onSelect: () => void;
  onCompareToggle: () => void;
  onRegister: () => void;
}

const withAlpha = (hex: string, alpha: string) => `${hex}${alpha}`;

const formatTime = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(iso));

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-bar">
      <span>{label}</span>
      <strong>{value}</strong>
      <div>
        <i style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export function EventCard({
  recommendation,
  selected,
  compareChecked,
  onSelect,
  onCompareToggle,
  onRegister
}: EventCardProps) {
  const { event, scores, travel, cost, sentiment } = recommendation;
  return (
    <article className={`event-card ${selected ? "is-selected" : ""}`} onClick={onSelect}>
      <div className="event-card-top">
        <span
          className="category-pill"
          style={
            {
              "--category-color": eventCategoryColors[event.category],
              "--category-bg": withAlpha(eventCategoryColors[event.category], "20"),
              "--category-border": withAlpha(eventCategoryColors[event.category], "77")
            } as CSSProperties & Record<string, string>
          }
        >
          {eventCategoryLabels[event.category]}
        </span>
        <span className={`effort-badge effort-${travel.effort}`}>{travel.effort} effort</span>
      </div>

      <div className="event-title-row">
        <h3>{event.name}</h3>
        <div className="score-badge">
          <strong>{scores.overall}</strong>
          <span>Signal</span>
        </div>
      </div>

      <p className="event-meta">
        {event.location.name} - {formatTime(event.startTime)} - GBP{cost.estimatedTotalCost}
      </p>
      <p className="event-copy">{event.description}</p>

      <div className="event-stats">
        <MetricBar label="Relevance" value={scores.intentRelevance} />
        <MetricBar label="Attendees" value={scores.attendeeRelevance} />
        <MetricBar label="Travel" value={scores.travelEffort} />
        <MetricBar label="Cost" value={scores.costFit} />
      </div>

      <div className="card-footer">
        <span>{sentiment.label} crowd</span>
        <span>{scores.confidence}% confidence</span>
      </div>

      <div className="event-actions" onClick={(eventClick) => eventClick.stopPropagation()}>
        <label className="compare-check">
          <input type="checkbox" checked={compareChecked} onChange={onCompareToggle} />
          Compare
        </label>
        <button type="button" className="ghost-button" onClick={onRegister}>
          Mock register
        </button>
      </div>
    </article>
  );
}

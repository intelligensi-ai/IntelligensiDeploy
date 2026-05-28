import {
  Bar,
  BarChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { EventRecommendation } from "../types";

interface ScoreBreakdownProps {
  recommendation?: EventRecommendation;
}

export function ScoreBreakdown({ recommendation }: ScoreBreakdownProps) {
  if (!recommendation) return null;

  const radarData = [
    { metric: "Intent", value: recommendation.scores.intentRelevance },
    { metric: "Attendee", value: recommendation.scores.attendeeRelevance },
    { metric: "Travel", value: recommendation.scores.travelEffort },
    { metric: "Cost", value: recommendation.scores.costFit },
    { metric: "Timing", value: recommendation.scores.timingSuitability },
    { metric: "Sentiment", value: recommendation.scores.sentiment }
  ];

  const barData = [
    { metric: "Weather", value: recommendation.scores.weather },
    { metric: "Crowd", value: recommendation.scores.crowdSuitability },
    { metric: "Network", value: recommendation.scores.networkingPotential },
    { metric: "Confidence", value: recommendation.scores.confidence }
  ];

  return (
    <section className="score-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Statistical dashboard</p>
          <h2>{recommendation.event.name}</h2>
        </div>
        <div className="hero-score">
          <strong>{recommendation.scores.overall}</strong>
          <span>{recommendation.judgement}</span>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <ResponsiveContainer width="100%" height={245}>
            <RadarChart data={radarData} outerRadius="70%">
              <PolarGrid stroke="rgba(148, 163, 184, 0.25)" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: "#cbd5e1", fontSize: 11 }} />
              <Radar dataKey="value" stroke="#67e8f9" fill="#67e8f9" fillOpacity={0.28} />
              <Tooltip
                contentStyle={{
                  background: "#07111f",
                  border: "1px solid rgba(103, 232, 249, 0.25)",
                  borderRadius: "8px",
                  color: "#e2e8f0"
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card compact-chart">
          <ResponsiveContainer width="100%" height={245}>
            <BarChart data={barData} layout="vertical" margin={{ left: 16, right: 18 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis dataKey="metric" type="category" width={78} tick={{ fill: "#cbd5e1", fontSize: 12 }} />
              <Tooltip
                cursor={{ fill: "rgba(103, 232, 249, 0.06)" }}
                contentStyle={{
                  background: "#07111f",
                  border: "1px solid rgba(103, 232, 249, 0.25)",
                  borderRadius: "8px",
                  color: "#e2e8f0"
                }}
              />
              <Bar dataKey="value" fill="#a7f3d0" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="worth-panel">
        <h3>Worth attending?</h3>
        <p>{recommendation.explanation}</p>
        <div className="tradeoffs">
          {recommendation.tradeOffs.map((tradeOff) => (
            <span key={tradeOff}>{tradeOff}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

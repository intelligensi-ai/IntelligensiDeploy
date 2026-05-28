import type { CSSProperties } from "react";
import { eventCategoryColors, eventCategoryLabels } from "../data/mockEvents";
import { knownLocations } from "../data/mockCityConditions";
import { EventRecommendation, LondonEvent } from "../types";
import { EffortRings } from "./EffortRings";

interface LondonMapProps {
  recommendations: EventRecommendation[];
  selectedId?: string;
  startLocation: string;
  onSelect: (eventId: string) => void;
}

const bounds = {
  minLng: -0.215,
  maxLng: 0.02,
  minLat: 51.455,
  maxLat: 51.55
};

const categoryShort: Record<LondonEvent["category"], string> = {
  "ai-tech": "AI",
  business: "B",
  culture: "C",
  nightlife: "N",
  sports: "S",
  gaming: "G",
  community: "P",
  education: "E"
};

const boroughShapes = [
  "130,144 300,92 420,155 380,270 205,278",
  "388,92 578,82 635,180 548,286 392,264",
  "610,116 836,128 900,244 784,330 628,266",
  "178,316 360,302 426,430 274,536 126,448",
  "390,322 590,308 648,454 512,552 368,474",
  "635,330 835,344 898,470 760,560 622,462",
  "288,108 414,92 368,28 218,54",
  "520,78 748,88 694,28 560,18"
];

const thamesPath =
  "M42 366 C142 322 210 342 294 380 C392 424 470 430 552 382 C644 328 728 310 842 346 C906 366 944 356 986 330";

function project(lat: number, lng: number) {
  const x = ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * 900 + 50;
  const y = (1 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * 520 + 50;
  return { x, y };
}

export function LondonMap({ recommendations, selectedId, startLocation, onSelect }: LondonMapProps) {
  const selected = recommendations.find((item) => item.event.id === selectedId) || recommendations[0];
  const start = knownLocations.find((location) => location.name === startLocation) || knownLocations[0];
  const origin = project(start.lat, start.lng);

  return (
    <section className="map-panel" aria-label="Simulated London event map">
      <div className="map-toolbar">
        <div>
          <p className="eyebrow">Live London signal</p>
          <h2>Event map</h2>
        </div>
        <div className="map-legend" aria-label="Event category legend">
          {Object.entries(eventCategoryLabels).map(([category, label]) => (
            <span
              key={category}
              style={
                {
                  "--legend-color": eventCategoryColors[category as LondonEvent["category"]]
                } as CSSProperties & Record<string, string>
              }
            >
              {label.split(" / ")[0]}
            </span>
          ))}
        </div>
      </div>

      <div className="map-canvas">
        <svg viewBox="0 0 1000 640" role="img" aria-label="Stylised London map with event pins and effort rings">
          <defs>
            <filter id="pinGlow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <linearGradient id="riverGradient" x1="0%" x2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.24" />
              <stop offset="45%" stopColor="#67e8f9" stopOpacity="0.38" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.24" />
            </linearGradient>
          </defs>

          <rect x="0" y="0" width="1000" height="640" rx="28" className="map-bg" />
          {boroughShapes.map((points, index) => (
            <polygon key={points} points={points} className={`borough borough-${index % 3}`} />
          ))}

          <path d={thamesPath} className="thames thames-wide" />
          <path d={thamesPath} className="thames thames-core" />

          <EffortRings x={origin.x} y={origin.y} />

          <g className="transport-lines">
            <path d="M116 212 C280 184 410 205 564 176 C702 150 820 176 930 128" />
            <path d="M164 482 C300 382 424 330 552 258 C690 180 786 138 900 100" />
            <path d="M242 72 C350 194 452 300 592 412 C688 488 776 530 888 552" />
          </g>

          <g className="origin-marker" transform={`translate(${origin.x} ${origin.y})`}>
            <circle r="11" />
            <circle r="4" />
            <text x="17" y="-12">{start.name}</text>
          </g>

          {recommendations.map((recommendation, index) => {
            const { event } = recommendation;
            const position = project(event.location.lat, event.location.lng);
            const isSelected = event.id === selectedId;
            const radius = isSelected ? 23 : 17;
            return (
              <g
                key={event.id}
                className={`event-pin ${isSelected ? "selected" : ""}`}
                transform={`translate(${position.x} ${position.y})`}
                onClick={() => onSelect(event.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(eventKey) => {
                  if (eventKey.key === "Enter") onSelect(event.id);
                }}
                aria-label={`${event.name}, Signal Score ${recommendation.scores.overall}`}
              >
                <circle
                  r={radius}
                  fill={eventCategoryColors[event.category]}
                  opacity={0.75 + Math.min(0.25, recommendation.scores.overall / 500)}
                  filter="url(#pinGlow)"
                />
                <circle r={radius - 5} className="pin-inner" />
                <text y="4">{categoryShort[event.category]}</text>
                <title>
                  {index + 1}. {event.name} - {recommendation.scores.overall}/100
                </title>
              </g>
            );
          })}
        </svg>

        {selected && (
          <aside className="map-popover">
            <div className="score-tile">{selected.scores.overall}</div>
            <div>
              <p className="eyebrow">{eventCategoryLabels[selected.event.category]}</p>
              <h3>{selected.event.name}</h3>
              <p>{selected.event.location.name} - {selected.travel.travelMinutes} min - {selected.judgement}</p>
            </div>
          </aside>
        )}
      </div>
    </section>
  );
}

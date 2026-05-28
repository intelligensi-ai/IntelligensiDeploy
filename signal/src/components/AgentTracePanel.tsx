import { AgentTrace } from "../types";

interface AgentTracePanelProps {
  trace: AgentTrace[];
}

export function AgentTracePanel({ trace }: AgentTracePanelProps) {
  return (
    <section className="trace-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Signal trace</p>
          <h2>Agent reasoning</h2>
        </div>
        <span className="simulated-badge">Simulated data</span>
      </div>
      <div className="trace-list">
        {trace.map((item, index) => (
          <article key={`${item.agent}-${index}`} className={`trace-item trace-${item.status}`}>
            <div className="trace-dot" />
            <div>
              <h3>{item.agent}</h3>
              <p>{item.summary}</p>
              {item.details && <span>{item.details}</span>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

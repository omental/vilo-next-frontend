import { Card } from "../ui/Card";

function toneClass(tone) {
  return `tone-${tone}`;
}

export function MetricsCard({ title, subtitle, headline, chart, rows }) {
  return (
    <Card title={title} subtitle={subtitle} className="metric-card">
      <div className="metric-headline">{headline}</div>
      <div className="metric-chart">{chart}</div>
      <div className="metric-list">
        {rows.map((row) => (
          <div className="metric-row" key={row.label}>
            <div className={`metric-icon ${toneClass(row.tone)}`} />
            <div>
              <strong>{row.label}</strong>
              <small>{row.sublabel}</small>
            </div>
            <span className="metric-value">{row.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

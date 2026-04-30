import { Card } from "../ui/Card";

function changeTone(change) {
  return change.startsWith("-") ? "negative" : "positive";
}

export function ListCard({ title, subtitle, items, compact = false }) {
  return (
    <Card title={title} subtitle={subtitle} className={compact ? "list-card compact" : "list-card"}>
      <ul className="stats-list">
        {items.map((item) => (
          <li className="stats-row" key={item.label}>
            <span className={`metric-icon tone-${item.tone}`} />
            <div className="stats-row-copy">
              <strong>{item.label}</strong>
              {item.helper ? <small>{item.helper}</small> : null}
            </div>
            <div className="stats-row-values">
              <span>{item.value}</span>
              <em className={changeTone(item.change)}>{item.change}</em>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

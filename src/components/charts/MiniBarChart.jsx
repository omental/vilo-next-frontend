export function MiniBarChart({ values }) {
  const max = Math.max(...values, 1);

  return (
    <div className="mini-bars" aria-label="Bar chart">
      {values.map((value, index) => (
        <span
          key={`${value}-${index}`}
          className={`mini-bar${index % 3 === 0 ? " is-muted" : ""}`}
          style={{ height: `${(value / max) * 100}%` }}
        />
      ))}
    </div>
  );
}

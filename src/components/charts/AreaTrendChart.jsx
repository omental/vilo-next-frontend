function buildPath(data, width, height, padding) {
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = padding + (index / (data.length - 1)) * innerWidth;
    const y = padding + innerHeight - ((value - min) / range) * innerHeight;
    return [x, y];
  });

  const line = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
  const area = `${line} L ${points.at(-1)[0]} ${height - padding} L ${points[0][0]} ${height - padding} Z`;

  return { points, line, area };
}

export function AreaTrendChart({ data, labels }) {
  const width = 720;
  const height = 280;
  const padding = 28;
  const { points, line, area } = buildPath(data, width, height, padding);

  return (
    <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Revenue trend chart">
      <defs>
        <linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(115,103,240,0.34)" />
          <stop offset="100%" stopColor="rgba(115,103,240,0.02)" />
        </linearGradient>
      </defs>

      {[0, 1, 2, 3].map((step) => {
        const y = padding + ((height - padding * 2) / 3) * step;
        return <line key={step} x1={padding} y1={y} x2={width - padding} y2={y} className="chart-gridline" />;
      })}

      <path d={area} fill="url(#trend-fill)" />
      <path d={line} fill="none" stroke="var(--color-primary)" strokeWidth="3" strokeLinecap="round" />

      {points.map(([x, y], index) => (
        <g key={`${x}-${y}`}>
          <circle cx={x} cy={y} r="4.5" className="chart-dot" />
          <text x={x} y={height - 8} textAnchor="middle" className="chart-label">
            {labels[index]}
          </text>
        </g>
      ))}
    </svg>
  );
}

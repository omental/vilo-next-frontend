const chartValues = [190, 105, 210, 80, 175, 240, 260];

const summaryItems = [
  { label: "Monthly expenses", value: "$21,450", tone: "is-green", icon: WalletIcon },
  { label: "Net Profit", value: "$21,450", tone: "is-orange", icon: FlagIcon },
  { label: "Trust Account", value: "$21,450", tone: "is-violet", icon: CheckCircleIcon }
];

const axisLabels = [400, 300, 200, 100, 0];

export function FinancialOverview() {
  const chartPoints = buildChartPoints(chartValues);
  const linePath = buildSmoothPath(chartPoints);
  const areaPath = `${linePath} L 100 100 L 0 100 Z`;

  return (
    <section className="dashboard-card dashboard-card--financial" aria-labelledby="financial-overview-title">
      <div className="dashboard-card__header">
        <h2 id="financial-overview-title">Financial Overview</h2>
      </div>

      <div className="financial-card__body">
        <div className="financial-copy">
          <h3>Monthly Earnings - March 2026</h3>
          <p>Total Revenue: $230,000</p>
        </div>

        <div className="financial-chart-wrap">
          <div className="financial-chart">
            <div className="financial-chart__axis">
              {axisLabels.map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>

            <div className="financial-chart__container">
              <div className="financial-chart__plot">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                  <defs>
                    <linearGradient id="financial-area-fill" x1="0%" x2="0%" y1="0%" y2="100%">
                      <stop offset="0%" stopColor="rgba(67, 44, 241, 0.34)" />
                      <stop offset="100%" stopColor="rgba(67, 44, 241, 0.04)" />
                    </linearGradient>
                  </defs>

                  <g className="financial-chart__grid">
                    <line x1="0" y1="0" x2="100" y2="0" />
                    <line x1="0" y1="25" x2="100" y2="25" />
                    <line x1="0" y1="50" x2="100" y2="50" />
                    <line x1="0" y1="75" x2="100" y2="75" />
                    <line x1="0" y1="100" x2="100" y2="100" />
                  </g>

                  <path d={areaPath} className="financial-chart__area" />
                  <path d={linePath} className="financial-chart__line" />

                  {chartPoints.slice(1, -1).map((point, index) => (
                    <circle
                      key={index}
                      className="financial-chart__point"
                      cx={point.x}
                      cy={point.y}
                      r="1.6"
                    />
                  ))}
                </svg>
              </div>
            </div>
          </div>
        </div>

        <div className="financial-summary">
          {summaryItems.map((item) => {
            const Icon = item.icon;

            return (
              <article key={item.label} className="financial-summary__item">
                <span className={`financial-summary__icon ${item.tone}`}>
                  <Icon />
                </span>
                <div className="financial-summary__copy">
                  <p>{item.label}:</p>
                  <strong>{item.value}</strong>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function buildChartPoints(values) {
  const maxValue = 400;
  const usableHeight = 88;
  const topPadding = 6;

  return values.map((value, index) => ({
    x: (index / (values.length - 1)) * 100,
    y: topPadding + (1 - value / maxValue) * usableHeight
  }));
}

function buildSmoothPath(points) {
  if (!points.length) {
    return "";
  }

  let path = `M ${points[0].x} ${points[0].y}`;

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const controlX = (current.x + next.x) / 2;

    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }

  return path;
}

function IconBase({ children }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

function WalletIcon() {
  return (
    <IconBase>
      <path d="M3 8.5A2.5 2.5 0 0 1 5.5 6H18a2 2 0 0 1 2 2v8.5a2.5 2.5 0 0 1-2.5 2.5h-12A2.5 2.5 0 0 1 3 16.5v-8Z" />
      <path d="M16.5 13h3.5" />
      <path d="M6 6V4.8A1.8 1.8 0 0 1 7.8 3h7.7" />
      <circle cx="17" cy="13" r="0.8" fill="currentColor" stroke="none" />
    </IconBase>
  );
}

function FlagIcon() {
  return (
    <IconBase>
      <path d="M5 20V4" />
      <path d="M5 5h10l-1.8 3.2L15 11H5" />
    </IconBase>
  );
}

function CheckCircleIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.1 2.1 2.3 4.9-5.1" />
    </IconBase>
  );
}

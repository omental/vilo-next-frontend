const billingBars = [
  { label: "Paid", value: 210, tone: "is-paid" },
  { label: "Unpaid", value: 130, tone: "is-unpaid" },
  { label: "Draft", value: 360, tone: "is-draft" },
  { label: "Overdue", value: 280, tone: "is-overdue" }
];

const billingAxisLabels = [400, 300, 200, 100, 0];

export function BillingOverview() {
  return (
    <section className="dashboard-card dashboard-card--billing" aria-labelledby="billing-overview-title">
      <div className="dashboard-card__header">
        <h2 id="billing-overview-title">Billing Overview</h2>
      </div>

      <div className="billing-card__body">
        <div className="billing-chart">
          <div className="billing-chart__axis">
            {billingAxisLabels.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>

          <div className="billing-chart__plot">
            <div className="billing-chart__grid">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>

            <div className="billing-chart__bars">
              {billingBars.map((bar) => (
                <div key={bar.label} className="billing-bar">
                  <span
                    className={`billing-bar__fill ${bar.tone}`}
                    style={{ height: `${(bar.value / 400) * 100}%` }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="billing-summary">
          {billingBars.map((bar) => (
            <article key={bar.label} className="billing-summary__card">
              <p>
                <span className={`billing-summary__dot ${bar.tone}`} />
                {bar.label}:
              </p>
              <strong>{bar.value}</strong>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

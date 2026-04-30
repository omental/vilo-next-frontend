export function AnalyticsHeroCard({ title, subtitle, sectionTitle, stats }) {
  return (
    <article className="hero-card">
      <div className="hero-copy">
        <div>
          <p className="hero-eyebrow">{subtitle}</p>
          <h3>{title}</h3>
        </div>

        <div>
          <h4>{sectionTitle}</h4>
          <div className="hero-stats">
            {stats.map((stat) => (
              <div key={stat.label} className="hero-stat">
                <span>{stat.value}</span>
                <small>{stat.label}</small>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="hero-visual" aria-hidden="true">
        <div className="hero-orbit hero-orbit-a" />
        <div className="hero-orbit hero-orbit-b" />
        <div className="hero-device">
          <div className="hero-device-top" />
          <div className="hero-device-bars">
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
      </div>
    </article>
  );
}

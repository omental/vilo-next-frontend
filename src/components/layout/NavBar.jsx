function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="m16 16 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function NavBar({ title, subtitle, searchPlaceholder, actions }) {
  return (
    <header className="navbar">
      <div className="navbar-leading">
        <button className="icon-button mobile-only" type="button" aria-label="Open menu">
          <MenuIcon />
        </button>
        <div className="navbar-title">
          <p>{subtitle}</p>
          <h2>{title}</h2>
        </div>
      </div>

      <div className="navbar-search">
        <SearchIcon />
        <input type="search" placeholder={searchPlaceholder} aria-label={searchPlaceholder} />
      </div>

      <div className="navbar-actions">
        {actions.map((action) => (
          <button className="icon-chip" type="button" key={action.label}>
            <span>{action.label}</span>
            {action.badge ? <span className="pill pill-danger">{action.badge}</span> : null}
          </button>
        ))}
      </div>
    </header>
  );
}

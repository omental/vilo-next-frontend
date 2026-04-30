const menuItems = [
  { label: "Dashboard", icon: HomeIcon, active: true },
  { label: "Files", icon: FileTextIcon },
  { label: "Clients", icon: UsersIcon },
  { label: "Calendar", icon: CalendarIcon },
  { label: "Tasks", icon: ClipboardListIcon },
  { label: "Documents", icon: FileStackIcon },
  { label: "Precedents", icon: ListIcon },
  { label: "Messages", icon: MessageCircleIcon },
  { label: "Billing", icon: DollarSignIcon, expandable: true },
  { label: "Finance", icon: LinkIcon, expandable: true },
  { label: "Team", icon: NetworkIcon },
  { label: "Reports", icon: ClipboardIcon },
  { label: "Settings", icon: SettingsIcon }
];

const quickMetrics = [
  { label: "Open Cases", value: 53, colorClass: "is-indigo" },
  { label: "Total Billed Hours", value: 53, colorClass: "is-red" },
  { label: "Unpaid Invoices", value: 53, colorClass: "is-green" }
];

const recentActivity = [
  { title: "Lorem Ipsum", timestamp: "Jul 13, 2:29 AM" },
  { title: "Lorem Ipsum", timestamp: "Jul 13, 2:29 AM" },
  { title: "Lorem Ipsum", timestamp: "Jul 13, 2:29 AM" }
];

const quickActions = [
  { label: "Create File", icon: PlusSquareIcon },
  { label: "Add Client", icon: UserPlusIcon },
  { label: "Upload Document", icon: UploadIcon }
];

export function Sidebar({ isMobileOpen = false }) {
  return (
    <aside className={`sidebar vilo-sidebar${isMobileOpen ? " is-mobile-open" : ""}`}>
      <div className="vilo-sidebar__inner">
        <div className="vilo-sidebar__brand">
          <BrandMark />
          <span>VILO</span>
        </div>

        <div className="vilo-sidebar__block">
          <p className="vilo-sidebar__eyebrow">APPS &amp; PAGES</p>

          <nav className="vilo-sidebar__nav" aria-label="Sidebar navigation">
            {menuItems.map((item) => {
              const Icon = item.icon;

              return (
                <button
                  key={item.label}
                  type="button"
                  className={`vilo-sidebar__item${item.active ? " is-active" : ""}`}
                >
                  <span className="vilo-sidebar__item-main">
                    <span className="vilo-sidebar__icon-wrap">
                      <Icon />
                    </span>
                    <span>{item.label}</span>
                  </span>
                  {item.expandable ? <ChevronDownIcon /> : null}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="vilo-sidebar__divider" />

        <button type="button" className="vilo-sidebar__new-row">
          <span className="vilo-sidebar__item-main">
            <span className="vilo-sidebar__icon-wrap">
              <PlusIcon />
            </span>
            <span>New</span>
          </span>
          <ChevronDownIcon />
        </button>

        <div className="vilo-sidebar__divider" />

        <section className="vilo-sidebar__block">
          <p className="vilo-sidebar__eyebrow">QUICK METRICS</p>

          <div className="vilo-metrics">
            <ProgressRing value={75} />
            <ul className="vilo-metrics__legend" aria-label="Quick metrics">
              {quickMetrics.map((metric) => (
                <li key={metric.label}>
                  <span className={`vilo-metrics__dot ${metric.colorClass}`} />
                  <span>
                    {metric.label}: {metric.value}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="vilo-sidebar__block">
          <p className="vilo-sidebar__eyebrow">RECENT ACTIVITY</p>

          <div className="vilo-activity">
            {recentActivity.map((item, index) => (
              <button key={`${item.title}-${index}`} type="button" className="vilo-activity__item">
                <span className="vilo-activity__status">
                  <CheckCircleIcon />
                </span>
                <span className="vilo-activity__copy">
                  <span className="vilo-activity__title">{item.title}</span>
                  <span className="vilo-activity__time">{item.timestamp}</span>
                </span>
                <ChevronRightIcon />
              </button>
            ))}
          </div>
        </section>

        <section className="vilo-sidebar__block">
          <p className="vilo-sidebar__eyebrow">QUICK ACTIONS</p>

          <div className="vilo-actions">
            {quickActions.map((action) => {
              const Icon = action.icon;

              return (
                <button key={action.label} type="button" className="vilo-actions__button">
                  <Icon />
                  <span>{action.label}</span>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </aside>
  );
}

function ProgressRing({ value }) {
  const radius = 27;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (value / 100) * circumference;

  return (
    <div className="vilo-ring" aria-label={`Completion ${value}%`}>
      <svg viewBox="0 0 72 72" aria-hidden="true">
        <circle cx="36" cy="36" r="27" className="vilo-ring__track" />
        <circle
          cx="36"
          cy="36"
          r="27"
          className="vilo-ring__segment is-indigo"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
        <circle
          cx="36"
          cy="36"
          r="21"
          className="vilo-ring__segment is-green"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - 0.68 * circumference}
        />
        <circle
          cx="36"
          cy="36"
          r="33"
          className="vilo-ring__segment is-cyan"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - 0.56 * circumference}
        />
      </svg>
      <div className="vilo-ring__center">
        <strong>{value}%</strong>
      </div>
    </div>
  );
}

function BrandMark() {
  return (
    <svg viewBox="0 0 52 40" aria-hidden="true" className="vilo-brand-mark">
      <defs>
        <linearGradient id="vilo-brand-a" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#8ef0f8" />
          <stop offset="100%" stopColor="#5bc5f9" />
        </linearGradient>
        <linearGradient id="vilo-brand-b" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#574bff" />
          <stop offset="100%" stopColor="#2d16dd" />
        </linearGradient>
      </defs>
      <path
        d="M6.5 17.8c-3-3-3-7.8 0-10.8l2-2c3-3 7.8-3 10.8 0l8.6 8.5-6.4 6.5c-3 3-7.8 3-10.8 0l-4.2-4.2Z"
        fill="url(#vilo-brand-a)"
      />
      <path
        d="M28 13.5 36.6 5c3-3 7.8-3 10.8 0l2 2c3 3 3 7.8 0 10.8L32.2 35c-3 3-7.8 3-10.8 0l-2-2c-3-3-3-7.8 0-10.8l8.6-8.7Z"
        fill="url(#vilo-brand-b)"
      />
    </svg>
  );
}

function IconBase({ children, className = "" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

function HomeIcon() {
  return (
    <IconBase>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5V20h13V9.5" />
    </IconBase>
  );
}

function FileTextIcon() {
  return (
    <IconBase>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6" />
      <path d="M9 17h6" />
    </IconBase>
  );
}

function UsersIcon() {
  return (
    <IconBase>
      <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
      <circle cx="9.5" cy="7" r="3" />
      <path d="M21 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16.5 4.1a3 3 0 0 1 0 5.8" />
    </IconBase>
  );
}

function CalendarIcon() {
  return (
    <IconBase>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M16 3v4" />
      <path d="M8 3v4" />
      <path d="M3 10h18" />
      <path d="M8 14h0.01" />
      <path d="M12 14h0.01" />
    </IconBase>
  );
}

function ClipboardListIcon() {
  return (
    <IconBase>
      <rect x="5" y="4" width="14" height="17" rx="3" />
      <path d="M9 4.5h6" />
      <path d="M9 10h6" />
      <path d="M9 14h6" />
      <path d="M9 18h4" />
    </IconBase>
  );
}

function FileStackIcon() {
  return (
    <IconBase>
      <path d="M14 2H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v5h5" />
      <path d="M4 8H3a1 1 0 0 0-1 1v10a2 2 0 0 0 2 2h9a1 1 0 0 0 1-1v-1" />
    </IconBase>
  );
}

function ListIcon() {
  return (
    <IconBase>
      <path d="M9 6h11" />
      <path d="M9 12h11" />
      <path d="M9 18h11" />
      <path d="M4 6h0.01" />
      <path d="M4 12h0.01" />
      <path d="M4 18h0.01" />
    </IconBase>
  );
}

function MessageCircleIcon() {
  return (
    <IconBase>
      <path d="M21 11.5a8.5 8.5 0 1 1-4-7.2" />
      <path d="m9 12 2 2 4-4" />
    </IconBase>
  );
}

function DollarSignIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v10" />
      <path d="M15 9.5c0-1.1-1.3-2-3-2s-3 0.9-3 2 1 1.8 3 2 3 0.9 3 2-1.3 2-3 2-3-0.9-3-2" />
    </IconBase>
  );
}

function LinkIcon() {
  return (
    <IconBase>
      <path d="M10.5 13.5 13.5 10.5" />
      <path d="M7 17a4 4 0 0 1 0-5.7l2.8-2.8a4 4 0 0 1 5.7 0" />
      <path d="M17 7a4 4 0 0 1 0 5.7l-2.8 2.8a4 4 0 0 1-5.7 0" />
    </IconBase>
  );
}

function NetworkIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="5" r="2.5" />
      <circle cx="5" cy="17" r="2.5" />
      <circle cx="19" cy="17" r="2.5" />
      <path d="M12 7.5v4.5" />
      <path d="M7.2 15.5 10 13" />
      <path d="M16.8 15.5 14 13" />
      <path d="M8 19.5h8" />
    </IconBase>
  );
}

function ClipboardIcon() {
  return (
    <IconBase>
      <rect x="6" y="4" width="12" height="17" rx="3" />
      <path d="M9 4h6v3H9z" />
    </IconBase>
  );
}

function SettingsIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 0.34 1.87l0.06 0.06a2 2 0 1 1-2.83 2.83l-0.06-0.06a1.7 1.7 0 0 0-1.87-0.34 1.7 1.7 0 0 0-1 1.54V21a2 2 0 1 1-4 0v-0.09a1.7 1.7 0 0 0-1-1.54 1.7 1.7 0 0 0-1.87 0.34l-0.06 0.06a2 2 0 1 1-2.83-2.83l0.06-0.06a1.7 1.7 0 0 0 0.34-1.87 1.7 1.7 0 0 0-1.54-1H3a2 2 0 1 1 0-4h0.09a1.7 1.7 0 0 0 1.54-1 1.7 1.7 0 0 0-0.34-1.87l-0.06-0.06a2 2 0 1 1 2.83-2.83l0.06 0.06a1.7 1.7 0 0 0 1.87 0.34H9a1.7 1.7 0 0 0 1-1.54V3a2 2 0 1 1 4 0v0.09a1.7 1.7 0 0 0 1 1.54 1.7 1.7 0 0 0 1.87-0.34l0.06-0.06a2 2 0 1 1 2.83 2.83l-0.06 0.06a1.7 1.7 0 0 0-0.34 1.87V9c0 0.67 0.39 1.28 1 1.54H21a2 2 0 1 1 0 4h-0.09a1.7 1.7 0 0 0-1.51 0.46Z" />
    </IconBase>
  );
}

function PlusIcon() {
  return (
    <IconBase>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </IconBase>
  );
}

function CheckCircleIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12 2.2 2.2L15.8 9" />
    </IconBase>
  );
}

function ChevronDownIcon() {
  return (
    <IconBase className="vilo-sidebar__chevron">
      <path d="m6 9 6 6 6-6" />
    </IconBase>
  );
}

function ChevronRightIcon() {
  return (
    <IconBase className="vilo-sidebar__activity-chevron">
      <path d="m9 6 6 6-6 6" />
    </IconBase>
  );
}

function PlusSquareIcon() {
  return (
    <IconBase>
      <rect x="3" y="3" width="18" height="18" rx="4" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </IconBase>
  );
}

function UserPlusIcon() {
  return (
    <IconBase>
      <circle cx="10" cy="8" r="3" />
      <path d="M4 19a6 6 0 0 1 12 0" />
      <path d="M19 8v6" />
      <path d="M16 11h6" />
    </IconBase>
  );
}

function UploadIcon() {
  return (
    <IconBase>
      <path d="M12 16V6" />
      <path d="m8 10 4-4 4 4" />
      <path d="M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5" />
    </IconBase>
  );
}

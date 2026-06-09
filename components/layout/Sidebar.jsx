"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";
import { motionEase, createHoverLift, createItemVariants } from "../motion";

const menuItems = [
  { label: "Dashboard", icon: HomeIcon, href: "/dashboard" },
  { label: "Files", icon: FileTextIcon, href: "/dashboard/cases" },
  { label: "Clients", icon: UsersIcon, href: "/dashboard/clients" },
  { label: "Calendar", icon: CalendarIcon, href: "/dashboard/calendar" },
  { label: "Tasks", icon: ClipboardListIcon, href: "/dashboard/tasks" },
  { label: "Documents", icon: FileStackIcon, href: "/dashboard/documents" },
  { label: "Precedents", icon: ListIcon, href: "/dashboard/precedents" },
  { label: "Messages", icon: MessageCircleIcon, href: "/dashboard/messages" },
  { label: "Billing", icon: DollarSignIcon, href: "/dashboard/billing", expandable: true },
  { label: "Finance", icon: LinkIcon, href: "/dashboard/finance", expandable: true },
  { label: "Team", icon: NetworkIcon, href: "/dashboard/team" },
  { label: "Reports", icon: ClipboardIcon, href: "/dashboard/reports" },
  { label: "Settings", icon: SettingsIcon, href: "/dashboard/settings" }
];

const quickMetrics = [
  { label: "Open Cases", value: 53, colorClass: "is-indigo" },
  { label: "Total Billed Hours", value: 53, colorClass: "is-red" },
  { label: "Unpaid Invoices", value: 53, colorClass: "is-green" }
];

const createActions = [
  { label: "New Case", href: "/dashboard/cases?create=1", icon: PlusSquareIcon },
  { label: "New Client", href: "/dashboard/clients?create=1", icon: UserPlusIcon },
  { label: "Upload Document", href: "/dashboard/documents?upload=1", icon: UploadIcon },
  { label: "New Task", href: "/dashboard/tasks?create=1", icon: ClipboardListIcon },
  { label: "New Event", href: "/dashboard/calendar?create=1", icon: CalendarIcon }
];

export function Sidebar({ isMobileOpen = false, onClose = () => {} }) {
  const router = useRouter();
  const pathname = usePathname();
  const [createOpen, setCreateOpen] = useState(false);
  const [activityItems, setActivityItems] = useState([]);
  const shouldReduceMotion = useReducedMotion();
  const itemVariants = createItemVariants(shouldReduceMotion, "y", 10);
  const hoverLift = createHoverLift(shouldReduceMotion, -2, 1.01);
  const sidebarVariants = shouldReduceMotion
    ? {
        hidden: { opacity: 1 },
        show: { opacity: 1 }
      }
    : {
        hidden: { opacity: 0 },
        show: {
          opacity: 1,
          transition: {
            duration: 0.3,
            ease: motionEase,
            when: "beforeChildren",
            staggerChildren: 0.04
          }
        }
      };
  const activeHover = shouldReduceMotion
    ? {}
    : {
        scale: 1.015,
        boxShadow: "0 10px 24px rgba(67, 44, 241, 0.35)",
        transition: { duration: 0.18 }
      };

  useEffect(() => {
    let cancelled = false;

    async function loadActivity() {
      try {
        const data = await apiRequest("/api/v1/notifications?page=1&page_size=5");
        if (cancelled) return;
        setActivityItems((data.items || []).map((item) => ({
          id: item.id,
          title: item.title || "Activity",
          timestamp: formatShortTimestamp(item.created_at),
          module: prettyType(item.type),
          href: resolveNotificationHref(item),
        })));
      } catch {
        if (!cancelled) setActivityItems([]);
      }
    }

    loadActivity();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <motion.aside
      className={`sidebar vilo-sidebar${isMobileOpen ? " is-mobile-open" : ""}`}
      initial="hidden"
      animate="show"
      variants={sidebarVariants}
    >
      <div className="vilo-sidebar__inner">
        <div className="vilo-sidebar__brand">
          <Image src="/assets/vilo-logo.png" alt="VILO" width={120} height={36} className="vilo-brand-logo" priority />
        </div>

        <div className="vilo-sidebar__block">
          <p className="vilo-sidebar__eyebrow">APPS &amp; PAGES</p>

          <nav className="vilo-sidebar__nav" aria-label="Sidebar navigation">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);

              return (
                <motion.button
                  key={item.label}
                  type="button"
                  className={`vilo-sidebar__item${isActive ? " is-active" : ""}`}
                  variants={itemVariants}
                  whileHover={isActive ? activeHover : hoverLift}
                  onClick={() => {
                    router.push(item.href);
                    onClose();
                  }}
                >
                  <span className="vilo-sidebar__item-main">
                    <span className="vilo-sidebar__icon-wrap">
                      <Icon />
                    </span>
                    <span>{item.label}</span>
                  </span>
                  {item.expandable ? <ChevronDownIcon /> : null}
                </motion.button>
              );
            })}
          </nav>
        </div>

        <div className="vilo-sidebar__divider" />

        <motion.button
          type="button"
          className={`vilo-sidebar__new-row${createOpen ? " is-open" : ""}`}
          variants={itemVariants}
          whileHover={hoverLift}
          aria-expanded={createOpen}
          aria-controls="vilo-create-menu"
          onClick={() => setCreateOpen((prev) => !prev)}
        >
          <span className="vilo-sidebar__item-main">
            <span className="vilo-sidebar__icon-wrap">
              <PlusIcon />
            </span>
            <span>Create New</span>
          </span>
          <ChevronDownIcon />
        </motion.button>

        {createOpen ? (
          <div id="vilo-create-menu" className="vilo-sidebar__create-menu" role="menu" aria-label="Create new">
            {createActions.map((action) => {
              const Icon = action.icon;

              return (
                <motion.button
                  key={action.label}
                  type="button"
                  className="vilo-sidebar__create-action"
                  variants={itemVariants}
                  whileHover={hoverLift}
                  role="menuitem"
                  onClick={() => {
                    setCreateOpen(false);
                    router.push(action.href);
                    onClose();
                  }}
                >
                  <span className="vilo-sidebar__icon-wrap">
                    <Icon />
                  </span>
                  <span>{action.label}</span>
                </motion.button>
              );
            })}
          </div>
        ) : null}

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
            {activityItems.length === 0 ? <div className="vilo-activity__empty">No recent activity yet.</div> : null}
            {activityItems.map((item) => (
              <motion.div key={item.id} variants={itemVariants} whileHover={hoverLift}>
                {item.href ? (
                  <Link href={item.href} className="vilo-activity__item" onClick={onClose}>
                    <span className="vilo-activity__status">
                      <CheckCircleIcon />
                    </span>
                    <span className="vilo-activity__copy">
                      <span className="vilo-activity__title">{item.title}</span>
                      <span className="vilo-activity__time">{item.module} · {item.timestamp}</span>
                    </span>
                    <ChevronRightIcon />
                  </Link>
                ) : (
                  <div className="vilo-activity__item is-static">
                    <span className="vilo-activity__status">
                      <CheckCircleIcon />
                    </span>
                    <span className="vilo-activity__copy">
                      <span className="vilo-activity__title">{item.title}</span>
                      <span className="vilo-activity__time">{item.module} · {item.timestamp}</span>
                    </span>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </section>
      </div>
    </motion.aside>
  );
}

function resolveNotificationHref(item) {
  const meta = item?.metadata || {};
  if (meta.conversation_id) return `/dashboard/messages?conversation=${meta.conversation_id}`;
  if (meta.message_id) return "/dashboard/messages";
  if (meta.document_id) return "/dashboard/documents";
  if (meta.invoice_id) return "/dashboard/invoices";
  if (meta.task_id) return "/dashboard/tasks";
  if (meta.calendar_event_id) return `/dashboard/calendar?event_id=${meta.calendar_event_id}`;
  if (meta.case_id) return `/dashboard/cases/${meta.case_id}`;
  if (meta.client_id) return `/dashboard/clients/${meta.client_id}`;
  if (item?.type?.includes("message")) return "/dashboard/messages";
  return "";
}

function prettyType(value) {
  const text = String(value || "activity").replace(/[_-]+/g, " ").trim();
  return text ? `${text[0].toUpperCase()}${text.slice(1)}` : "Activity";
}

function formatShortTimestamp(value) {
  if (!value) return "Just now";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Just now";
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function ProgressRing({ value }) {
  const radius = 27;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (value / 100) * circumference;
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="vilo-ring" aria-label={`Completion ${value}%`}>
      <svg viewBox="0 0 72 72" aria-hidden="true">
        <circle cx="36" cy="36" r="27" className="vilo-ring__track" />
        <motion.circle
          cx="36"
          cy="36"
          r="27"
          className="vilo-ring__segment is-indigo"
          initial={shouldReduceMotion ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 0.75, ease: "easeOut" }}
          strokeDasharray={circumference}
        />
        <motion.circle
          cx="36"
          cy="36"
          r="21"
          className="vilo-ring__segment is-green"
          initial={shouldReduceMotion ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - 0.68 * circumference }}
          transition={{ duration: 0.75, delay: 0.08, ease: "easeOut" }}
          strokeDasharray={circumference}
        />
        <motion.circle
          cx="36"
          cy="36"
          r="33"
          className="vilo-ring__segment is-cyan"
          initial={shouldReduceMotion ? false : { strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - 0.56 * circumference }}
          transition={{ duration: 0.75, delay: 0.16, ease: "easeOut" }}
          strokeDasharray={circumference}
        />
      </svg>
      <div className="vilo-ring__center">
        <strong>{value}%</strong>
      </div>
    </div>
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

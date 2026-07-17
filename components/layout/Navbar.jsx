"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "../../lib/api";
import UserAvatar from "../UserAvatar";

export function Navbar({ onMenuClick, user, onLogout }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  async function loadNotifications() {
    try {
      const data = await apiRequest("/api/v1/notifications?page=1&page_size=10");
      setItems(data.items || []);
      setUnreadCount(data.unread_count || 0);
    } catch {
      setItems([]);
      setUnreadCount(0);
    }
  }

  useEffect(() => {
    loadNotifications();
    const id = setInterval(loadNotifications, 25000);
    return () => clearInterval(id);
  }, []);

  async function markRead(id) {
    await apiRequest("/api/v1/notifications/mark-read", {
      method: "POST",
      body: JSON.stringify({ notification_ids: [id] }),
    });
    loadNotifications();
  }

  async function openNotification(item) {
    await markRead(item.id);
    const href = resolveNotificationHref(item);
    if (href) router.push(href);
  }

  async function markAllRead() {
    await apiRequest("/api/v1/notifications/mark-all-read", { method: "POST" });
    loadNotifications();
  }

  return (
    <header className="dashboard-navbar" aria-label="Top navigation">
      <div className="dashboard-navbar__search">
        <button
          type="button"
          className="dashboard-navbar__mobile-menu"
          aria-label="Open sidebar menu"
          onClick={onMenuClick}
        >
          <MenuIcon />
        </button>
        <SearchIcon />
        <input className="dashboard-navbar__search-input" type="text" placeholder="Search 98K" aria-label="Search dashboard" />
      </div>

      <div className="dashboard-navbar__actions">
        <button type="button" className="dashboard-navbar__icon-button" aria-label="Team shortcuts">
          <UsersShortcutIcon />
        </button>
        <button type="button" className="dashboard-navbar__icon-button" aria-label="Time tracker">
          <ClockIcon />
        </button>
        <button
          type="button"
          className="dashboard-navbar__icon-button is-notification"
          aria-label="Notifications"
          onClick={() => setOpen((prev) => !prev)}
        >
          <BellIcon />
          {unreadCount > 0 ? <span className="dashboard-navbar__alert-dot" /> : null}
        </button>
        {open ? (
          <div className="dashboard-navbar__notifications">
            <div className="dashboard-navbar__notifications-header">
              <strong>Notifications</strong>
              <button type="button" onClick={markAllRead}>Mark all read</button>
            </div>
            <div className="dashboard-navbar__notifications-list">
              {items.length === 0 ? <p>No notifications yet.</p> : null}
              {items.map((item) => (
                <button key={item.id} type="button" className="dashboard-navbar__notification-item" onClick={() => openNotification(item)}>
                  <div>
                    <strong>{item.title}</strong>
                    {item.body ? <span>{item.body}</span> : null}
                    <small>{new Date(item.created_at).toLocaleString()}</small>
                  </div>
                  {!item.is_read ? <em>New</em> : null}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <button type="button" className="dashboard-navbar__avatar-button" aria-label="Profile Settings" onClick={() => router.push("/dashboard/settings")}>
          <UserAvatar user={user} size="sm" />
          <span className="dashboard-navbar__online-dot" />
        </button>
        <button type="button" className="dashboard-navbar__identity dashboard-navbar__identity--button" onClick={() => router.push("/dashboard/settings")}>
          <strong>{user?.name || "Loading..."}</strong>
          <span>{user?.role || ""}</span>
        </button>
        <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
}

function resolveNotificationHref(item) {
  const meta = item?.metadata || {};
  if (meta.link) return meta.link;
  if (meta.task_id) return `/dashboard/tasks/${meta.task_id}`;
  if (meta.calendar_event_id) return `/dashboard/calendar?event_id=${meta.calendar_event_id}`;
  if (meta.case_id) return `/dashboard/cases/${meta.case_id}`;
  if (meta.client_id) return `/dashboard/clients/${meta.client_id}`;
  return "";
}

function MenuIcon() {
  return (
    <IconBase>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </IconBase>
  );
}

function IconBase({ children, className = "" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

function SearchIcon() {
  return (
    <IconBase>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </IconBase>
  );
}

function UsersShortcutIcon() {
  return (
    <IconBase>
      <circle cx="10" cy="9" r="4.5" />
      <circle cx="17.2" cy="6.8" r="2.2" />
      <path d="M3.8 19a6.4 6.4 0 0 1 12.4 0" />
      <path d="M15.8 11.6a4.8 4.8 0 0 1 3.8 4.6" />
    </IconBase>
  );
}

function ClockIcon() {
  return (
    <IconBase>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.8v4.6" />
      <path d="M12 12.4h3.3" />
    </IconBase>
  );
}

function BellIcon() {
  return (
    <IconBase>
      <path d="M8.2 17h7.6" />
      <path d="M10 19.4a2.3 2.3 0 0 0 4 0" />
      <path d="M18 17c-1-1.1-1.6-2.7-1.6-4.7 0-2.8-1.8-5-4.4-5s-4.4 2.2-4.4 5C7.6 14.3 7 15.9 6 17" />
    </IconBase>
  );
}

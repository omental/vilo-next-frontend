"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../../lib/api";

export function Navbar({ onMenuClick, user, onLogout }) {
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
                <button key={item.id} type="button" className="dashboard-navbar__notification-item" onClick={() => markRead(item.id)}>
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
        <button type="button" className="dashboard-navbar__avatar-button" aria-label="User profile">
          <span className="dashboard-navbar__avatar">
            <AvatarIcon />
          </span>
          <span className="dashboard-navbar__online-dot" />
        </button>
        <div className="dashboard-navbar__identity">
          <strong>{user?.name || "Loading..."}</strong>
          <span>{user?.role || ""}</span>
        </div>
        <button type="button" className="vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
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

function AvatarIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="dashboard-navbar__avatar-art">
      <defs>
        <linearGradient id="avatar-bg" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#7b70ff" />
          <stop offset="100%" stopColor="#5d46f6" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="16" fill="url(#avatar-bg)" />
      <circle cx="16" cy="12.3" r="5.1" fill="#ffcfb6" />
      <path d="M8.8 26.2c1.9-4.6 5.1-6.9 7.2-6.9 2.1 0 5.3 2.3 7.2 6.9" fill="#f5f6fb" />
      <path d="M11.2 12.4c.1-3 2.2-5.2 4.8-5.2 2.9 0 5 2.3 5 5.4v1.2h-1.8v-1c0-1.2-.9-2.1-2-2.1H15c-1.1 0-2 .9-2 2.1v1h-1.8z" fill="#2d243f" />
      <path d="M11.5 11.4c1.3-2.7 3.5-4.1 6.3-4.1 1.2 0 2.2.3 3 .8-1-1.9-2.8-3.1-4.8-3.1-2.7 0-4.8 2.1-4.8 4.8 0 .5.1 1.1.3 1.6z" fill="#2d243f" opacity=".92" />
    </svg>
  );
}

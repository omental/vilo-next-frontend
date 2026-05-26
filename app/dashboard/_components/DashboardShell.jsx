"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Navbar } from "../../../components/layout/Navbar";
import { Sidebar } from "../../../components/layout/Sidebar";
import { apiRequest } from "../../../lib/api";
import { clearAuth, getCachedUser, getToken, setCachedUser } from "../../../lib/auth";

export default function DashboardShell({ children }) {
  const router = useRouter();
  const [user, setUser] = useState(getCachedUser());
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  useEffect(() => {
    async function load() {
      if (!getToken()) {
        router.replace("/login");
        return;
      }
      try {
        const me = await apiRequest("/api/v1/auth/me");
        setCachedUser(me);
        setUser(me);
        if (me.role === "client") router.replace("/portal");
      } catch {
        router.replace("/login");
      }
    }
    load();
  }, [router]);

  function logout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <div className="dashboard-shell">
      <div
        className={`mobile-sidebar-overlay${isMobileSidebarOpen ? " is-visible" : ""}`}
        onClick={() => setIsMobileSidebarOpen(false)}
        aria-hidden="true"
      />
      <Sidebar isMobileOpen={isMobileSidebarOpen} onClose={() => setIsMobileSidebarOpen(false)} />
      <main className="dashboard-main">
        <div className="dashboard-content-container">
          <Navbar onMenuClick={() => setIsMobileSidebarOpen(true)} />
          <div className="dashboard-userbar">
            <div className="dashboard-userbar__identity">
              <strong>{user?.name || "Loading..."}</strong>
              <span>{user?.role || ""}</span>
            </div>
            <button className="dashboard-userbar__logout vilo-btn vilo-btn--secondary vilo-btn--xs" onClick={logout}>Logout</button>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}

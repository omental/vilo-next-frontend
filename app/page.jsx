"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getCachedUser, getToken } from "../lib/auth";
import { apiRequest } from "../lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    async function resolveHome() {
      if (!getToken()) {
        router.replace("/login");
        return;
      }
      const cached = getCachedUser();
      if (cached?.role) {
        router.replace(cached.role === "client" ? "/portal" : "/dashboard");
        return;
      }
      try {
        const me = await apiRequest("/api/v1/auth/me");
        router.replace(me.role === "client" ? "/portal" : "/dashboard");
      } catch {
        router.replace("/login");
      }
    }
    resolveHome();
  }, [router]);

  return null;
}

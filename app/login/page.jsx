"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiRequest } from "../../lib/api";
import { setCachedUser, setToken } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const result = await apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(result.access_token);
      const user = await apiRequest("/api/v1/auth/me");
      setCachedUser(user);
      router.push(user.role === "client" ? "/portal" : "/dashboard");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <p className="auth-brand">VILO</p>
        <h1>Welcome back</h1>
        <p className="auth-subtitle">Sign in to your legal workspace.</p>
        <input placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error ? <p className="auth-error">{error}</p> : null}
        <button type="submit">Login</button>
        <p className="auth-foot">Need an account? <Link href="/register">Register</Link></p>
      </form>
    </main>
  );
}

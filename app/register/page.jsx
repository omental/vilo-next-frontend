"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiRequest } from "../../lib/api";
import { setCachedUser, setToken } from "../../lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ organization_name: "", organization_slug: "", name: "", email: "", password: "" });
  const [error, setError] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const result = await apiRequest("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(form),
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
        <div className="auth-brand">
          <Image src="/assets/vilo-logo.png" alt="VILO" width={132} height={40} className="auth-brand__logo" priority />
        </div>
        <h1>Create your firm workspace</h1>
        <p className="auth-subtitle">Start with owner access and invite your team later.</p>
        <input placeholder="Organization name" value={form.organization_name} onChange={(e) => setForm({ ...form, organization_name: e.target.value })} required />
        <input placeholder="Organization slug" value={form.organization_slug} onChange={(e) => setForm({ ...form, organization_slug: e.target.value })} required />
        <input placeholder="Your name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <input placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        {error ? <p className="auth-error">{error}</p> : null}
        <button type="submit">Register</button>
        <p className="auth-foot">Already have an account? <Link href="/login">Login</Link></p>
      </form>
    </main>
  );
}

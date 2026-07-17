"use client";

import { useEffect, useMemo, useState } from "react";
import { apiBlob } from "../lib/api";

export function getInitials(nameOrEmail) {
  const text = String(nameOrEmail || "").trim();
  if (!text) return "U";
  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return text.slice(0, 2).toUpperCase();
}

export default function UserAvatar({ user, size = "md", className = "" }) {
  const [imageUrl, setImageUrl] = useState("");
  const version = user?.profile_image_updated_at || "";
  const initials = useMemo(() => getInitials(user?.name || user?.email), [user?.email, user?.name]);

  useEffect(() => {
    if (!version) {
      setImageUrl("");
      return undefined;
    }

    let cancelled = false;
    let objectUrl = "";
    apiBlob(`/api/v1/users/me/profile-picture?v=${encodeURIComponent(version)}`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setImageUrl("");
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [version]);

  return (
    <span className={`user-avatar user-avatar--${size} ${className}`.trim()} aria-hidden="true">
      {imageUrl ? <img src={imageUrl} alt="" /> : <span>{initials}</span>}
    </span>
  );
}

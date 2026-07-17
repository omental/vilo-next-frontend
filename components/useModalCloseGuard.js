"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function useModalCloseGuard({ open, isDirty, isSubmitting = false, onClose, onDiscard }) {
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  const requestClose = useCallback(() => {
    if (isSubmitting) return;
    if (!isDirty) {
      onClose?.();
      return;
    }
    setConfirmDiscard(true);
  }, [isDirty, isSubmitting, onClose]);

  const keepEditing = useCallback(() => {
    setConfirmDiscard(false);
  }, []);

  const discard = useCallback(() => {
    setConfirmDiscard(false);
    onDiscard?.();
    onClose?.();
  }, [onClose, onDiscard]);

  useEffect(() => {
    if (!open) {
      setConfirmDiscard(false);
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      if (confirmDiscard) {
        setConfirmDiscard(false);
        return;
      }
      requestClose();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmDiscard, open, requestClose]);

  useEffect(() => {
    if (!open && !confirmDiscard) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [confirmDiscard, open]);

  return {
    confirmDiscard,
    requestClose,
    keepEditing,
    discard,
  };
}

export function DiscardChangesDialog({ open, onKeepEditing, onDiscard }) {
  const [mounted, setMounted] = useState(false);
  const dialogRef = useRef(null);
  const keepButtonRef = useRef(null);
  const previousFocusRef = useRef(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const timer = window.setTimeout(() => {
      keepButtonRef.current?.focus();
    }, 0);

    return () => {
      window.clearTimeout(timer);
      previousFocusRef.current?.focus?.();
    };
  }, [open]);

  if (!open || !mounted) return null;

  function handleKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onKeepEditing();
      return;
    }

    if (event.key !== "Tab") return;

    const focusable = dialogRef.current
      ? Array.from(dialogRef.current.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"))
          .filter((node) => !node.disabled && node.getAttribute("aria-hidden") !== "true")
      : [];
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div
      className="vilo-discard-overlay"
      role="presentation"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onKeepEditing();
      }}
      onKeyDown={handleKeyDown}
    >
      <button className="vilo-discard-backdrop" type="button" aria-label="Keep editing" onClick={onKeepEditing} />
      <div
        ref={dialogRef}
        className="vilo-discard-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="discard-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="vilo-discard-card__header">
          <h3 id="discard-dialog-title">Discard the information you entered?</h3>
        </div>
        <div className="vilo-discard-card__body">
          <div className="vilo-table-actions">
            <button ref={keepButtonRef} className="vilo-btn vilo-btn--secondary" type="button" onClick={onKeepEditing}>Keep editing</button>
            <button className="vilo-btn vilo-btn--primary" type="button" onClick={onDiscard}>Discard</button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

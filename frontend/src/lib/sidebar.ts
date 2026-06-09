"use client";

import { useSyncExternalStore } from "react";

// Persisted, SSR-safe sidebar collapse state (server snapshot = expanded).
const KEY = "trendscout-sidebar-collapsed";
const listeners = new Set<() => void>();

function read(): boolean {
  if (typeof localStorage === "undefined") return false;
  return localStorage.getItem(KEY) === "1";
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function setSidebarCollapsed(value: boolean): void {
  try {
    localStorage.setItem(KEY, value ? "1" : "0");
  } catch {
    /* storage unavailable — ignore */
  }
  listeners.forEach((l) => l());
}

export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}

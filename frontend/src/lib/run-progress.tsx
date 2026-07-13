"use client";

// Global search-run state: one active pipeline run at a time, polled in a
// context provider so the progress pill/modal survive page navigation and the
// whole app can react when a run finishes.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";

import {
  fetchRunDiff,
  fetchRunProgress,
  type RunDiff,
  type RunMode,
  type RunProgress,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const STORAGE_KEY = "trendscout.activeRun";

interface ActiveRun {
  runId: number;
  query: string;
  mode: RunMode;
}

interface RunProgressContextValue {
  activeRun: ActiveRun | null;
  progress: RunProgress | null;
  diff: RunDiff | null;
  modalOpen: boolean;
  /** Increments whenever a run completes; pages watch this to refetch. */
  completedCount: number;
  startRun: (result: { run_id: number; query: string; mode: RunMode }) => void;
  openModal: () => void;
  closeModal: () => void;
}

const RunProgressContext = createContext<RunProgressContextValue | null>(null);

export function useRunProgress(): RunProgressContextValue {
  const ctx = useContext(RunProgressContext);
  if (!ctx) throw new Error("useRunProgress requires RunProgressProvider");
  return ctx;
}

function readStoredRun(): ActiveRun | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ActiveRun) : null;
  } catch {
    return null;
  }
}

export function RunProgressProvider({ children }: { children: React.ReactNode }) {
  const { t, lang } = useI18n();
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null);
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);
  const terminalHandledRef = useRef<number | null>(null);

  // Resume a run that was started before a full page reload. Must happen
  // after mount (not as a lazy initializer) so server and client render the
  // same initial HTML; the one-off setState here is intentional.
  useEffect(() => {
    const stored = readStoredRun();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored) setActiveRun(stored);
  }, []);

  useEffect(() => {
    if (!activeRun) return;
    const runId = activeRun.runId;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const next = await fetchRunProgress(runId);
        if (cancelled) return;
        setProgress(next);
        const terminal = next.status === "completed" || next.status === "failed";
        if (terminal) {
          window.localStorage.removeItem(STORAGE_KEY);
          if (terminalHandledRef.current !== runId) {
            terminalHandledRef.current = runId;
            if (next.status === "completed") {
              try {
                const nextDiff = await fetchRunDiff(runId, lang);
                if (!cancelled) setDiff(nextDiff);
              } catch {
                /* diff is optional decoration for the modal */
              }
              setCompletedCount((count) => count + 1);
              toast.success(t("search.toastDoneTitle"), {
                description: t("search.toastDoneDesc", {
                  topics: next.n_topics,
                  docs: next.n_documents,
                }),
              });
            } else {
              toast.error(t("search.toastFailedTitle"), {
                description: next.error ?? "",
              });
            }
          }
          return;
        }
      } catch {
        /* transient API failure; keep polling the background run */
      }
      if (!cancelled) timer = setTimeout(poll, 1200);
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeRun, t, lang]);

  const startRun = useCallback(
    (result: { run_id: number; query: string; mode: RunMode }) => {
      const next: ActiveRun = {
        runId: result.run_id,
        query: result.query,
        mode: result.mode,
      };
      terminalHandledRef.current = null;
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setActiveRun(next);
      setDiff(null);
      setProgress({
        run_id: result.run_id,
        status: "running",
        phase: "queued",
        progress: 2,
        message: "",
        n_documents: 0,
        n_topics: 0,
        error: null,
        events: [],
      });
      setModalOpen(true);
      toast.success(t("search.toastStartTitle"), {
        description: t("search.toastStartDesc", { query: result.query }),
      });
    },
    [t],
  );

  const openModal = useCallback(() => setModalOpen(true), []);
  // Closing the dialog after the run has finished (via "close" or "open
  // result") dismisses the whole indicator for good – pill included. While the
  // run is still going, only the dialog closes and the pill stays.
  const closeModal = useCallback(() => {
    setModalOpen(false);
    const terminal =
      progress?.status === "completed" || progress?.status === "failed";
    if (terminal) {
      setActiveRun(null);
      setProgress(null);
      setDiff(null);
    }
  }, [progress]);

  const value = useMemo(
    () => ({
      activeRun,
      progress,
      diff,
      modalOpen,
      completedCount,
      startRun,
      openModal,
      closeModal,
    }),
    [activeRun, progress, diff, modalOpen, completedCount, startRun, openModal, closeModal],
  );

  return (
    <RunProgressContext.Provider value={value}>
      {children}
    </RunProgressContext.Provider>
  );
}

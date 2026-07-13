"use client";

// Renders the search progress modal and the floating bottom-right pill on
// every page, fed by the global run-progress context.

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import SearchProgressModal, {
  SearchProgressPill,
} from "@/components/SearchProgressModal";
import { useRunProgress } from "@/lib/run-progress";

export default function GlobalSearchProgress() {
  const { activeRun, progress, diff, modalOpen, openModal, closeModal } =
    useRunProgress();
  const pathname = usePathname();
  const previousPathname = useRef(pathname);

  // Close the dialog after a route change (e.g. "open result" was clicked).
  // Closing via onClick would unmount the link mid-transition and could cancel
  // the navigation; reacting to the completed route change is race-free.
  useEffect(() => {
    if (previousPathname.current === pathname) return;
    previousPathname.current = pathname;
    if (modalOpen) closeModal();
  }, [pathname, modalOpen, closeModal]);

  if (!activeRun || !progress) return null;

  return (
    <>
      <SearchProgressModal
        open={modalOpen}
        query={activeRun.query}
        mode={activeRun.mode}
        progress={progress}
        diff={diff}
        onClose={closeModal}
      />
      {!modalOpen && <SearchProgressPill progress={progress} onClick={openModal} />}
    </>
  );
}

import type { RunDiffKind } from "@/lib/api";

const STYLES: Record<RunDiffKind, string> = {
  new: "bg-primary/12 text-primary",
  updated: "bg-climate/12 text-climate",
  unchanged: "bg-surface-2 text-muted",
  review: "bg-markets/15 text-markets",
};

export default function ChangeBadge({
  kind,
  label,
}: {
  kind: RunDiffKind;
  label?: string;
}) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${STYLES[kind]}`}
    >
      {label ?? kind}
    </span>
  );
}

import type { RunDiffKind } from "@/lib/api";

const META: Record<RunDiffKind, string> = {
  new: "bg-primary/12 text-primary",
  classification_changed: "bg-climate/12 text-climate",
  content_changed: "bg-climate/12 text-climate",
  evidence_only: "bg-markets/15 text-markets",
  unchanged: "bg-surface-2 text-muted",
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
      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${META[kind]}`}
    >
      {label ?? kind}
    </span>
  );
}

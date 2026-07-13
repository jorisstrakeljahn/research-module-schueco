import {
  FilePenLine,
  FilePlus2,
  Files,
  RefreshCw,
  Tag,
} from "lucide-react";

import type { RunDiffKind } from "@/lib/api";

const META: Record<
  RunDiffKind,
  { className: string; icon: typeof FilePlus2 }
> = {
  new: { className: "bg-primary/12 text-primary", icon: FilePlus2 },
  classification_changed: {
    className: "bg-climate/12 text-climate",
    icon: Tag,
  },
  content_changed: {
    className: "bg-climate/12 text-climate",
    icon: FilePenLine,
  },
  evidence_only: {
    className: "bg-markets/15 text-markets",
    icon: Files,
  },
  unchanged: { className: "bg-surface-2 text-muted", icon: RefreshCw },
};

export default function ChangeBadge({
  kind,
  label,
}: {
  kind: RunDiffKind;
  label?: string;
}) {
  const { className, icon: Icon } = META[kind];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${className}`}
    >
      <Icon className="h-3 w-3" />
      {label ?? kind}
    </span>
  );
}

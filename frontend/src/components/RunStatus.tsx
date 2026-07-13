import { CheckCircle2, CircleDashed, Clock3, Loader2, XCircle } from "lucide-react";

import { useI18n } from "@/lib/i18n";

const STATUS_META = {
  completed: {
    icon: CheckCircle2,
    className: "bg-primary/12 text-primary",
  },
  failed: {
    icon: XCircle,
    className: "bg-digital/10 text-digital",
  },
  running: {
    icon: Loader2,
    className: "bg-markets/15 text-markets",
    animate: true,
  },
  queued: {
    icon: Clock3,
    className: "bg-surface-2 text-muted",
  },
} as const;

export default function RunStatus({ status }: { status: string }) {
  const { t } = useI18n();
  const meta = STATUS_META[status as keyof typeof STATUS_META];
  const Icon = meta?.icon ?? CircleDashed;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        meta?.className ?? "bg-surface-2 text-muted"
      }`}
    >
      <Icon className={`h-3 w-3 ${meta && "animate" in meta && meta.animate ? "animate-spin" : ""}`} />
      {t(`runs.status.${status}`)}
    </span>
  );
}

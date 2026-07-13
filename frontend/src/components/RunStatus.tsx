import { Loader2 } from "lucide-react";

import { useI18n } from "@/lib/i18n";

const STATUS_CLASSES: Record<string, string> = {
  completed: "bg-primary/12 text-primary",
  failed: "bg-digital/10 text-digital",
  running: "bg-markets/15 text-markets",
  queued: "bg-surface-2 text-muted",
};

export default function RunStatus({ status }: { status: string }) {
  const { t } = useI18n();

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
        STATUS_CLASSES[status] ?? "bg-surface-2 text-muted"
      }`}
    >
      {status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
      {t(`runs.status.${status}`)}
    </span>
  );
}

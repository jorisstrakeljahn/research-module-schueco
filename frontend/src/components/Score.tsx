"use client";

import { useI18n } from "@/lib/i18n";

export default function Score({
  field,
  value,
}: {
  /** i18n suffix, e.g. "impact" -> t("field.impact") */
  field: "impact" | "urgency" | "uncertainty";
  value: number | null;
}) {
  const { t } = useI18n();
  const v = value ?? 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px] text-muted">
        <span className="truncate">{t(`field.${field}`)}</span>
        <span className="font-mono text-fg">
          {value != null ? value.toFixed(1) : "–"}
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full rounded-full bg-surface-2">
        <div
          className="h-1.5 rounded-full bg-primary"
          style={{ width: `${(v / 10) * 100}%` }}
        />
      </div>
    </div>
  );
}

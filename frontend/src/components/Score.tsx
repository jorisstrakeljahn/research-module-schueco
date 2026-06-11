export default function Score({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  const v = value ?? 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-[12px] text-muted">
        <span>{label}</span>
        <span className="font-mono text-fg">{value != null ? value.toFixed(1) : "n/a"}</span>
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

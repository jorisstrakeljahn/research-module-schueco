"use client";

import {
  CATEGORY_META,
  PESTEL_SECTORS,
  RADAR_STAGE_META,
  type Trend,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

// Schüco-style Trendradar: PESTEL sectors (angle) x Act/Prepare/Watch rings
// (radius) x thematic category (colour) x corpus share (dot size).

const SIZE = 720;
const C = SIZE / 2;
const MAX_R = 308;
const PAD = 92; // breathing room so sector labels are never clipped
const N_SECTORS = PESTEL_SECTORS.length;
const SECTOR_DEG = 360 / N_SECTORS;
const RING_BANDS: Record<number, [number, number]> = {
  0: [0.06, 0.36], // Act
  1: [0.4, 0.66], // Prepare
  2: [0.7, 0.98], // Watch
};

function deg2rad(d: number): number {
  return ((d - 90) * Math.PI) / 180;
}

function polar(angleDeg: number, radius: number): { x: number; y: number } {
  const a = deg2rad(angleDeg);
  return { x: C + radius * Math.cos(a), y: C + radius * Math.sin(a) };
}

function jitter(id: number, salt: number): number {
  const v = Math.sin(id * 12.9898 + salt * 78.233) * 43758.5453;
  return v - Math.floor(v);
}

function sectorIndex(trend: Trend): number {
  const idx = PESTEL_SECTORS.findIndex((s) => s.key === trend.pestel?.[0]);
  return idx >= 0 ? idx : 1;
}

function stageRing(trend: Trend): number {
  return RADAR_STAGE_META[trend.radar_stage ?? "watch"]?.ring ?? 2;
}

export default function TrendRadar({
  trends,
  selectedId,
  onSelect,
}: {
  trends: Trend[];
  selectedId?: number | null;
  onSelect?: (t: Trend) => void;
}) {
  const { t } = useI18n();
  const maxSize = Math.max(1, ...trends.map((t) => t.size));

  const placed = trends.map((t) => {
    const sec = sectorIndex(t);
    const [inner, outer] = RING_BANDS[stageRing(t)];
    const angle = sec * SECTOR_DEG + (0.2 + 0.6 * jitter(t.id, 1)) * SECTOR_DEG;
    const radius = (inner + (outer - inner) * jitter(t.id, 2)) * MAX_R;
    const { x, y } = polar(angle, radius);
    const r = 6 + (t.size / maxSize) * 12;
    const color = CATEGORY_META[t.category ?? "technology"]?.color ?? "#9ca3af";
    return { trend: t, x, y, r, color };
  });

  return (
    <div className="@container flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-hidden xl:flex-row xl:items-stretch">
      <div className="flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden">
        <svg
          viewBox={`${-PAD} ${-PAD} ${SIZE + 2 * PAD} ${SIZE + 2 * PAD}`}
          className="aspect-square h-[min(920px,100cqmin,calc(100dvh-11rem))] w-[min(920px,100cqmin,calc(100dvh-11rem))] transition-[width,height] duration-200 ease-out"
          role="img"
          aria-label="Radar"
          preserveAspectRatio="xMidYMid meet"
        >
        {[2, 1, 0].map((ring) => (
          <circle
            key={ring}
            cx={C}
            cy={C}
            r={RING_BANDS[ring][1] * MAX_R}
            fill="var(--ring-band)"
            stroke="var(--ring-line)"
            strokeWidth={1}
          />
        ))}

        {PESTEL_SECTORS.map((_, i) => {
          const { x, y } = polar(i * SECTOR_DEG, MAX_R);
          return (
            <line
              key={i}
              x1={C}
              y1={C}
              x2={x}
              y2={y}
              stroke="var(--ring-line)"
              strokeWidth={1}
            />
          );
        })}

        {PESTEL_SECTORS.map((s, i) => {
          const { x, y } = polar(i * SECTOR_DEG + SECTOR_DEG / 2, MAX_R + 30);
          return (
            <text
              key={s.key}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="var(--muted)"
              style={{ fontSize: 13, fontWeight: 600 }}
            >
              {s.label}
            </text>
          );
        })}

        {[0, 1, 2].map((ring) => {
          const mid = ((RING_BANDS[ring][0] + RING_BANDS[ring][1]) / 2) * MAX_R;
          return (
            <text
              key={ring}
              x={C}
              y={C - mid}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="var(--faint)"
              style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2 }}
            >
              {Object.values(RADAR_STAGE_META).find((m) => m.ring === ring)?.label}
            </text>
          );
        })}

        {placed.map((p) => {
          const selected = selectedId === p.trend.id;
          return (
            <circle
              key={p.trend.id}
              cx={p.x}
              cy={p.y}
              r={selected ? p.r + 2 : p.r}
              fill={p.color}
              fillOpacity={0.9}
              stroke={selected ? "var(--fg)" : "var(--bg)"}
              strokeWidth={selected ? 2 : 1.5}
              className="cursor-pointer transition-all"
              onClick={() => onSelect?.(p.trend)}
            >
              <title>
                {p.trend.title}
                {"\n"}
                {(p.trend.radar_stage ?? "watch").toUpperCase()}
                {"  "}
                {CATEGORY_META[p.trend.category ?? "technology"]?.label}
                {"\n"}
                impact {p.trend.impact?.toFixed(1) ?? "n/a"}
                {"   "}
                urgency {p.trend.urgency?.toFixed(1) ?? "n/a"}
              </title>
            </circle>
          );
        })}
        </svg>
      </div>

      <div className="shrink-0 space-y-4 border-t border-border pt-4 text-xs xl:w-44 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-1">
        <div>
          <p className="mb-2 font-medium uppercase tracking-wider text-faint">
            {t("radar.legend.category")}
          </p>
          <ul className="space-y-1.5">
            {Object.entries(CATEGORY_META).map(([key, meta]) => (
              <li key={key} className="flex items-center gap-2 text-muted">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: meta.color }}
                />
                {meta.label}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-2 font-medium uppercase tracking-wider text-faint">
            {t("radar.legend.ring")}
          </p>
          <ul className="space-y-2">
            {(["act", "prepare", "watch"] as const).map((ring) => (
              <li key={ring}>
                <span className="text-fg">{t(`radar.ring.${ring}`)}</span>
                <span className="ml-2 text-faint">{t(`radar.ring.${ring}Desc`)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-faint">{t("radar.legend.size")}</p>
        </div>
      </div>
    </div>
  );
}

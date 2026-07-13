"use client";

import { useLayoutEffect, useRef, useState, type RefObject } from "react";

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
const MAX_R = 330;
const PAD = 64; // breathing room so sector labels are never clipped
const MAX_CHART_PX = 1080;
const MIN_CHART_PX = 300;
const N_SECTORS = PESTEL_SECTORS.length;
const SECTOR_DEG = 360 / N_SECTORS;
const RING_BANDS: Record<number, [number, number]> = {
  0: [0.14, 0.36], // Act (starts away from the dead center so dots stay legible)
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

function idSeed(id: string | number): number {
  if (typeof id === "number") return id;
  return Array.from(id).reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 7);
}

function jitter(id: string | number, salt: number): number {
  const v = Math.sin(idSeed(id) * 12.9898 + salt * 78.233) * 43758.5453;
  return v - Math.floor(v);
}

function sectorIndex(trend: Trend): number {
  const idx = PESTEL_SECTORS.findIndex((s) => s.key === trend.pestel?.[0]);
  return idx >= 0 ? idx : 1;
}

function stageRing(trend: Trend): number {
  return RADAR_STAGE_META[trend.radar_stage ?? "watch"]?.ring ?? 2;
}

function useChartSize(): { ref: RefObject<HTMLDivElement | null>; size: number } {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(MIN_CHART_PX);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    const update = () => {
      const { width, height } = el.getBoundingClientRect();
      const next = Math.min(width, height, MAX_CHART_PX);
      setSize(Math.max(MIN_CHART_PX, Math.floor(next)));
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return { ref, size };
}

export default function TrendRadar({
  trends,
  selectedId,
  onSelect,
}: {
  trends: Trend[];
  selectedId?: string | number | null;
  onSelect?: (t: Trend) => void;
}) {
  const { t } = useI18n();
  const { ref: chartRef, size: chartSize } = useChartSize();
  const maxSize = Math.max(1, ...trends.map((t) => t.size));

  // Deterministic, collision-avoiding placement: trends sharing a sector+ring
  // cell are fanned out evenly across the sector angle (and staggered in
  // radius) instead of randomly jittered, so dots never pile up on each other.
  const cells = new Map<string, Trend[]>();
  for (const trend of trends) {
    const key = `${sectorIndex(trend)}:${stageRing(trend)}`;
    const bucket = cells.get(key) ?? [];
    bucket.push(trend);
    cells.set(key, bucket);
  }
  const placed = [...cells.entries()].flatMap(([key, bucket]) => {
    const [sec, ring] = key.split(":").map(Number);
    const [inner, outer] = RING_BANDS[ring];
    // Big dots go to the outer edge of the band where there is more arc length.
    const sorted = [...bucket].sort(
      (a, b) => a.size - b.size || idSeed(a.id) - idSeed(b.id),
    );
    return sorted.map((trend, index) => {
      const step = 1 / (sorted.length + 1);
      const angleFrac = step * (index + 1);
      const angle = sec * SECTOR_DEG + (0.06 + 0.88 * angleFrac) * SECTOR_DEG;
      // Spread evenly across the band radius as well (spiral-like fan).
      const radialFrac =
        sorted.length === 1 ? 0.5 : 0.12 + 0.76 * ((index + 0.5) / sorted.length);
      const radius = (inner + (outer - inner) * radialFrac) * MAX_R;
      const { x, y } = polar(angle, radius);
      const r = 6 + (trend.size / maxSize) * 12;
      const color = CATEGORY_META[trend.category ?? "technology"]?.color ?? "#9ca3af";
      return { trend, x, y, r, color };
    });
  });

  // Final safety pass: nudge any two dots apart until nothing overlaps. The
  // displacement stays small (a few px), so sector/ring semantics are kept.
  for (let iteration = 0; iteration < 40; iteration++) {
    let moved = false;
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const a = placed[i];
        const b = placed[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 0.001;
        const minDist = a.r + b.r + 3;
        if (dist >= minDist) continue;
        const push = (minDist - dist) / 2;
        const ux = dx / dist;
        const uy = dy / dist;
        a.x -= ux * push;
        a.y -= uy * push;
        b.x += ux * push;
        b.y += uy * push;
        moved = true;
      }
    }
    if (!moved) break;
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div
        ref={chartRef}
        className="flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden"
      >
        <svg
          viewBox={`${-PAD} ${-PAD} ${SIZE + 2 * PAD} ${SIZE + 2 * PAD}`}
          width={chartSize}
          height={chartSize}
          className="shrink-0 transition-[width,height] duration-200 ease-out"
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
          const { x, y } = polar(i * SECTOR_DEG + SECTOR_DEG / 2, MAX_R + 26);
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

        {/* Legends are part of the chart itself so the radar can use the full
            width; foreignObject gives us robust text layout that scales with
            the SVG. */}
        <foreignObject x={-PAD} y={C + MAX_R + 8} width={SIZE + 2 * PAD} height={PAD + (SIZE - C - MAX_R) - 8}>
          <div className="flex h-full flex-col items-center justify-end gap-2.5 text-center">
            <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-1">
              {Object.entries(CATEGORY_META).map(([key, meta]) => (
                <span
                  key={key}
                  className="flex items-center gap-2"
                  style={{ fontSize: 14, color: "var(--muted)" }}
                >
                  <span
                    className="inline-block rounded-full"
                    style={{ width: 11, height: 11, backgroundColor: meta.color }}
                  />
                  {meta.label}
                </span>
              ))}
            </div>
            <div
              className="flex flex-wrap items-center justify-center gap-x-6 gap-y-1"
              style={{ fontSize: 13, color: "var(--faint)" }}
            >
              {(["act", "prepare", "watch"] as const).map((ring) => (
                <span key={ring}>
                  <span style={{ color: "var(--fg)", fontWeight: 600 }}>
                    {t(`radar.ring.${ring}`)}
                  </span>{" "}
                  · {t(`radar.ring.${ring}Desc`)}
                </span>
              ))}
              <span>{t("radar.legend.size")}</span>
            </div>
          </div>
        </foreignObject>
        </svg>
      </div>
    </div>
  );
}

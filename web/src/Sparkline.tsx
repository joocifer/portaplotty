import type { ActivitySample } from "./types";

export function Sparkline({
  samples,
  width = 120,
  height = 28,
  color = "#34d399",
}: {
  samples: ActivitySample[];
  width?: number;
  height?: number;
  color?: string;
}) {
  if (samples.length < 2) {
    return (
      <svg className="sparkline" width={width} height={height} aria-hidden>
        <line
          x1="0"
          y1={height - 1}
          x2={width}
          y2={height - 1}
          stroke="var(--border)"
          strokeWidth="1"
        />
      </svg>
    );
  }

  const values = samples.map((s) => s.established);
  const max = Math.max(...values, 1);
  const pad = 2;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const step = w / (values.length - 1);

  const pts = values.map((v, i) => {
    const x = pad + i * step;
    const y = pad + h - (v / max) * h;
    return [x, y] as const;
  });

  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area =
    `${pad},${pad + h} ` + line + ` ${pad + w},${pad + h}`;
  const [lastX, lastY] = pts[pts.length - 1];

  return (
    <svg className="sparkline" width={width} height={height} aria-hidden>
      <polygon points={area} fill={color} opacity="0.12" />
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX} cy={lastY} r="2" fill={color} />
    </svg>
  );
}

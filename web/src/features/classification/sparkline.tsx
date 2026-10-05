/** Minimal SVG sparkline. Missing points break the line; nothing is interpolated. */
export function Sparkline({
  values,
  label,
  width = 260,
  height = 56,
}: {
  values: (number | null)[];
  label: string;
  width?: number;
  height?: number;
}) {
  const nums = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (nums.length < 2) {
    return <p className="text-xs text-muted-foreground">Not enough history yet for {label}.</p>;
  }
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const pad = 4;
  const x = (i: number) => pad + (i / Math.max(values.length - 1, 1)) * (width - 2 * pad);
  const y = (v: number) => height - pad - ((v - min) / span) * (height - 2 * pad);

  const segments: string[] = [];
  let current: string[] = [];
  values.forEach((v, i) => {
    if (v === null || !Number.isFinite(v)) {
      if (current.length) segments.push(current.join(" "));
      current = [];
    } else {
      current.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    }
  });
  if (current.length) segments.push(current.join(" "));

  const last = nums[nums.length - 1];
  return (
    <svg
      role="img"
      aria-label={`${label}: from ${nums[0].toFixed(2)} to ${last.toFixed(2)} percent, range ${min.toFixed(2)} to ${max.toFixed(2)}`}
      viewBox={`0 0 ${width} ${height}`}
      className="h-14 w-full text-info"
      preserveAspectRatio="none"
    >
      {min < 0 && max > 0 ? (
        <line
          x1={pad}
          x2={width - pad}
          y1={y(0)}
          y2={y(0)}
          stroke="currentColor"
          strokeOpacity={0.25}
          strokeDasharray="3 3"
        />
      ) : null}
      {segments.map((points) => (
        <polyline
          key={points}
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.75}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}
    </svg>
  );
}

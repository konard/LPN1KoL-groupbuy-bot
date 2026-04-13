/**
 * Simple SVG Donut Chart Component (no external dependencies)
 */
import React from 'react';

const COLORS = [
  '#2563eb', '#16a34a', '#d97706', '#dc2626', '#0891b2',
  '#7c3aed', '#db2777', '#059669', '#ea580c', '#4338ca',
];

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? '0' : '1';
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

export default function DonutChart({ data = [], size = 180, label = '' }) {
  if (!data || data.length === 0) {
    return <div className="chart-empty">Нет данных</div>;
  }

  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return <div className="chart-empty">Нет данных</div>;

  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 10;
  const innerR = outerR * 0.55;
  const strokeWidth = outerR - innerR;

  let currentAngle = 0;
  const slices = data.map((d, i) => {
    const angle = (d.value / total) * 360;
    const slice = {
      startAngle: currentAngle,
      endAngle: currentAngle + angle,
      color: COLORS[i % COLORS.length],
      name: d.name,
      value: d.value,
      percent: ((d.value / total) * 100).toFixed(1),
    };
    currentAngle += angle;
    return slice;
  });

  return (
    <div className="chart-wrapper">
      {label && <div className="chart-label">{label}</div>}
      <div className="donut-chart-container">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {slices.map((slice, i) => {
            const gap = 1.5;
            const startAdj = slice.startAngle + gap;
            const endAdj = slice.endAngle - gap;
            if (endAdj <= startAdj) return null;
            const d = arcPath(cx, cy, (outerR + innerR) / 2, startAdj, endAdj);
            return (
              <path
                key={i}
                d={d}
                fill="none"
                stroke={slice.color}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
              >
                <title>{`${slice.name}: ${slice.value} (${slice.percent}%)`}</title>
              </path>
            );
          })}
          <text
            x={cx}
            y={cy - 6}
            textAnchor="middle"
            fontSize="18"
            fontWeight="700"
            fill="#1e293b"
          >
            {total}
          </text>
          <text
            x={cx}
            y={cy + 14}
            textAnchor="middle"
            fontSize="10"
            fill="#64748b"
          >
            всего
          </text>
        </svg>

        <div className="donut-legend">
          {slices.map((slice, i) => (
            <div key={i} className="donut-legend-item">
              <span
                className="donut-legend-dot"
                style={{ background: slice.color }}
              />
              <span className="donut-legend-name">{slice.name}</span>
              <span className="donut-legend-value">
                {slice.value} ({slice.percent}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

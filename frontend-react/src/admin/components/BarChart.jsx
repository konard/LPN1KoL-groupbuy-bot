/**
 * Simple SVG Bar Chart Component (no external dependencies)
 */
import React from 'react';

export default function BarChart({ data = [], color = '#2563eb', height = 180, label = '' }) {
  if (!data || data.length === 0) {
    return (
      <div className="chart-empty">Нет данных</div>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1);
  const barWidth = Math.floor(560 / data.length) - 4;
  const chartWidth = 560;
  const chartHeight = height - 40; // leave space for labels

  return (
    <div className="chart-wrapper">
      {label && <div className="chart-label">{label}</div>}
      <svg
        viewBox={`0 0 ${chartWidth} ${height}`}
        className="chart-svg"
        aria-label={label}
      >
        {/* Y axis grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = chartHeight - chartHeight * ratio;
          return (
            <g key={ratio}>
              <line
                x1={0}
                y1={y}
                x2={chartWidth}
                y2={y}
                stroke="#e2e8f0"
                strokeWidth="1"
              />
              <text
                x={0}
                y={y - 3}
                fontSize="10"
                fill="#64748b"
              >
                {Math.round(maxValue * ratio)}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {data.map((d, i) => {
          const barHeight = (d.value / maxValue) * chartHeight;
          const x = i * (barWidth + 4) + 2;
          const y = chartHeight - barHeight;
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                fill={color}
                rx={3}
                opacity={0.85}
              >
                <title>{`${d.name}: ${d.value}`}</title>
              </rect>
              <text
                x={x + barWidth / 2}
                y={chartHeight + 14}
                textAnchor="middle"
                fontSize="10"
                fill="#64748b"
              >
                {d.name.length > 6 ? d.name.slice(0, 6) + '…' : d.name}
              </text>
              {d.value > 0 && (
                <text
                  x={x + barWidth / 2}
                  y={y - 4}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#1e293b"
                  fontWeight="500"
                >
                  {d.value}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

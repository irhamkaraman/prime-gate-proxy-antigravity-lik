import React, { useState } from 'react';
import { TokenVolumePoint } from '../types';

interface TokenChartProps {
  data: TokenVolumePoint[];
  timeRange: '1s' | '1m' | '1h' | '1d';
  onTimeRangeChange: (range: '1s' | '1m' | '1h' | '1d') => void;
}

export const TokenChart: React.FC<TokenChartProps> = ({
  data,
  timeRange,
  onTimeRangeChange,
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<TokenVolumePoint | null>(null);

  // Fallback demo points if live data is empty
  const chartPoints = data.length > 0 ? data : [
    { timestamp: '1', timeLabel: '03:10', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '2', timeLabel: '03:15', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '3', timeLabel: '03:20', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '4', timeLabel: '03:25', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '5', timeLabel: '03:30', prompt: 1420, reasoning: 680, completion: 340, total: 2440 },
    { timestamp: '6', timeLabel: '03:35', prompt: 0, reasoning: 0, completion: 0, total: 0 },
  ];

  const maxTotal = Math.max(...chartPoints.map(p => p.total), 100);
  const chartHeight = 220;
  const chartWidth = 900;
  const paddingBottom = 30;
  const paddingTop = 20;
  const usableHeight = chartHeight - paddingBottom - paddingTop;

  return (
    <div className="glass-card" style={{ padding: '24px 28px', marginTop: 20 }}>
      {/* Chart Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff' }}>
            Token Consumption Breakdown
          </h2>
          <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 3 }}>
            Granular token volume segmented into Prompt, Reasoning (Thinking), and Completion
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Legend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: '#ea580c' }} />
              <span style={{ color: '#d6d3d1' }}>Prompt</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: '#d97706' }} />
              <span style={{ color: '#d6d3d1' }}>Reasoning</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: '#f59e0b' }} />
              <span style={{ color: '#d6d3d1' }}>Completion</span>
            </div>
          </div>

          {/* Time range selector */}
          <div
            style={{
              display: 'flex',
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: 8,
              padding: 2,
              border: '1px solid rgba(168, 162, 158, 0.15)',
            }}
          >
            {(['1s', '1m', '1h', '1d'] as const).map(range => (
              <button
                key={range}
                onClick={() => onTimeRangeChange(range)}
                style={{
                  background: timeRange === range ? '#d97706' : 'transparent',
                  color: timeRange === range ? '#ffffff' : '#a8a29e',
                  border: 'none',
                  borderRadius: 6,
                  padding: '4px 10px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* SVG Chart */}
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          style={{ width: '100%', height: chartHeight, overflow: 'visible' }}
        >
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = paddingTop + usableHeight * (1 - pct);
            const val = Math.round(maxTotal * pct);
            return (
              <g key={idx}>
                <line
                  x1={45}
                  y1={y}
                  x2={chartWidth}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray="4 4"
                />
                <text
                  x={35}
                  y={y + 4}
                  fill="#78716c"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="var(--font-mono)"
                >
                  {val.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {chartPoints.map((p, idx) => {
            const barWidth = Math.max(12, Math.min(32, (chartWidth - 60) / (chartPoints.length * 2)));
            const step = (chartWidth - 60) / chartPoints.length;
            const x = 55 + idx * step + (step - barWidth) / 2;

            const promptHeight = (p.prompt / maxTotal) * usableHeight;
            const reasoningHeight = (p.reasoning / maxTotal) * usableHeight;
            const completionHeight = (p.completion / maxTotal) * usableHeight;

            const yPrompt = paddingTop + usableHeight - promptHeight;
            const yReasoning = yPrompt - reasoningHeight;
            const yCompletion = yReasoning - completionHeight;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredPoint(p)}
                onMouseLeave={() => setHoveredPoint(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Invisible hover capture column */}
                <rect
                  x={x - 6}
                  y={paddingTop}
                  width={barWidth + 12}
                  height={usableHeight}
                  fill="transparent"
                />

                {/* Prompt segment */}
                {promptHeight > 0 && (
                  <rect
                    x={x}
                    y={yPrompt}
                    width={barWidth}
                    height={promptHeight}
                    fill="#ea580c"
                    rx={completionHeight === 0 && reasoningHeight === 0 ? 3 : 0}
                  />
                )}

                {/* Reasoning segment */}
                {reasoningHeight > 0 && (
                  <rect
                    x={x}
                    y={yReasoning}
                    width={barWidth}
                    height={reasoningHeight}
                    fill="#d97706"
                    rx={completionHeight === 0 ? 3 : 0}
                  />
                )}

                {/* Completion segment */}
                {completionHeight > 0 && (
                  <rect
                    x={x}
                    y={yCompletion}
                    width={barWidth}
                    height={completionHeight}
                    fill="#f59e0b"
                    rx={3}
                  />
                )}

                {/* X-axis label */}
                <text
                  x={x + barWidth / 2}
                  y={chartHeight - 8}
                  fill="#78716c"
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                >
                  {p.timeLabel}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip */}
        {hoveredPoint && hoveredPoint.total > 0 && (
          <div
            style={{
              position: 'absolute',
              top: 10,
              right: 20,
              background: '#1c1713',
              border: '1px solid rgba(245, 158, 11, 0.35)',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: 12,
              pointerEvents: 'none',
              boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div style={{ fontWeight: 700, color: '#fafaf9' }}>
              Time: {hoveredPoint.timeLabel}
            </div>
            <div style={{ color: '#ea580c' }}>
              Prompt: {hoveredPoint.prompt.toLocaleString()} tokens
            </div>
            <div style={{ color: '#d97706' }}>
              Reasoning: {hoveredPoint.reasoning.toLocaleString()} tokens
            </div>
            <div style={{ color: '#f59e0b' }}>
              Completion: {hoveredPoint.completion.toLocaleString()} tokens
            </div>
            <div style={{ color: '#ffffff', fontWeight: 600, borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 4 }}>
              Total: {hoveredPoint.total.toLocaleString()} tokens
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState, useRef, useEffect } from 'react';
import { TokenVolumePoint, TimeRange } from '../types';

interface TokenChartProps {
  data: TokenVolumePoint[];
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
}

export const TokenChart: React.FC<TokenChartProps> = ({
  data,
  timeRange,
  onTimeRangeChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(1100);
  const [hoveredPoint, setHoveredPoint] = useState<TokenVolumePoint | null>(null);
  const [hoveredX, setHoveredX] = useState<number | null>(null);

  // Measure dynamic container width with ResizeObserver to ensure 100% edge-to-edge distribution
  useEffect(() => {
    if (!containerRef.current) return;
    const updateWidth = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        if (rect.width > 200) {
          setContainerWidth(Math.round(rect.width));
        }
      }
    };

    updateWidth();

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 200) {
          setContainerWidth(Math.round(entry.contentRect.width));
        }
      }
    });

    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Fallback demo points if live data is empty
  const chartPoints = data && data.length > 0 ? data : [
    { timestamp: '1', timeLabel: '03:10', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '2', timeLabel: '03:15', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '3', timeLabel: '03:20', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '4', timeLabel: '03:25', prompt: 0, reasoning: 0, completion: 0, total: 0 },
    { timestamp: '5', timeLabel: '03:30', prompt: 1420, reasoning: 680, completion: 340, total: 2440 },
    { timestamp: '6', timeLabel: '03:35', prompt: 0, reasoning: 0, completion: 0, total: 0 },
  ];

  const maxTotal = Math.max(...chartPoints.map(p => p.total), 100);
  const chartHeight = 240;
  const paddingTop = 22;
  const paddingBottom = 34;
  const marginLeft = 68;
  const marginRight = 24;

  const usableWidth = Math.max(100, containerWidth - marginLeft - marginRight);
  const usableHeight = chartHeight - paddingTop - paddingBottom;

  // Stride calculation to prevent X-axis label collision
  const approxLabelWidth = 70;
  const maxLabels = Math.max(3, Math.floor(usableWidth / approxLabelWidth));
  const stride = Math.max(1, Math.ceil(chartPoints.length / maxLabels));

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
            {(['1m', '1h', '1d', '1month'] as const).map(range => (
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

      {/* SVG Chart Container */}
      <div
        ref={containerRef}
        style={{
          position: 'relative',
          width: '100%',
          overflow: 'hidden',
        }}
      >
        <svg
          viewBox={`0 0 ${containerWidth} ${chartHeight}`}
          style={{ width: '100%', height: chartHeight, display: 'block', overflow: 'visible' }}
        >
          {/* Grid lines and Y-axis labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = paddingTop + usableHeight * (1 - pct);
            const val = Math.round(maxTotal * pct);
            return (
              <g key={idx}>
                <line
                  x1={marginLeft}
                  y1={y}
                  x2={containerWidth - marginRight}
                  y2={y}
                  stroke="rgba(255, 255, 255, 0.06)"
                  strokeDasharray="4 4"
                />
                <text
                  x={marginLeft - 12}
                  y={y + 3.5}
                  fill="#78716c"
                  fontSize="11"
                  textAnchor="end"
                  fontFamily="var(--font-mono)"
                >
                  {val.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Vertical guide line on hover */}
          {hoveredX !== null && (
            <line
              x1={hoveredX}
              y1={paddingTop}
              x2={hoveredX}
              y2={paddingTop + usableHeight}
              stroke="rgba(245, 158, 11, 0.35)"
              strokeDasharray="3 3"
              strokeWidth={1.5}
            />
          )}

          {/* Evenly distributed bars across full container width */}
          {chartPoints.map((p, idx) => {
            const step = usableWidth / chartPoints.length;
            const barWidth = Math.max(6, Math.min(26, step * 0.68));
            const x = marginLeft + idx * step + (step - barWidth) / 2;
            const centerX = x + barWidth / 2;

            const promptHeight = (p.prompt / maxTotal) * usableHeight;
            const reasoningHeight = (p.reasoning / maxTotal) * usableHeight;
            const completionHeight = (p.completion / maxTotal) * usableHeight;

            const yPrompt = paddingTop + usableHeight - promptHeight;
            const yReasoning = yPrompt - reasoningHeight;
            const yCompletion = yReasoning - completionHeight;

            // X-axis label anti-collision rule
            const isLast = idx === chartPoints.length - 1;
            const isFirst = idx === 0;
            const shouldShowLabel = isFirst || idx % stride === 0 || (isLast && (chartPoints.length - 1) % stride >= Math.floor(stride * 0.4));

            const isHovered = hoveredPoint === p;

            return (
              <g
                key={idx}
                onMouseEnter={() => {
                  setHoveredPoint(p);
                  setHoveredX(centerX);
                }}
                onMouseLeave={() => {
                  setHoveredPoint(null);
                  setHoveredX(null);
                }}
                style={{ cursor: 'pointer' }}
              >
                {/* Full-height invisible hover capture area */}
                <rect
                  x={marginLeft + idx * step}
                  y={paddingTop}
                  width={step}
                  height={usableHeight + 20}
                  fill="transparent"
                />

                {/* Subtle baseline track for empty/zero slots */}
                <rect
                  x={x}
                  y={paddingTop + usableHeight - 3}
                  width={barWidth}
                  height={3}
                  rx={1.5}
                  fill={isHovered ? 'rgba(245, 158, 11, 0.3)' : 'rgba(255, 255, 255, 0.08)'}
                  style={{ transition: 'fill 0.15s ease' }}
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
                    opacity={isHovered ? 1 : 0.9}
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
                    opacity={isHovered ? 1 : 0.9}
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
                    opacity={isHovered ? 1 : 0.9}
                  />
                )}

                {/* Top highlight cap on hover */}
                {isHovered && p.total > 0 && (
                  <rect
                    x={x - 1}
                    y={Math.min(yPrompt, yReasoning, yCompletion) - 2}
                    width={barWidth + 2}
                    height={2}
                    fill="#fef08a"
                    rx={1}
                  />
                )}

                {/* Clean, Non-overlapping X-axis timestamp label */}
                {shouldShowLabel && (
                  <text
                    x={centerX}
                    y={chartHeight - 8}
                    fill={isHovered ? '#f59e0b' : '#78716c'}
                    fontSize="11"
                    fontWeight={isHovered ? '600' : '400'}
                    textAnchor="middle"
                    fontFamily="var(--font-mono)"
                  >
                    {p.timeLabel}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Floating Context-Aware Tooltip */}
        {hoveredPoint && hoveredPoint.total > 0 && hoveredX !== null && (
          <div
            style={{
              position: 'absolute',
              top: 12,
              left: Math.min(containerWidth - 230, Math.max(marginLeft, hoveredX - 100)),
              background: '#1c1713',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              borderRadius: 8,
              padding: '10px 14px',
              fontSize: 12,
              pointerEvents: 'none',
              boxShadow: '0 10px 25px rgba(0,0,0,0.6)',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              zIndex: 30,
              backdropFilter: 'blur(8px)',
            }}
          >
            <div style={{ fontWeight: 700, color: '#fafaf9', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 4 }}>
              Timestamp: {hoveredPoint.timeLabel}
            </div>
            <div style={{ color: '#ea580c', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span>Prompt:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{hoveredPoint.prompt.toLocaleString()}</span>
            </div>
            <div style={{ color: '#d97706', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span>Reasoning:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{hoveredPoint.reasoning.toLocaleString()}</span>
            </div>
            <div style={{ color: '#f59e0b', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span>Completion:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{hoveredPoint.completion.toLocaleString()}</span>
            </div>
            <div style={{ color: '#ffffff', fontWeight: 700, borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 4, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span>Total Volume:</span>
              <span style={{ fontFamily: 'var(--font-mono)', color: '#f59e0b' }}>{hoveredPoint.total.toLocaleString()} tokens</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

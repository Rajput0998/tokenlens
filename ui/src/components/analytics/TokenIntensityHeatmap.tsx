import { useRef, useEffect, useState } from "react";
import * as d3 from "d3";
import { InfoTooltip } from "../home/InfoTooltip";

export interface HeatmapCell {
  hour: number; // 0-23
  day: number; // 0-6 (Mon-Sun)
  value: number;
}

interface TokenIntensityHeatmapProps {
  data: HeatmapCell[];
  loading?: boolean;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function TokenIntensityHeatmap({ data, loading }: TokenIntensityHeatmapProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 200 });

  useEffect(() => {
    const container = svgRef.current?.parentElement;
    if (container) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setDimensions({
            width: entry.contentRect.width,
            height: 200,
          });
        }
      });
      resizeObserver.observe(container);
      return () => resizeObserver.disconnect();
    }
  }, []);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 20, right: 10, bottom: 30, left: 40 };
    const width = dimensions.width - margin.left - margin.right;
    const height = dimensions.height - margin.top - margin.bottom;

    const cellWidth = width / 24;
    const cellHeight = height / 7;

    const maxValue = d3.max(data, (d) => d.value) ?? 1;

    const colorScale = d3
      .scaleSequential(d3.interpolateBlues)
      .domain([0, maxValue]);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Draw cells
    g.selectAll("rect")
      .data(data)
      .enter()
      .append("rect")
      .attr("x", (d) => d.hour * cellWidth)
      .attr("y", (d) => d.day * cellHeight)
      .attr("width", cellWidth - 1)
      .attr("height", cellHeight - 1)
      .attr("rx", 2)
      .attr("fill", (d) => (d.value > 0 ? colorScale(d.value) : "hsl(var(--muted))"))
      .on("mouseenter", function (event, d) {
        const tooltip = tooltipRef.current;
        if (tooltip) {
          tooltip.style.display = "block";
          tooltip.style.left = `${event.offsetX + 10}px`;
          tooltip.style.top = `${event.offsetY - 30}px`;
          tooltip.textContent = `${DAYS[d.day]} ${d.hour}:00 — ${d.value.toLocaleString()} tokens`;
        }
        d3.select(this).attr("stroke", "hsl(var(--foreground))").attr("stroke-width", 1);
      })
      .on("mouseleave", function () {
        const tooltip = tooltipRef.current;
        if (tooltip) tooltip.style.display = "none";
        d3.select(this).attr("stroke", "none");
      });

    // X axis (hours)
    const xScale = d3.scaleLinear().domain([0, 23]).range([0, width - cellWidth]);
    g.append("g")
      .attr("transform", `translate(${cellWidth / 2},${height + 5})`)
      .call(
        d3
          .axisBottom(xScale)
          .ticks(6)
          .tickFormat((d) => `${d}:00`)
      )
      .selectAll("text")
      .attr("fill", "hsl(var(--muted-foreground))")
      .style("font-size", "10px");

    // Y axis (days)
    DAYS.forEach((day, i) => {
      g.append("text")
        .attr("x", -5)
        .attr("y", i * cellHeight + cellHeight / 2)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("fill", "hsl(var(--muted-foreground))")
        .style("font-size", "10px")
        .text(day);
    });
  }, [data, dimensions]);

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-4 w-32 bg-muted rounded mb-4" />
        <div className="h-48 bg-muted rounded" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <p className="text-muted-foreground">
          Not enough data for the heatmap. Use AI tools for a few days to see patterns.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-4">
        <span className="flex items-center gap-2">
          Token Intensity (24×7)
          <InfoTooltip
            title="Token Intensity Heatmap"
            description="A GitHub-style heatmap showing your AI usage patterns across the week. Each cell represents one hour of one day. Darker blue means more tokens consumed during that hour. Hover over cells to see exact values."
            tips={[
              "Identify your peak coding hours and days",
              "Dark cells = heavy AI usage, light/empty = no activity",
              "Use this to plan when to tackle token-heavy tasks",
              "Patterns emerge after a few days of usage data",
            ]}
          />
        </span>
      </h3>
      <div className="relative">
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full"
        />
        <div
          ref={tooltipRef}
          className="absolute hidden bg-popover text-popover-foreground border rounded px-2 py-1 text-xs pointer-events-none shadow-md"
        />
      </div>
    </div>
  );
}

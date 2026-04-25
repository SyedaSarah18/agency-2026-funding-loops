"use client";

import { useMemo, useRef, useEffect, useState } from "react";
import dynamic from "next/dynamic";

// react-force-graph-2d touches window/canvas, so it must be client-only.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

type Charity = {
  bn: string;
  legal_name: string;
  city?: string;
  designation?: string;
};

type Edge = {
  from_bn: string;
  to_bn: string;
  total_amount: number;
  year_range?: [number, number];
};

type GraphData = {
  charities: Charity[];
  edges: Edge[];
};

type Node = {
  id: string;
  label: string;
  city: string;
  inflow: number;
  outflow: number;
  netFlow: number;
};

type Link = {
  source: string;
  target: string;
  amount: number;
  yearRange: string;
};

function fmtMoney(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function LoopGraph({ data }: { data: GraphData }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const { nodes, links } = useMemo(() => {
    const inflow: Record<string, number> = {};
    const outflow: Record<string, number> = {};
    for (const e of data.edges) {
      outflow[e.from_bn] = (outflow[e.from_bn] ?? 0) + e.total_amount;
      inflow[e.to_bn] = (inflow[e.to_bn] ?? 0) + e.total_amount;
    }
    const nodes: Node[] = data.charities.map((c) => ({
      id: c.bn,
      label: c.legal_name,
      city: c.city ?? "",
      inflow: inflow[c.bn] ?? 0,
      outflow: outflow[c.bn] ?? 0,
      netFlow: (inflow[c.bn] ?? 0) - (outflow[c.bn] ?? 0),
    }));
    const links: Link[] = data.edges.map((e) => ({
      source: e.from_bn,
      target: e.to_bn,
      amount: e.total_amount,
      yearRange: e.year_range ? `${e.year_range[0]}–${e.year_range[1]}` : "",
    }));
    return { nodes, links };
  }, [data]);

  if (!data || nodes.length === 0) {
    return (
      <div className="text-xs text-slate-500 italic">
        (no graph data available for this loop)
      </div>
    );
  }

  // Find max amount for edge-width scaling.
  const maxAmount = links.reduce((m, l) => Math.max(m, l.amount), 1);

  return (
    <div ref={wrapRef} className="w-full">
      <div className="text-xs font-bold uppercase text-slate-500 mb-2">
        Loop graph ({nodes.length} charities, {links.length} edges)
      </div>
      <div className="border border-slate-200 rounded bg-slate-50">
        <ForceGraph2D
          graphData={{ nodes, links }}
          width={width}
          height={320}
          nodeRelSize={6}
          linkColor={() => "rgba(100, 116, 139, 0.55)"}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkWidth={(l) => 1 + (((l as unknown as Link).amount / maxAmount) * 5)}
          linkLabel={(l) => {
            const link = l as unknown as Link;
            return `${fmtMoney(link.amount)} (${link.yearRange})`;
          }}
          nodeLabel={(n) => {
            const node = n as unknown as Node;
            return `${node.label} — ${node.city}\nin: ${fmtMoney(node.inflow)} | out: ${fmtMoney(node.outflow)} | net: ${fmtMoney(node.netFlow)}`;
          }}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const n = node as unknown as Node & { x: number; y: number };
            const label =
              n.label.length > 28 ? n.label.slice(0, 25) + "…" : n.label;
            const fontSize = 11 / globalScale;
            ctx.font = `${fontSize}px sans-serif`;
            // Color by net flow: green=accumulator, red=distributor, gray=neutral
            const color =
              n.netFlow > 1_000_000
                ? "#10b981"
                : n.netFlow < -1_000_000
                ? "#ef4444"
                : "#64748b";
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, 6, 0, 2 * Math.PI, false);
            ctx.fill();
            ctx.fillStyle = "#0f172a";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            ctx.fillText(label, n.x, n.y + 8);
          }}
          cooldownTicks={80}
        />
      </div>
      <div className="mt-2 flex items-center gap-4 text-xs text-slate-600">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500" />
          net accumulator (money lands here)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500" />
          net distributor (money leaves)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-slate-500" />
          balanced
        </span>
      </div>
    </div>
  );
}

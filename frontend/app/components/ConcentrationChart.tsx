"use client";

import { useMemo } from "react";

type Recipient = {
  name: string;
  bn?: string | null;
  amount: number;
  agreement_count?: number;
  share_of_program: number;
};

type TimePoint = {
  year: number;
  total_spend: number;
  top_vendor_share: number;
};

type TopVendor = {
  name?: string;
  bn?: string | null;
  entity_type?: string;
  fed_total_all_programs?: number;
};

type ChartData = {
  program?: string;
  dept?: string;
  recipients?: Recipient[];
  time_series?: TimePoint[];
  top_vendor?: TopVendor;
};

function fmtMoney(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function ConcentrationChart({ data }: { data: ChartData }) {
  const recipients = (data.recipients ?? []).slice(0, 8);
  const timeSeries = data.time_series ?? [];

  const maxAmount = useMemo(
    () => recipients.reduce((m, r) => Math.max(m, r.amount), 1),
    [recipients]
  );

  const maxYearTotal = useMemo(
    () => timeSeries.reduce((m, t) => Math.max(m, t.total_spend), 1),
    [timeSeries]
  );

  if (recipients.length === 0 && timeSeries.length === 0) {
    return null;
  }

  return (
    <div className="space-y-5">
      {recipients.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase text-slate-500 mb-2">
            Recipient breakdown ({recipients.length} of {data.recipients?.length ?? 0})
          </div>
          <div className="space-y-1.5">
            {recipients.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className="w-48 shrink-0 truncate" title={r.name}>
                  {i === 0 && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5" />
                  )}
                  <span className={i === 0 ? "font-semibold text-slate-900" : "text-slate-700"}>
                    {r.name}
                  </span>
                </div>
                <div className="flex-1 bg-slate-100 rounded-sm h-5 relative overflow-hidden">
                  <div
                    className={`absolute inset-y-0 left-0 ${
                      i === 0 ? "bg-amber-400" : "bg-slate-400"
                    }`}
                    style={{
                      width: `${Math.max((r.amount / maxAmount) * 100, 1)}%`,
                    }}
                  />
                  <div className="absolute inset-0 flex items-center justify-end px-2 text-xs font-mono text-slate-900 mix-blend-difference">
                    {fmtMoney(r.amount)} ({(r.share_of_program * 100).toFixed(1)}%)
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {timeSeries.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase text-slate-500 mb-2">
            Annual program spend
          </div>
          <div className="flex items-end gap-2 h-24">
            {timeSeries.map((t, i) => (
              <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1">
                <div
                  className="w-full bg-slate-300 rounded-t-sm relative"
                  style={{
                    height: `${Math.max((t.total_spend / maxYearTotal) * 90, 4)}%`,
                  }}
                >
                  <div
                    className="absolute inset-x-0 bottom-0 bg-amber-400 rounded-t-sm"
                    style={{ height: `${(t.top_vendor_share ?? 0) * 100}%` }}
                    title={`top vendor share: ${((t.top_vendor_share ?? 0) * 100).toFixed(1)}%`}
                  />
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {t.year}
                </div>
                <div className="text-[10px] text-slate-700 font-mono">
                  {fmtMoney(t.total_spend)}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-1 flex items-center gap-4 text-[10px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-2 h-2 bg-amber-400" /> top vendor
              share
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2 h-2 bg-slate-300" /> rest of
              program
            </span>
          </div>
        </div>
      )}

      {data.top_vendor?.fed_total_all_programs ? (
        <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded p-2">
          <span className="font-semibold">{data.top_vendor.name}</span>{" "}
          received{" "}
          <span className="font-mono font-semibold">
            {fmtMoney(data.top_vendor.fed_total_all_programs)}
          </span>{" "}
          in total federal funding across all programs
          {data.top_vendor.entity_type
            ? ` · entity type: ${data.top_vendor.entity_type}`
            : ""}
          .
        </div>
      ) : null}
    </div>
  );
}

"use client";

import { useState } from "react";

export default function Explainer() {
  const [open, setOpen] = useState(true);

  return (
    <div className="mb-6 bg-white border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-slate-50 transition"
      >
        <span className="font-semibold text-slate-900">
          What this investigates {open ? "" : "(click to expand)"}
        </span>
        <span className="text-slate-500 font-mono text-sm">
          {open ? "−" : "+"}
        </span>
      </button>
      {open && (
        <div className="px-5 pb-5 text-sm text-slate-700 space-y-3 border-t border-slate-200 pt-4">
          <p>
            Every Canadian charity must file an annual T3010 with the CRA disclosing
            every gift it made to another charity.{" "}
            <span className="font-semibold">5,808 cycles</span> exist in 2020-2024
            data where money flowed A → B → ... → A in a closed loop. Total volume
            in cross-entity cycles ≥ $100K:{" "}
            <span className="font-semibold">$2.86 billion</span>.
          </p>
          <p>
            <span className="font-semibold">Why it matters:</span> looped charity
            transfers can inflate reported revenue (each hop counts as new
            revenue), distort tax-receipt mechanics, and let charities reclassify
            admin costs as program costs. Most cycles are legitimate (denominational
            pooling, donor-advised-fund migrations) — but the ones that aren&apos;t
            cost taxpayers and undermine public trust in charitable status.
          </p>
          <p>
            <span className="font-semibold">What runs on click:</span> four AI
            agents in sequence — Discovery scans the cycle table for the highest-
            flow cross-entity loops; Investigation pulls each cycle&apos;s charities,
            edges, directors, and external grant exposure into a dossier; Validator
            calls{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">verify_*</code> tools
            against source rows to confirm dollar amounts, director relationships,
            and revenue figures (downgrades the verdict if any verification fails);
            Narrative writes a Minister-ready brief whose every number is traceable
            to a database row.
          </p>
          <p>
            <span className="font-semibold">Why this challenge over the other 9:</span>{" "}
            empirical scorecard at{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">analysis/scorecard.md</code>{" "}
            — Funding Loops scored 18/20 because the data is clean, the math is
            deterministic (no LLM-hallucinated relationships), the cycles are
            visualizable, and every named entity is recognizable.
          </p>
        </div>
      )}
    </div>
  );
}

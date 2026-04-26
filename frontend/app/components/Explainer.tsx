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
            <span className="font-semibold">The challenge (verbatim):</span>{" "}
            <em>
              &quot;In any given category of government spending, how many
              vendors are actually competing? Identify areas where a single
              supplier or a small group of suppliers receives a disproportionate
              share of contracts. Where has incumbency replaced competition?
              Where has government become dependent on a vendor it can no
              longer walk away from?&quot;
            </em>
          </p>
          <p>
            <span className="font-semibold">Our data:</span>{" "}
            <span className="font-semibold">15,533 Alberta sole-source contracts</span>{" "}
            from <code className="bg-slate-100 px-1 rounded text-xs">ab.ab_sole_source</code>{" "}
            ($18.2B total, 2014-2025) — money the government spent without
            competitive bidding. Plus 67K rows of broader Alberta procurement.
            We pre-compute a <span className="font-semibold">Procurement Concentration Atlas</span>{" "}
            (3 parquet tables) ranking every (ministry × category) combination
            by a composite risk score combining dollar magnitude, top-1 vendor
            share, vendor scarcity, and cross-ministry lock-in breadth.
          </p>
          <p>
            <span className="font-semibold">Two operating modes:</span>
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-slate-700 ml-2">
            <li>
              <span className="font-semibold">Run Investigation</span> — 4
              agents (Discovery → Investigation → Validator → Narrative) read
              from the Atlas and produce ranked Minister briefs. The Validator
              calls{" "}
              <code className="bg-slate-100 px-1 rounded text-xs">verify_concentration_share</code>{" "}
              and{" "}
              <code className="bg-slate-100 px-1 rounded text-xs">verify_vendor_ministry_count</code>{" "}
              against source rows and downgrades verdict if any verification fails.
            </li>
            <li>
              <span className="font-semibold">Conductor chat</span> — type any
              question. A single agent reasons about which tools the question
              needs (Atlas reads, code_compute pandas sandbox, knowledge base,
              raw SQL fallback) and answers with sources. Says &quot;I don&apos;t
              know&quot; when the data doesn&apos;t support an answer.
            </li>
          </ul>
          <p>
            <span className="font-semibold">Headline findings already in the data:</span>{" "}
            $1.48B Alberta Blue Cross benefit administration (100% sole-source);
            $60M 2025-2030 Microsoft Azure cloud agreement (5-year sole-source);
            three separate IBM Canada enterprise monopolies ($129M combined for
            software licensing, mainframe hosting, IMAGIS); IBM is the
            single most cross-embedded vendor at 20 ministries / lockin score
            72.4 (top 1%).
          </p>
          <p>
            <span className="font-semibold">Defensibility:</span> every
            threshold derived from data percentiles, not magic numbers
            (see <code className="bg-slate-100 px-1 rounded text-xs">analysis/atlas/baselines.py</code>).
            8/8 known true-positive monopolies pass the regression eval
            (<code className="bg-slate-100 px-1 rounded text-xs">analysis/atlas/known_cases.py</code>).
            Empirical scorecard at{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">analysis/scorecard.md</code>.
          </p>
        </div>
      )}
    </div>
  );
}

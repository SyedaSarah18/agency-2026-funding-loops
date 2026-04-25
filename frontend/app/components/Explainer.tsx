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
            The federal government discloses every grant and contribution it
            issues — recipient, dollar amount, program, department, dates. Our
            scan of <span className="font-semibold">1.28M federal records</span>{" "}
            since 2020 found{" "}
            <span className="font-semibold">2,365 spending programs</span> where{" "}
            <span className="font-semibold">
              one recipient receives 80% or more of the program&apos;s total
              spend
            </span>
            . Most are legitimate (designated organisations under treaty,
            named-recipient programs, intergovernmental transfers). But some are
            real concerns — Sustainable Development Technology Canada (the 2024
            Auditor General-flagged &quot;green slush fund&quot;) is in our
            data.
          </p>
          <p>
            <span className="font-semibold">Why it matters:</span> when a single
            vendor dominates a federal program with no competitive process, the
            risks are well-documented — non-arm&apos;s-length governance, scope
            creep, no benchmarking, and an audit trail the public can&apos;t see
            through. Surfacing these patterns at scale lets the Treasury Board
            triage which programs deserve a deeper look before money continues
            flowing.
          </p>
          <p>
            <span className="font-semibold">What runs on click:</span> four AI
            agents in sequence — Discovery scans federal grants for
            single-recipient-dominated programs (filtering out named-recipient
            programs like Mitacs Inc. that are legitimately single-vendor by
            design); Investigation builds the program&apos;s full recipient
            roster, time series, and the dominant vendor&apos;s broader federal
            footprint; Validator calls{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">
              verify_program_concentration
            </code>{" "}
            and{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">
              verify_vendor_federal_total
            </code>{" "}
            against source rows, rules out designated/legitimate single-vendor
            patterns, and downgrades the verdict if any verification fails;
            Narrative writes a Minister-ready brief whose every number is
            traceable to a database row.
          </p>
          <p>
            <span className="font-semibold">
              Why this challenge over the other 9:
            </span>{" "}
            empirical scorecard at{" "}
            <code className="bg-slate-100 px-1 rounded text-xs">
              analysis/scorecard.md
            </code>{" "}
            — Vendor Concentration scored 17/20 after a deep re-probe (the
            original probe undercounted by 100×). The data is rich (2,365
            candidates), the deterministic math is defensible, the architecture
            generalises across challenges, and the SDTC + Greener Homes
            placeholder findings are concrete and politically resonant.
          </p>
        </div>
      )}
    </div>
  );
}

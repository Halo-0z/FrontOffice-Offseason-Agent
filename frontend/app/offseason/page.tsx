"use client";

/**
 * Offseason proposal viewer page.
 *
 * M6-A static frontend viewer. Renders two static demo scenarios
 * (default recommendation + strict-budget fallback) using the
 * ProposalViewer component. No API calls, no LLM, no MCP, no data
 * mutation. All data is sample / simulation JSON.
 *
 * Milestone: M6-A.
 */

import { useState } from "react";
import ProposalViewer from "../../components/ProposalViewer";
import { scenarios } from "../../data/demoProposalPayload";

export default function OffseasonPage() {
  const [activeScenarioId, setActiveScenarioId] = useState(scenarios[0].id);
  const activeScenario =
    scenarios.find((s) => s.id === activeScenarioId) ?? scenarios[0];

  return (
    <main
      style={{
        padding: 24,
        fontFamily: "system-ui, sans-serif",
        maxWidth: 1100,
        margin: "0 auto",
      }}
    >
      {/* Header */}
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>FrontOffice-Offseason-Agent</h1>
        <p style={{ color: "#666", margin: "4px 0 0 0" }}>
          Demo Preview — NBA offseason front-office decision workflow.
        </p>
        <div
          style={{
            marginTop: 8,
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              background: "#fef3c7",
              color: "#92400e",
              border: "1px solid #fcd34d",
            }}
          >
            sample data
          </span>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              background: "#dbeafe",
              color: "#1e40af",
              border: "1px solid #93c5fd",
            }}
          >
            preview only
          </span>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              background: "#fee2e2",
              color: "#991b1b",
              border: "1px solid #fca5a5",
            }}
          >
            requires human approval
          </span>
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              fontSize: 12,
              background: "#f3f4f6",
              color: "#374151",
              border: "1px solid #d1d5db",
            }}
          >
            no LLM · no MCP · no external NBA API
          </span>
        </div>
      </header>

      {/* Scenario Tabs */}
      <div
        style={{
          display: "flex",
          gap: 8,
          borderBottom: "2px solid #ddd",
          marginBottom: 16,
        }}
      >
        {scenarios.map((scenario) => {
          const isActive = scenario.id === activeScenarioId;
          return (
            <button
              key={scenario.id}
              onClick={() => setActiveScenarioId(scenario.id)}
              style={{
                padding: "8px 16px",
                border: "none",
                background: isActive ? "#111" : "transparent",
                color: isActive ? "#fff" : "#111",
                cursor: "pointer",
                borderRadius: "4px 4px 0 0",
                fontSize: 14,
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {scenario.label}
            </button>
          );
        })}
      </div>

      {/* Active Scenario Description */}
      <div
        style={{
          padding: 12,
          background: "#f9fafb",
          borderRadius: 6,
          fontSize: 13,
          color: "#4b5563",
        }}
      >
        <strong>Scenario:</strong> {activeScenario.description}
      </div>

      {/* Proposal Viewer */}
      <ProposalViewer payload={activeScenario.payload} />

      {/* Footer */}
      <footer
        style={{
          marginTop: 32,
          paddingTop: 16,
          borderTop: "1px solid #ddd",
          color: "#666",
          fontSize: 12,
        }}
      >
        <p>
          M6-A static frontend viewer. All data is sample / simulation
          JSON. No LLM, no MCP, no external NBA API, no data mutation.
          Every action is a preview that requires human approval.
        </p>
        <p>
          Payload source:{" "}
          <code>
            python backend/scripts/run_offseason_demo.py --format json
          </code>
        </p>
      </footer>
    </main>
  );
}

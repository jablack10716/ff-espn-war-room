"use client";

import React from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { Cpu, Lightbulb, Loader2, Sparkles } from "lucide-react";

export const AgentAdvisoryPanel: React.FC = () => {
  const { agentAdvisories, adaRankings, triggerDebate, isDeliberating } = useDraftStore();

  const topPick = agentAdvisories?.top_3_picks?.[0] || null;
  const topAdaPlayer = adaRankings[0] || null;

  const targetName = topPick?.player_name || topAdaPlayer?.full_name || topAdaPlayer?.player_name || "Top Target";
  const targetPos = topPick?.position || topAdaPlayer?.position || "FLEX";

  // Fallback status helpers
  const isFallbackUsed = agentAdvisories?.fallback_used ?? true;
  const isMarcusFallback = agentAdvisories?.marcus_fallback ?? true;
  const isWinstonFallback = agentAdvisories?.winston_fallback ?? true;

  const marcusPitch = topPick?.marcus_upside || agentAdvisories?.marcus_notes?.[topAdaPlayer?.player_id || ""] || null;
  const winstonPitch = topPick?.winston_need || agentAdvisories?.winston_notes?.[topAdaPlayer?.player_id || ""] || null;
  const arthurReasoning = agentAdvisories?.reasoning_2_sentences || topPick?.arthur_reasoning || null;

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-indigo-900/40 bg-gradient-to-b from-indigo-950/30 via-slate-900/80 to-slate-950 p-4 backdrop-blur-xl shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-indigo-900/40 pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-indigo-400" />
          <h2 className="text-base font-extrabold text-white tracking-wide">GOOGLE ANTIGRAVITY AGENT POOL</h2>
        </div>
        <span className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-semibold text-indigo-400 border border-indigo-500/20 flex items-center gap-1">
          <Sparkles className="h-3 w-3" /> Async Fan-Out Synthesis
        </span>
      </div>

      {/* Target Focus Banner */}
      <div className="rounded-xl border border-indigo-800/50 bg-indigo-950/50 p-3 flex items-center justify-between shadow-inner">
        <div>
          <span className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider">CONSENSUS TOP TARGET</span>
          <h3 className="text-base font-black text-white">{targetName} ({targetPos})</h3>
        </div>
        <span className="rounded-lg bg-indigo-500/20 px-3 py-1 text-xs font-bold text-indigo-300 border border-indigo-500/30">
          RANK #1 TARGET
        </span>
      </div>

      {/* Manual Trigger Button */}
      <div className="w-full">
        <button
          onClick={() => triggerDebate()}
          disabled={isDeliberating}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 py-2.5 text-xs font-extrabold text-white hover:from-indigo-500 hover:to-violet-500 transition shadow disabled:opacity-50"
        >
          {isDeliberating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Agents Deliberating (Upside, Roster & GM)...
            </>
          ) : (
            <>
              <span>🤖 Trigger War Room Agent Debate</span>
            </>
          )}
        </button>
      </div>

      {/* Agent Cards */}
      <div className="flex flex-col gap-3">
        {/* Marcus Scout Card */}
        <div className="rounded-xl border border-amber-900/40 bg-slate-950/70 p-3.5 shadow-sm">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-amber-500/20 text-amber-400 font-bold text-xs">
                M
              </div>
              <span className="text-xs font-extrabold text-amber-300 uppercase tracking-wide">MARCUS • CHIEF SCOUT</span>
            </div>
            {agentAdvisories && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                isMarcusFallback
                  ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
                  : "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
              }`}>
                {isMarcusFallback ? "TEMPLATE FALLBACK" : "🤖 AI GENERATED"}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 leading-relaxed italic border-l-2 border-amber-500/60 pl-2.5">
            {marcusPitch ? `“${marcusPitch}”` : "No scouting notes loaded. Trigger the debate to delibrate."}
          </p>
        </div>

        {/* Winston Architect Card */}
        <div className="rounded-xl border border-teal-900/40 bg-slate-950/70 p-3.5 shadow-sm">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-teal-500/20 text-teal-400 font-bold text-xs">
                W
              </div>
              <span className="text-xs font-extrabold text-teal-300 uppercase tracking-wide">WINSTON • ROSTER ARCHITECT</span>
            </div>
            {agentAdvisories && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                isWinstonFallback
                  ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
                  : "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
              }`}>
                {isWinstonFallback ? "TEMPLATE FALLBACK" : "🤖 AI GENERATED"}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-300 leading-relaxed italic border-l-2 border-teal-500/60 pl-2.5">
            {winstonPitch ? `“${winstonPitch}”` : "No roster architecture notes loaded. Trigger the debate to deliberate."}
          </p>
        </div>

        {/* Arthur GM Terminal Card */}
        <div className="rounded-xl border border-indigo-500/50 bg-indigo-950/40 p-4 shadow-md">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-indigo-500 text-slate-950 font-black text-xs shadow-md">
                A
              </div>
              <span className="text-xs font-extrabold text-indigo-200 uppercase tracking-wider">ARTHUR • GENERAL MANAGER TERMINAL</span>
            </div>
            {agentAdvisories && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                isFallbackUsed
                  ? "bg-amber-500/5 border-amber-500/20 text-amber-400"
                  : "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
              }`}>
                {isFallbackUsed ? "TEMPLATE FALLBACK" : "🤖 AI GENERATED"}
              </span>
            )}
          </div>

          <div className="rounded-lg border border-indigo-900/60 bg-slate-950/80 p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400 border-b border-indigo-900/40 pb-1.5">
              <Lightbulb className="h-4 w-4 text-amber-400 animate-pulse" />
              <span>Key Deciding Factors (Draft Talking Points)</span>
            </div>
            <p className="text-xs font-medium text-indigo-100 leading-relaxed">
              {arthurReasoning || "General Manager strategy synthesis pending. Click debate to trigger."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

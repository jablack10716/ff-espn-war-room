"use client";

import React from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { Award, ChevronRight } from "lucide-react";
import { Player } from "../types/draft";

export const AdaRecommendations: React.FC = () => {
  const { adaRankings, recordPick, isSubmitting, isUserOnClock } = useDraftStore();

  const top10 = adaRankings.slice(0, 10);

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-xl shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Award className="h-5 w-5 text-emerald-400" />
          <h2 className="text-base font-extrabold text-white tracking-wide">ADA TOP QUANT PICKS</h2>
        </div>
        <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
          Pure Deterministic Math
        </span>
      </div>

      <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[600px] pr-1">
        {top10.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">No recommended players available.</div>
        ) : (
          top10.map((player: Player, index: number) => {
            const name = player.full_name || player.player_name || "Unknown";
            const breakdown = player.breakdown || {};
            const vorp = breakdown.vor_raw !== undefined ? breakdown.vor_raw.toFixed(1) : "0.0";
            const oc = breakdown.oc_raw !== undefined ? breakdown.oc_raw.toFixed(1) : "0.0";
            const isTopRank = index === 0;

            return (
              <div
                key={player.player_id}
                className={`group relative flex flex-col gap-2 rounded-xl border p-3.5 transition-all ${
                  isTopRank
                    ? "border-emerald-500/50 bg-gradient-to-r from-emerald-950/40 via-slate-900 to-slate-900 shadow-md shadow-emerald-500/10"
                    : "border-slate-800/80 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/80"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-lg text-xs font-black ${
                        isTopRank ? "bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/40" : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      #{index + 1}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm group-hover:text-emerald-300 transition">{name}</span>
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-bold text-slate-300">
                          {player.position}
                        </span>
                        <span className="text-xs text-slate-400">{player.team || "FA"}</span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span>ADP: {player.adp ? player.adp : "N/A"}</span>
                        <span>•</span>
                        <span>Proj: {player.projection_median ? player.projection_median.toFixed(1) : "0.0"} pts</span>
                      </div>
                      {player.data_sources && player.data_sources.length > 0 && (
                        <div className="mt-1 flex flex-wrap items-center gap-1">
                          {player.data_sources.map((src: string) => {
                            const labelMap: Record<string, string> = {
                              espn: "ESPN",
                              sleeper: "Sleeper",
                              fantasypros: "FantasyPros",
                              underdog: "Underdog ADP",
                              underdog_adp: "Underdog ADP",
                              vegas: "Vegas Props",
                              vegas_props: "Vegas Props",
                              high_stakes: "ETR/PFF",
                              advanced: "AirYards/xFP",
                              advanced_metrics: "AirYards/xFP",
                            };
                            return (
                              <span key={src} className="rounded bg-slate-800/90 border border-slate-700/60 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400">
                                {labelMap[src] || src}
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => recordPick(player.player_id, isUserOnClock)}
                    disabled={isSubmitting}
                    className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow hover:bg-emerald-500 transition active:scale-95 disabled:opacity-50"
                  >
                    Draft <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>

                {/* Metrics Row: VORP, OC Delta, Score */}
                <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-900/90 p-2 text-xs border border-slate-800/60 mt-1">
                  <div>
                    <span className="block text-[10px] text-slate-500 font-bold uppercase">Positional VORP</span>
                    <span className="font-bold text-emerald-400">+{vorp} pts</span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-slate-500 font-bold uppercase">Opp Cost Delta</span>
                    <span className={`font-bold ${parseFloat(oc) >= 0 ? "text-teal-400" : "text-amber-400"}`}>
                      {parseFloat(oc) >= 0 ? `+${oc}` : oc} pts
                    </span>
                  </div>
                  <div>
                    <span className="block text-[10px] text-slate-500 font-bold uppercase">Ada Score</span>
                    <span className="font-bold text-white">{player.composite_score !== undefined ? player.composite_score : "N/A"}</span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

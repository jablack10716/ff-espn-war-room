"use client";

import React from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { History, Users } from "lucide-react";

export const RosterGrid: React.FC = () => {
  const { rosterByPosition, userRoster, draftLog } = useDraftStore();

  const slots = [
    { key: "QB", label: "STARTER QB", count: 1 },
    { key: "RB", label: "STARTER RB", count: 2 },
    { key: "WR", label: "STARTER WR", count: 2 },
    { key: "TE", label: "STARTER TE", count: 1 },
    { key: "FLEX", label: "FLEX (RB/WR/TE)", count: 1 },
    { key: "SUPERFLEX", label: "SUPERFLEX", count: 1 },
    { key: "BENCH", label: "BENCH SLOTS", count: 7 },
  ];

  // Calculate bye weeks in roster to highlight conflicts
  const byeWeekCounts: Record<number, number> = {};
  userRoster.forEach((p) => {
    const bye = (p as unknown as { bye_week?: number }).bye_week;
    if (bye) {
      byeWeekCounts[bye] = (byeWeekCounts[bye] || 0) + 1;
    }
  });

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-xl shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-emerald-400" />
          <h2 className="text-base font-extrabold text-white tracking-wide">MY ROSTER GRID</h2>
        </div>
        <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-semibold text-slate-300">
          {userRoster.length} Players Drafted
        </span>
      </div>

      {/* Roster Categories */}
      <div className="flex flex-col gap-3">
        {slots.map((s) => {
          const players = rosterByPosition[s.key] || [];

          return (
            <div key={s.key} className="rounded-xl border border-slate-800 bg-slate-950/70 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider">{s.label}</span>
                <span className="text-[10px] font-bold text-slate-500">{players.length} Filled</span>
              </div>

              {players.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-850 p-2 text-center text-xs text-slate-600">
                  Empty Slot
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {players.map((p) => {
                    const bye = (p as unknown as { bye_week?: number }).bye_week;
                    const hasConflict = bye && byeWeekCounts[bye] >= 3;

                    return (
                      <div
                        key={`${p.pick_no}-${p.player_id}`}
                        className={`flex items-center justify-between rounded-lg p-2 text-xs border ${
                          hasConflict
                            ? "border-amber-900/60 bg-amber-950/30 text-amber-200"
                            : "border-slate-800 bg-slate-900/90 text-slate-200"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-emerald-400">R{p.round_no}</span>
                          <span className="font-bold text-white">{p.player_name}</span>
                          <span className="text-[10px] font-semibold text-slate-400">{p.position}</span>
                        </div>

                        {bye && (
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${hasConflict ? "bg-amber-500/20 text-amber-300" : "bg-slate-800 text-slate-400"}`}>
                            BYE {bye}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Mini Draft Log Timeline */}
      <div className="mt-2 flex flex-col gap-2 border-t border-slate-800 pt-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-extrabold uppercase text-slate-300">Draft History ({draftLog.length} picks)</span>
        </div>

        <div className="max-h-48 overflow-y-auto flex flex-col gap-1.5 pr-1 text-xs">
          {draftLog.length === 0 ? (
            <div className="p-3 text-center text-slate-500">No picks logged yet.</div>
          ) : (
            [...draftLog].reverse().map((pick) => (
              <div
                key={`${pick.pick_no}-${pick.player_id}`}
                className={`flex items-center justify-between rounded-lg px-3 py-1.5 border ${
                  pick.picked_by_user
                    ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-300"
                    : "border-slate-800 bg-slate-950 text-slate-400"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold">#{pick.pick_no}</span>
                  <span className="font-medium text-white">{pick.player_name}</span>
                  <span className="text-[10px] text-slate-500">({pick.position})</span>
                </div>
                <span className="text-[10px] font-semibold">
                  {pick.picked_by_user ? "★ User" : `Team ${pick.team_slot}`}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

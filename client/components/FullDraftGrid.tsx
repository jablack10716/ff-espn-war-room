"use client";

import React, { useState, useMemo } from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { Edit3, Trash2, X, Search } from "lucide-react";

export const FullDraftGrid: React.FC = () => {
  const {
    draftLog,
    adaRankings,
    espnTeams,
    numTeams,
    userTeamSlot,
    is3rr,
    recordPick,
    deletePick,
  } = useDraftStore();

  const [activePickNo, setActivePickNo] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPlayerId, setSelectedPlayerId] = useState("");

  const totalRounds = 16;

  // Helper pick calculation logic
  const getPickNo = (roundNo: number, teamSlot: number) => {
    let isReverse = false;
    if (is3rr) {
      if (roundNo === 1) isReverse = false;
      else if (roundNo === 2 || roundNo === 3) isReverse = true;
      else isReverse = (roundNo % 2 === 1);
    } else {
      isReverse = (roundNo % 2 === 0);
    }
    const pickInRound = isReverse ? (numTeams - teamSlot + 1) : teamSlot;
    return (roundNo - 1) * numTeams + pickInRound;
  };

  // Helper round and slot from pick number
  const getRoundAndSlot = (pickNo: number) => {
    const roundNo = Math.floor((pickNo - 1) / numTeams) + 1;
    const posInRound = (pickNo - 1) % numTeams;
    let isReverse = false;
    if (is3rr) {
      if (roundNo === 1) isReverse = false;
      else if (roundNo === 2 || roundNo === 3) isReverse = true;
      else isReverse = (roundNo % 2 === 1);
    } else {
      isReverse = (roundNo % 2 === 0);
    }
    const teamSlot = isReverse ? (numTeams - posInRound) : (posInRound + 1);
    return { roundNo, teamSlot };
  };

  // Resolve team names mapping
  const slotToName = useMemo(() => {
    const mapping: Record<number, string> = {};
    for (let s = 1; s <= numTeams; s++) {
      mapping[s] = `Team ${s}`;
    }
    espnTeams.forEach((t) => {
      mapping[t.team_slot] = t.team_name;
    });
    return mapping;
  }, [espnTeams, numTeams]);

  // Index draft log
  const pickMap = useMemo(() => {
    const mapping: Record<number, typeof draftLog[0]> = {};
    draftLog.forEach((e) => {
      if (e.event_type === "PICK") {
        mapping[e.pick_no] = e;
      }
    });
    return mapping;
  }, [draftLog]);

  // Summary Metrics
  const totalPicksPossible = numTeams * totalRounds;
  const picksLogged = Object.keys(pickMap).length;
  const progressPct = totalPicksPossible > 0 ? ((picksLogged / totalPicksPossible) * 100).toFixed(1) : "0.0";
  const userPicksCount = Object.values(pickMap).filter((p) => p.picked_by_user).length;
  const keepersCount = Object.values(pickMap).filter((p) => p.source === "keeper" || p.notes === "Pre-draft keeper").length;

  // Shorten player name for compact grid cell representation
  const formatShortName = (fullName: string) => {
    const parts = fullName.split(" ");
    if (parts.length >= 2 && !parts[0].endsWith(".")) {
      return `${parts[0][0]}. ${parts.slice(1).join(" ")}`;
    }
    return fullName;
  };

  // Color sticker based on position
  const getPosColorClass = (pos: string) => {
    const p = pos.toUpperCase();
    if (p === "QB") return "bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20";
    if (p === "RB") return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20";
    if (p === "WR") return "bg-blue-500/10 border-blue-500/30 text-blue-400 hover:bg-blue-500/20";
    if (p === "TE") return "bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20";
    if (p === "DST" || p === "D/ST") return "bg-purple-500/10 border-purple-500/30 text-purple-400 hover:bg-purple-500/20";
    return "bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-800";
  };

  // Filter available players for overlay edit select
  const filteredSearchPlayers = useMemo(() => {
    if (!searchQuery.trim()) return adaRankings.slice(0, 50);
    const q = searchQuery.toLowerCase().trim();
    return adaRankings.filter((p) => {
      const name = (p.full_name || p.player_name || "").toLowerCase();
      const pos = p.position.toLowerCase();
      const team = p.team.toLowerCase();
      return name.includes(q) || pos.includes(q) || team.includes(q);
    });
  }, [searchQuery, adaRankings]);

  const activeEvent = activePickNo !== null ? pickMap[activePickNo] : null;
  const activeDetails = activePickNo !== null ? getRoundAndSlot(activePickNo) : null;
  const activeTeamName = activeDetails ? slotToName[activeDetails.teamSlot] : "";

  const handleSavePick = async () => {
    if (activePickNo === null || !selectedPlayerId) return;
    const { teamSlot } = getRoundAndSlot(activePickNo);
    const isUserTurn = teamSlot === userTeamSlot;
    await recordPick(selectedPlayerId, isUserTurn, activePickNo, teamSlot);
    setSelectedPlayerId("");
    setSearchQuery("");
    setActivePickNo(null);
  };

  const handleClearPick = async () => {
    if (activePickNo === null) return;
    await deletePick(activePickNo);
    setSelectedPlayerId("");
    setSearchQuery("");
    setActivePickNo(null);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* ── 1. SUMMARY METRICS ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3 shadow-sm">
          <span className="block text-[9px] uppercase font-bold text-slate-500">Total Picks Logged</span>
          <span className="text-base font-extrabold text-white">{picksLogged} / {totalPicksPossible}</span>
        </div>
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3 shadow-sm">
          <span className="block text-[9px] uppercase font-bold text-slate-500">Draft Progress</span>
          <span className="text-base font-extrabold text-emerald-400">{progressPct}%</span>
        </div>
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3 shadow-sm">
          <span className="block text-[9px] uppercase font-bold text-slate-500">User Roster Picks</span>
          <span className="text-base font-extrabold text-teal-400">{userPicksCount}</span>
        </div>
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-3 shadow-sm">
          <span className="block text-[9px] uppercase font-bold text-slate-500">Pre-Draft Keepers</span>
          <span className="text-base font-extrabold text-amber-400">{keepersCount}</span>
        </div>
      </div>

      {/* ── 2. BOARD GRID TABLE (Optimized to fit on 1 Page) ─────────────────────── */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-2.5 backdrop-blur-xl shadow-lg w-full">
        <table className="w-full table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-slate-800">
              <th className="py-2 px-1 text-[9px] font-black text-slate-500 w-[6%] uppercase truncate text-center">Rnd</th>
              {Array.from({ length: numTeams }, (_, i) => {
                const slot = i + 1;
                const name = slotToName[slot] || `Slot ${slot}`;
                const isUser = slot === userTeamSlot;
                return (
                  <th key={slot} className={`py-2 px-0.5 text-[9px] font-extrabold w-[7.8%] truncate text-center uppercase tracking-tighter ${isUser ? "text-emerald-400" : "text-slate-400"}`}>
                    S{slot}: {name}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: totalRounds }, (_, rIdx) => {
              const roundNo = rIdx + 1;
              return (
                <tr key={roundNo} className="border-b border-slate-850 hover:bg-slate-900/10">
                  <td className="py-1 px-1 text-[9px] font-bold text-slate-400 text-center truncate">R{roundNo}</td>
                  {Array.from({ length: numTeams }, (_, sIdx) => {
                    const teamSlot = sIdx + 1;
                    const pickNo = getPickNo(roundNo, teamSlot);
                    const event = pickMap[pickNo];

                    if (event) {
                      const isUser = event.picked_by_user;
                      const isKeeper = event.source === "keeper" || event.notes === "Pre-draft keeper";
                      const label = formatShortName(event.player_name);
                      return (
                        <td key={teamSlot} className="py-1 px-0.5">
                          <button
                            onClick={() => {
                              setSelectedPlayerId("");
                              setActivePickNo(pickNo);
                            }}
                            className={`w-full flex flex-col justify-center items-center rounded border px-1 py-0.5 text-[9px] font-medium leading-none transition select-none h-8 text-center ${getPosColorClass(
                              event.position
                            )} ${isUser ? "ring-1 ring-emerald-500/50" : ""} ${isKeeper ? "ring-1 ring-amber-500/40" : ""}`}
                          >
                            <span className="font-extrabold text-white truncate max-w-full block text-center leading-tight">
                              {isKeeper && "🔒"}
                              {label}
                            </span>
                            <span className="text-[7px] font-extrabold opacity-75 uppercase block text-center tracking-tighter mt-0.5">
                              #{pickNo} • {event.position}
                            </span>
                          </button>
                        </td>
                      );
                    } else {
                      return (
                        <td key={teamSlot} className="py-1 px-0.5">
                          <button
                            onClick={() => {
                              setSelectedPlayerId("");
                              setActivePickNo(pickNo);
                            }}
                            className="w-full flex items-center justify-center rounded border border-slate-800/80 bg-slate-950/40 text-[9px] font-semibold text-slate-600 hover:border-slate-700 hover:bg-slate-900/60 hover:text-slate-400 transition h-8"
                          >
                            #{pickNo}
                          </button>
                        </td>
                      );
                    }
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── 3. EDIT MODAL OVERLAY ────────────────────────────────────────────── */}
      {activePickNo !== null && activeDetails !== null && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-md">
          <div className="relative w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="h-4 text-emerald-400" />
                <h3 className="text-sm font-black text-white">✏️ Manage Pick #{activePickNo}</h3>
              </div>
              <button
                onClick={() => {
                  setActivePickNo(null);
                  setSelectedPlayerId("");
                }}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-1.5 text-xs text-slate-300">
              <div>Round: <strong className="text-white">{activeDetails.roundNo}</strong></div>
              <div>Team Slot: <strong className="text-emerald-400">{activeDetails.teamSlot}</strong></div>
              <div>Owner: <strong className="text-white">{activeTeamName}</strong></div>
            </div>

            {/* Current Drafted Player Banner */}
            {activeEvent && (
              <div className="mt-4 rounded-xl border border-indigo-900/40 bg-indigo-950/20 p-3 text-xs flex justify-between items-center text-slate-200">
                <div>
                  <span className="block text-[9px] uppercase font-bold text-indigo-400">Current Player</span>
                  <span className="font-bold text-white text-sm">{activeEvent.player_name}</span>
                  <span className="text-[10px] text-slate-400 ml-2">({activeEvent.position} - {activeEvent.team_name || "FA"})</span>
                </div>
                <button
                  type="button"
                  onClick={handleClearPick}
                  className="flex items-center gap-1 text-[10px] font-bold text-rose-400 hover:bg-rose-950/40 hover:text-rose-300 border border-rose-500/20 bg-rose-950/20 px-2.5 py-1 rounded-lg transition"
                >
                  <Trash2 className="h-3 w-3" /> Clear Pick
                </button>
              </div>
            )}

            {/* Search and Assign Dropdown */}
            <div className="mt-4 flex flex-col gap-3">
              <span className="text-xs font-bold text-slate-400 uppercase">
                {activeEvent ? "Swap to a New Player" : "Assign Player to Pick"}
              </span>

              <div className="relative">
                <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search player name, pos, or team..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-10 pr-4 text-xs text-white focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <select
                value={selectedPlayerId}
                onChange={(e) => setSelectedPlayerId(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-emerald-500 focus:outline-none"
              >
                <option value="">-- Select Player --</option>
                {filteredSearchPlayers.map((p) => {
                  const name = p.full_name || p.player_name || "Unknown";
                  return (
                    <option key={p.player_id} value={p.player_id}>
                      {name} ({p.position} - {p.team})
                    </option>
                  );
                })}
              </select>
            </div>

            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setActivePickNo(null);
                  setSelectedPlayerId("");
                }}
                className="flex-1 rounded-xl border border-slate-700 bg-slate-800 text-xs font-bold text-slate-300 py-2 hover:bg-slate-700 transition"
              >
                ❌ Cancel
              </button>
              <button
                type="button"
                onClick={handleSavePick}
                disabled={!selectedPlayerId}
                className="flex-1 rounded-xl bg-emerald-600 text-xs font-bold text-white py-2 hover:bg-emerald-500 disabled:opacity-50 transition"
              >
                💾 Save Pick
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

"use client";

import React, { useState } from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { RotateCcw, Settings, ShieldAlert, Sparkles, Wifi, WifiOff } from "lucide-react";
import { ESPNSyncModal } from "./ESPNSyncModal";

export const HeaderBar: React.FC = () => {
  const {
    currentPick,
    currentRound,
    teamOnClock,
    picksUntilUserTurn,
    isUserOnClock,
    userTeamSlot,
    wsConnected,
    undoPick,
    resetDraft,
    isSubmitting,
    espnTeams,
  } = useDraftStore();

  const [isModalOpen, setIsModalOpen] = useState(false);

  // Find user's ESPN team name if available
  const userTeam = espnTeams.find((t) => t.team_slot === userTeamSlot);
  const userTeamLabel = userTeam ? `${userTeam.team_name}` : `Team #${userTeamSlot}`;

  const activeClockTeam = espnTeams.find((t) => t.team_slot === teamOnClock);
  const activeClockTeamLabel = activeClockTeam ? activeClockTeam.team_name : `Team ${teamOnClock}`;

  const handleOpenModal = () => {
    console.log("⚙️ [HeaderBar] 'ESPN Sync & Settings' button clicked! Opening modal...");
    setIsModalOpen(true);
  };

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          {/* Brand & Connection Status */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-700 shadow-lg shadow-emerald-500/20">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-base sm:text-lg font-black tracking-tight text-white flex items-center gap-2">
                  THE BEST DAMN FANTASY FOOTBALL DRAFTING APP <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-xs font-bold text-emerald-400 border border-emerald-500/20">V2 ADA ENGINE</span>
                </h1>
                <p className="text-xs font-semibold text-emerald-400">The Best Damn Fantasy Football Drafting App</p>
              </div>
            </div>

            {/* Connection Status Badge */}
            <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-xs">
              {wsConnected ? (
                <>
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                  </span>
                  <span className="font-medium text-emerald-400 flex items-center gap-1">
                    <Wifi className="h-3 w-3" /> Live WebSocket (&lt;10ms)
                  </span>
                </>
              ) : (
                <>
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500"></span>
                  <span className="font-medium text-amber-400 flex items-center gap-1">
                    <WifiOff className="h-3 w-3" /> REST Polling Mode
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Draft Stats Center */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/80 px-4 py-2 text-sm shadow-inner">
              <div>
                <span className="block text-[10px] uppercase font-bold text-slate-500">Your Team</span>
                <span className="font-bold text-emerald-400 truncate max-w-[120px] block">{userTeamLabel}</span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="block text-[10px] uppercase font-bold text-slate-500">Round / Pick</span>
                <span className="font-bold text-white">R{currentRound} • Pick #{currentPick}</span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="block text-[10px] uppercase font-bold text-slate-500">On The Clock</span>
                <span className={`font-bold ${isUserOnClock ? "text-amber-400 animate-pulse" : "text-slate-300"}`}>
                  {isUserOnClock ? "★ YOU" : activeClockTeamLabel}
                </span>
              </div>
              <div className="h-6 w-px bg-slate-800" />
              <div>
                <span className="block text-[10px] uppercase font-bold text-slate-500">Picks Until Turn</span>
                <span className="font-bold text-teal-300">
                  {picksUntilUserTurn === 0 ? "NOW" : `${picksUntilUserTurn} picks`}
                </span>
              </div>
            </div>
          </div>

          {/* Action Controls */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleOpenModal}
              className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20 active:scale-95"
            >
              <Settings className="h-3.5 w-3.5" /> ESPN Sync & Settings
            </button>
            <button
              onClick={() => undoPick()}
              disabled={isSubmitting}
              className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white disabled:opacity-50"
              title="Shortcut: Cmd+Z or Ctrl+Z"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Undo
            </button>
            <button
              onClick={() => {
                if (confirm("Are you sure you want to reset the draft log?")) {
                  resetDraft();
                }
              }}
              className="flex items-center gap-1.5 rounded-lg border border-rose-900/50 bg-rose-950/40 px-3 py-1.5 text-xs font-semibold text-rose-300 transition hover:bg-rose-900/60"
            >
              <ShieldAlert className="h-3.5 w-3.5" /> Reset
            </button>
          </div>
        </div>
      </header>

      {/* ESPN Sync & Settings Modal */}
      <ESPNSyncModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};

"use client";

import React, { useEffect, useRef, useState } from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { CornerDownLeft, Search, UserCheck, UserX, Zap } from "lucide-react";
import { Player } from "../types/draft";

export const PickInput: React.FC = () => {
  const {
    adaRankings,
    recordPick,
    undoPick,
    currentPick,
    teamOnClock,
    isUserOnClock,
    espnTeams,
  } = useDraftStore();

  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [isDraftedByUser, setIsDraftedByUser] = useState(isUserOnClock);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync draft user toggle with who is on clock
  useEffect(() => {
    setIsDraftedByUser(isUserOnClock);
  }, [isUserOnClock]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter available top candidates based on search query
  const filteredPlayers = React.useMemo(() => {
    if (!query.trim()) return adaRankings.slice(0, 10);
    const q = query.toLowerCase().trim();
    return adaRankings
      .filter((p) => {
        const name = (p.full_name || p.player_name || "").toLowerCase();
        const pos = (p.position || "").toLowerCase();
        const team = (p.team || "").toLowerCase();
        return name.includes(q) || pos.includes(q) || team.includes(q);
      })
      .slice(0, 10);
  }, [query, adaRankings]);

  // Keyboard Shortcuts (Cmd+K focus, Cmd+Z undo, Enter confirm, Arrow keys navigate)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K -> Focus Search
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
        return;
      }

      // Cmd+Z or Ctrl+Z -> Undo
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undoPick();
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [undoPick]);

  const handleSelectPlayer = (player: Player) => {
    recordPick(player.player_id, isDraftedByUser);
    setQuery("");
    setIsOpen(false);
  };

  const onKeyDownInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredPlayers.length));
      setIsOpen(true);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredPlayers.length) % Math.max(1, filteredPlayers.length));
      setIsOpen(true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredPlayers.length > 0 && selectedIndex < filteredPlayers.length) {
        handleSelectPlayer(filteredPlayers[selectedIndex]);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const activeClockTeam = espnTeams.find((t) => t.team_slot === teamOnClock);
  const activeClockTeamLabel = activeClockTeam ? activeClockTeam.team_name : `Team #${teamOnClock}`;

  return (
    <div ref={containerRef} className="relative w-full z-50">
      <div className="flex flex-col gap-2 rounded-2xl border border-slate-800 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-emerald-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              High-Speed Pick Entry (Pick #{currentPick})
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Targeting:</span>
            <button
              onClick={() => setIsDraftedByUser(!isDraftedByUser)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1 font-semibold transition border ${
                isDraftedByUser
                  ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-300"
                  : "border-amber-500/50 bg-amber-500/20 text-amber-300"
              }`}
            >
              {isDraftedByUser ? (
                <>
                  <UserCheck className="h-3.5 w-3.5" /> My Roster Pick
                </>
              ) : (
                <>
                  <UserX className="h-3.5 w-3.5" /> Opponent Pick ({activeClockTeamLabel})
                </>
              )}
            </button>
          </div>
        </div>

        {/* Input Field with Dropdown results embedded inside the relative container */}
        <div className="relative flex flex-col w-full">
          <div className="relative flex items-center w-full">
            <Search className="absolute left-3.5 h-5 w-5 text-slate-400" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onFocus={() => setIsOpen(true)}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
                setIsOpen(true);
              }}
              onKeyDown={onKeyDownInput}
              placeholder="Type player name, position (QB, RB...), or team (Cmd+K)..."
              className="w-full rounded-xl border border-slate-700 bg-slate-950 py-3 pl-11 pr-24 text-sm font-medium text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 transition shadow-inner"
            />
            <div className="absolute right-3 flex items-center gap-1">
              <kbd className="hidden rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-400 sm:inline-block border border-slate-700">
                ⌘K
              </kbd>
              <kbd className="hidden rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-400 sm:inline-block border border-slate-700">
                ↵ Enter
              </kbd>
            </div>
          </div>

          {/* Combobox Dropdown Results inside the stacking context */}
          {isOpen && filteredPlayers.length > 0 && (
            <div className="absolute top-full left-0 right-0 z-50 mt-1 max-h-72 overflow-y-auto rounded-xl border border-emerald-500/40 bg-slate-950 p-1 shadow-2xl">
              {filteredPlayers.map((player, idx) => {
                const isSelected = idx === selectedIndex;
                const name = player.full_name || player.player_name || "Unknown";
                return (
                  <div
                    key={player.player_id}
                    onClick={() => handleSelectPlayer(player)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-xs transition ${
                      isSelected ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/20" : "text-slate-300 hover:bg-slate-900"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-5 w-5 items-center justify-center rounded bg-slate-800 text-[10px] font-bold text-slate-300">
                        #{player.rank || idx + 1}
                      </span>
                      <div>
                        <span className="font-bold text-white">{name}</span>
                        <span className="ml-2 text-[10px] text-slate-400">
                          {player.position} • {player.team || "FA"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-[10px]">
                      {player.composite_score !== undefined && (
                        <span className="rounded bg-emerald-950/80 px-1.5 py-0.5 font-bold text-emerald-400 border border-emerald-800/30">
                          SCORE {player.composite_score}
                        </span>
                      )}
                      {player.adp && <span className="text-slate-400">ADP {player.adp}</span>}
                      <CornerDownLeft className={`h-3.5 w-3.5 ${isSelected ? "opacity-100 text-emerald-400" : "opacity-0"}`} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

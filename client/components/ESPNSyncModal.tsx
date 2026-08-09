"use client";

import React, { useEffect, useState } from "react";
import { useDraftStore } from "../stores/useDraftStore";
import { CheckCircle2, Lock, Play, RefreshCw, RotateCcw, Settings, ShieldAlert, X } from "lucide-react";

interface ESPNSyncModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ESPNSyncModal: React.FC<ESPNSyncModalProps> = ({ isOpen, onClose }) => {
  console.log("⚙️ [ESPNSyncModal] Rendered. isOpen =", isOpen);

  const {
    espnLeagueId,
    espnSeasonYear,
    espnS2,
    espnSwid,
    useMultiSource,
    espnTeams,
    userTeamSlot,
    numTeams,
    scoringFormat,
    isSyncing,
    syncMessage,
    feedStatus,
    syncESPN,
    updateConfig,
    fetchConfig,
    is3rr,
    adaRankings,
    draftLog,
    addKeeper,
    undoKeeper,
    startDraft,
  } = useDraftStore();

  const [leagueIdInput, setLeagueIdInput] = useState(espnLeagueId);
  const [seasonYearInput, setSeasonYearInput] = useState(espnSeasonYear);
  const [s2Input, setS2Input] = useState(espnS2);
  const [swidInput, setSwidInput] = useState(espnSwid);
  const [multiSourceInput, setMultiSourceInput] = useState(useMultiSource);
  const [enableSleeper, setEnableSleeper] = useState(true);
  const [enableFantasyPros, setEnableFantasyPros] = useState(true);
  const [enableUnderdog, setEnableUnderdog] = useState(true);
  const [enableVegas, setEnableVegas] = useState(true);
  const [enableHighStakes, setEnableHighStakes] = useState(true);
  const [enableAdvanced, setEnableAdvanced] = useState(true);

  // Keeper Selector state
  const [keeperPlayerId, setKeeperPlayerId] = useState("");
  const [keeperTeamSlot, setKeeperTeamSlot] = useState(1);
  const [keeperRound, setKeeperRound] = useState(1);

  useEffect(() => {
    if (isOpen) {
      console.log("⚙️ [ESPNSyncModal] Modal opened! Calling fetchConfig()...");
      fetchConfig();
    }
  }, [isOpen, fetchConfig]);

  useEffect(() => {
    setLeagueIdInput(espnLeagueId);
    setSeasonYearInput(espnSeasonYear);
    setS2Input(espnS2);
    setSwidInput(espnSwid);
  }, [espnLeagueId, espnSeasonYear, espnS2, espnSwid]);

  if (!isOpen) return null;

  const handleSync = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log("🔄 [ESPNSyncModal] Submitting sync request...", {
      league_id: leagueIdInput,
      season_year: seasonYearInput,
      use_multi_source: multiSourceInput,
    });
    await syncESPN({
      league_id: leagueIdInput ? Number(leagueIdInput) : undefined,
      season_year: Number(seasonYearInput),
      espn_s2: s2Input,
      swid: swidInput,
      use_multi_source: multiSourceInput,
    });
  };

  // Helper pick calculation logic in JS
  const calculateKeeperPickNo = (roundNo: number, teamSlot: number, totalTeams: number, is3rrEnabled: boolean) => {
    let isReverse = false;
    if (is3rrEnabled) {
      if (roundNo === 1) isReverse = false;
      else if (roundNo === 2 || roundNo === 3) isReverse = true;
      else isReverse = (roundNo % 2 === 1);
    } else {
      isReverse = (roundNo % 2 === 0);
    }
    const pickInRound = isReverse ? (totalTeams - teamSlot + 1) : teamSlot;
    return (roundNo - 1) * totalTeams + pickInRound;
  };

  const currentEstimatedPick = calculateKeeperPickNo(keeperRound, keeperTeamSlot, numTeams, is3rr);

  const handleLockKeeper = async () => {
    if (!keeperPlayerId) return;
    console.log("🔒 [ESPNSyncModal] Locking keeper player:", keeperPlayerId, "for team slot:", keeperTeamSlot);
    await addKeeper(keeperPlayerId, keeperTeamSlot, keeperRound);
    setKeeperPlayerId("");
  };

  const handleStartDraft = async () => {
    console.log("🚀 [ESPNSyncModal] Starting draft...");
    await startDraft();
    onClose();
  };

  // Filter draft log for keepers
  const keepers = draftLog.filter(
    (e) =>
      e.source === "keeper" ||
      (e.notes && e.notes.toLowerCase().includes("keeper"))
  );

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-md">
      <div className="relative w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl max-h-[85vh] overflow-y-auto scrollbar-thin">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-emerald-400" />
            <h2 className="text-base font-bold text-white">ESPN League Data & Settings</h2>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Sync Status Banner */}
        {syncMessage && (
          <div
            className={`mt-3 flex items-center gap-2 rounded-xl p-2.5 text-xs font-semibold border ${
              syncMessage.startsWith("Error")
                ? "border-rose-500/40 bg-rose-950/30 text-rose-300"
                : syncMessage.startsWith("Warning")
                ? "border-amber-500/45 bg-amber-950/20 text-amber-350"
                : "border-emerald-500/40 bg-emerald-950/30 text-emerald-300"
            }`}
          >
            {syncMessage.startsWith("Error") || syncMessage.startsWith("Warning") ? (
              <ShieldAlert className="h-4 w-4" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            <span>{syncMessage}</span>
          </div>
        )}

        {/* STEP 1: Sync ESPN League Data and Players */}
        <div className="mt-3 flex flex-col gap-2">
          <h3 className="text-xs font-extrabold uppercase text-emerald-400 tracking-wider">1. Sync ESPN League Data & Players</h3>
          <form onSubmit={handleSync} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">ESPN League ID</label>
                <input
                  type="text"
                  value={leagueIdInput}
                  onChange={(e) => setLeagueIdInput(e.target.value)}
                  placeholder="e.g. 123456789"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Season Year</label>
                <input
                  type="number"
                  value={seasonYearInput}
                  onChange={(e) => setSeasonYearInput(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">ESPN_S2 Cookie</label>
                <input
                  type="password"
                  value={s2Input}
                  onChange={(e) => setS2Input(e.target.value)}
                  placeholder="Optional if public"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">SWID Cookie</label>
                <input
                  type="text"
                  value={swidInput}
                  onChange={(e) => setSwidInput(e.target.value)}
                  placeholder="{YOUR-SWID}"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Multi-Source Data Feeds & Source Toggles Panel */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase text-slate-300 tracking-wider">⚡ Data Feeds & Source Controls</span>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="multiSource"
                    checked={multiSourceInput}
                    onChange={(e) => setMultiSourceInput(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500"
                  />
                  <label htmlFor="multiSource" className="text-[11px] font-bold text-emerald-400">
                    Master Multi-Source Blending
                  </label>
                </div>
              </div>

              {multiSourceInput && (
                <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800/80 text-[10px]">
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableSleeper} onChange={(e) => setEnableSleeper(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>📈 Sleeper ADP</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableFantasyPros} onChange={(e) => setEnableFantasyPros(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>🎯 FantasyPros ECR</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableUnderdog} onChange={(e) => setEnableUnderdog(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>⚡ Underdog High-Stakes ADP</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableVegas} onChange={(e) => setEnableVegas(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>🎲 Vegas Sportsbook Props</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableHighStakes} onChange={(e) => setEnableHighStakes(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>🔬 High-Stakes (ETR/PFF)</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
                    <input type="checkbox" checked={enableAdvanced} onChange={(e) => setEnableAdvanced(e.target.checked)} className="rounded border-slate-700 text-emerald-500" />
                    <span>📊 AirYards & xFP Metrics</span>
                  </label>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is3rr"
                  checked={is3rr}
                  onChange={(e) => updateConfig(userTeamSlot, numTeams, e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500"
                />
                <label htmlFor="is3rr" className="text-[11px] font-semibold text-slate-300">
                  3rd Round Reversal (3RR)
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSyncing}
              className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 py-2 text-xs font-bold text-white shadow hover:from-emerald-500 hover:to-teal-500 transition disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isSyncing ? "animate-spin" : ""}`} />
              {isSyncing ? "Syncing ESPN & Multi-Source Data..." : "🔄 Sync ESPN League Data & Players"}
            </button>

            {/* Live Data Feeds Audit Status Results */}
            {feedStatus && (
              <div className="mt-2 flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-extrabold uppercase text-emerald-400 tracking-wider">📊 Data Feed Sync Audit Breakdown</span>
                  <span className="text-[10px] text-slate-400 font-bold">Live Status</span>
                </div>
                <div className="grid grid-cols-2 gap-1.5 pt-1 border-t border-slate-800/80">
                  {Object.entries(feedStatus).map(([key, info]) => {
                    const isOk = info.status === "OK";
                    const isOff = info.status === "OFF";
                    return (
                      <div key={key} className="flex items-center justify-between rounded-lg bg-slate-900/90 px-2.5 py-1.5 border border-slate-800/80">
                        <span className="text-slate-300 font-semibold text-[11px] truncate max-w-[110px]">{info.name || key}</span>
                        <span className={`text-[9px] font-black px-1.5 py-0.5 rounded border ${
                          isOk ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" :
                          isOff ? "bg-slate-800 text-slate-400 border-slate-700" :
                          "bg-rose-500/20 text-rose-300 border-rose-500/40"
                        }`}>
                          {isOk ? `🟢 OK (${info.matched_count})` : isOff ? "⚪ OFF" : "⚠️ Failed"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </form>
        </div>

        {/* STEP 2: Select Your Team */}
        {adaRankings.length > 0 && (
          <div className="mt-4 border-t border-slate-800 pt-3 flex flex-col gap-2">
            <h3 className="text-xs font-extrabold uppercase text-emerald-400 tracking-wider">2. Select Your Team</h3>

            {espnTeams.length > 0 ? (
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Select Your Team (ESPN)</label>
                <select
                  value={userTeamSlot}
                  onChange={(e) => updateConfig(Number(e.target.value), numTeams, is3rr)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-medium text-white focus:border-emerald-500 focus:outline-none"
                >
                  {espnTeams.map((t) => (
                    <option key={t.team_slot} value={t.team_slot}>
                      Slot {t.team_slot}: {t.team_name}{t.owner ? ` (${t.owner})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Your Team Slot</label>
                  <input
                    type="number"
                    value={userTeamSlot}
                    min={1}
                    max={20}
                    onChange={(e) => updateConfig(Number(e.target.value), numTeams, is3rr)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Total League Teams</label>
                  <input
                    type="number"
                    value={numTeams}
                    min={4}
                    max={20}
                    onChange={(e) => updateConfig(userTeamSlot, Number(e.target.value), is3rr)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500"
                  />
                </div>
              </div>
            )}

            <div className="flex items-center justify-between text-[11px] text-slate-400 bg-slate-950/60 p-2 rounded-xl border border-slate-800">
              <span>Scoring Format: <strong className="text-emerald-400">{scoringFormat}</strong></span>
              <span>League Teams: <strong className="text-white">{numTeams} Teams</strong></span>
            </div>
          </div>
        )}

        {/* STEP 3: Select Keepers */}
        {adaRankings.length > 0 && (
          <div className="mt-4 border-t border-slate-800 pt-3 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-amber-400" />
              <h3 className="text-xs font-extrabold uppercase text-emerald-400 tracking-wider">3. Select Keepers</h3>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Select Keeper Player</label>
                <select
                  value={keeperPlayerId}
                  onChange={(e) => setKeeperPlayerId(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                >
                  <option value="">-- Select Player --</option>
                  {adaRankings.slice(0, 150).map((p) => {
                    const name = p.full_name || p.player_name || "Unknown";
                    return (
                      <option key={p.player_id} value={p.player_id}>
                        {name} ({p.position} - {p.team})
                      </option>
                    );
                  })}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Assign to Team</label>
                <select
                  value={keeperTeamSlot}
                  onChange={(e) => setKeeperTeamSlot(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500 focus:outline-none"
                >
                  {espnTeams.length > 0 ? (
                    espnTeams.map((t) => (
                      <option key={t.team_slot} value={t.team_slot}>
                        Slot {t.team_slot}: {t.team_name}
                      </option>
                    ))
                  ) : (
                    Array.from({ length: numTeams }, (_, i) => (
                      <option key={i + 1} value={i + 1}>
                        Team Slot {i + 1}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 items-end">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1">Keeper Round</label>
                <input
                  type="number"
                  min={1}
                  max={25}
                  value={keeperRound}
                  onChange={(e) => setKeeperRound(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-emerald-500"
                />
              </div>

              <button
                type="button"
                onClick={handleLockKeeper}
                disabled={!keeperPlayerId}
                className="w-full rounded-xl bg-amber-650 py-2 text-xs font-bold text-white shadow hover:bg-amber-500 disabled:opacity-50 transition"
              >
                🔒 Lock in Keeper
              </button>
            </div>

            <div className="text-[11px] text-amber-300 bg-amber-950/20 p-2 rounded-xl border border-amber-900/40">
              📍 Estimated Draft Pick Assignment: <strong>#{currentEstimatedPick}</strong> (Round {keeperRound})
            </div>

            {/* List of Active Keepers */}
            {keepers.length > 0 && (
              <div className="mt-2 flex flex-col gap-2 border-t border-slate-800 pt-3">
                <span className="text-[10px] font-extrabold uppercase text-slate-400">Locked Pre-Draft Keepers:</span>
                <div className="max-h-32 overflow-y-auto flex flex-col gap-1.5 pr-1 text-xs">
                  {keepers.map((k) => (
                    <div key={k.pick_no} className="flex items-center justify-between rounded-lg bg-slate-950 border border-slate-800 px-3 py-1.5 text-slate-300">
                      <div>
                        <span className="font-bold text-amber-400 mr-2">Pick #{k.pick_no}</span>
                        <span className="font-medium text-white">{k.player_name}</span>
                        <span className="text-[10px] text-slate-500 ml-2">({k.position})</span>
                      </div>
                      <span className="font-semibold text-slate-400">{k.team_name || `Slot ${k.team_slot}`}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => undoKeeper()}
                  className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 py-1 text-xs font-semibold text-slate-200 transition hover:bg-slate-700 hover:text-white"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Undo Last Keeper
                </button>
              </div>
            )}
          </div>
        )}

        {/* STEP 4: Start Draft Button */}
        {adaRankings.length > 0 && (
          <div className="mt-6 border-t border-slate-800 pt-4">
            <button
              onClick={handleStartDraft}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 py-2.5 text-sm font-black text-white hover:from-emerald-400 hover:to-teal-450 transition shadow-lg shadow-emerald-500/25 active:scale-98"
            >
              <Play className="h-4 w-4 fill-white text-white" />
              🚀 START LIVE DRAFT NOW
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

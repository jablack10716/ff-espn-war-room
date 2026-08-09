"use client";

import React, { useEffect, useState } from "react";
import { HeaderBar } from "../components/HeaderBar";
import { PickInput } from "../components/PickInput";
import { AdaRecommendations } from "../components/AdaRecommendations";
import { AgentAdvisoryPanel } from "../components/AgentAdvisoryPanel";
import { RosterGrid } from "../components/RosterGrid";
import { FullDraftGrid } from "../components/FullDraftGrid";
import { useDraftStore } from "../stores/useDraftStore";

export default function WarRoomDashboard() {
  const { fetchState, connectWebSocket } = useDraftStore();
  const [activeTab, setActiveTab] = useState<"war-room" | "draft-grid">("war-room");

  useEffect(() => {
    fetchState();
    connectWebSocket();
  }, [fetchState, connectWebSocket]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased selection:bg-emerald-500 selection:text-slate-950">
      {/* Top Navigation Header */}
      <HeaderBar />

      {/* Main War Room Content */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6">
          
          {/* Navigation Tabs bar */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex gap-2 rounded-xl bg-slate-900/60 p-1 border border-slate-800 w-fit">
              <button
                onClick={() => setActiveTab("war-room")}
                className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  activeTab === "war-room" ? "bg-emerald-500 text-slate-950 shadow-md" : "text-slate-400 hover:text-white"
                }`}
              >
                🎯 Live War Room
              </button>
              <button
                onClick={() => setActiveTab("draft-grid")}
                className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  activeTab === "draft-grid" ? "bg-emerald-500 text-slate-950 shadow-md" : "text-slate-400 hover:text-white"
                }`}
              >
                📊 Full Draft Board Grid
              </button>
            </div>

            {activeTab === "war-room" && (
              <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wide">
                The Best Damn Fantasy Football Drafting App
              </span>
            )}
            {activeTab === "draft-grid" && (
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                Interactive board matrix active
              </span>
            )}
          </div>

          {/* High Speed Pick Entry Input Bar */}
          <PickInput />

          {activeTab === "war-room" ? (
            /* 3-Column Dashboard Layout */
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Left Column: Ada Top Recommendations (5 Cols) */}
              <div className="lg:col-span-5">
                <AdaRecommendations />
              </div>

              {/* Middle Column: Agent Advisory Panel (4 Cols) */}
              <div className="lg:col-span-4">
                <AgentAdvisoryPanel />
              </div>

              {/* Right Column: Live Roster Grid & Draft Log (3 Cols) */}
              <div className="lg:col-span-3">
                <RosterGrid />
              </div>
            </div>
          ) : (
            /* 2D Board Matrix Grid Layout */
            <FullDraftGrid />
          )}
        </div>
      </main>
    </div>
  );
}

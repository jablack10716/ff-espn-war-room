import { create } from "zustand";
import { DraftStatePayload, ESPNTeam, PickEvent, Player } from "../types/draft";

interface DraftStoreState {
  draftId: string;
  userTeamSlot: number;
  numTeams: number;
  currentPick: number;
  currentRound: number;
  teamOnClock: number;
  picksUntilUserTurn: number;
  isUserOnClock: boolean;
  wsConnected: boolean;
  draftLog: PickEvent[];
  userRoster: PickEvent[];
  rosterByPosition: Record<string, PickEvent[]>;
  adaRankings: Player[];
  agentAdvisories: any | null;
  searchQuery: string;
  isSubmitting: boolean;
  wsInstance: WebSocket | null;

  // ESPN Settings State
  espnLeagueId: string;
  espnSeasonYear: number;
  espnS2: string;
  espnSwid: string;
  useMultiSource: boolean;
  espnTeams: ESPNTeam[];
  scoringFormat: string;
  isSyncing: boolean;
  syncMessage: string | null;
  is3rr: boolean;
  draftStarted: boolean;
  isDeliberating: boolean;

  // Actions
  setSearchQuery: (query: string) => void;
  fetchState: () => Promise<void>;
  fetchConfig: () => Promise<void>;
  updateConfig: (userTeamSlot?: number, numTeams?: number, is3rr?: boolean) => Promise<void>;
  syncESPN: (params: { league_id?: number; season_year?: number; espn_s2?: string; swid?: string; use_multi_source?: boolean }) => Promise<void>;
  recordPick: (playerId: string, isUserPick?: boolean, pickNo?: number, teamSlot?: number) => Promise<void>;
  undoPick: () => Promise<void>;
  deletePick: (pickNo: number) => Promise<void>;
  resetDraft: () => Promise<void>;
  connectWebSocket: () => void;

  // Keeper Actions
  addKeeper: (playerId: string, teamSlot: number, roundNo: number) => Promise<void>;
  undoKeeper: () => Promise<void>;

  // Start Draft Action
  startDraft: () => Promise<void>;

  // Debate Action
  triggerDebate: () => Promise<void>;
}

const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

export const useDraftStore = create<DraftStoreState>((set, get) => ({
  draftId: "default_draft_2026",
  userTeamSlot: 1,
  numTeams: 12,
  currentPick: 1,
  currentRound: 1,
  teamOnClock: 1,
  picksUntilUserTurn: 0,
  isUserOnClock: true,
  wsConnected: false,
  draftLog: [],
  userRoster: [],
  rosterByPosition: {
    QB: [], RB: [], WR: [], TE: [], FLEX: [], SUPERFLEX: [], K: [], DST: [], BENCH: []
  },
  adaRankings: [],
  agentAdvisories: null,
  searchQuery: "",
  isSubmitting: false,
  wsInstance: null,

  espnLeagueId: "",
  espnSeasonYear: 2026,
  espnS2: "",
  espnSwid: "",
  useMultiSource: true,
  espnTeams: [],
  scoringFormat: "HALF_PPR",
  isSyncing: false,
  syncMessage: null,
  is3rr: false,
  draftStarted: false,
  isDeliberating: false,

  setSearchQuery: (query: string) => set({ searchQuery: query }),

  fetchConfig: async () => {
    console.log("⚙️ [useDraftStore] fetchConfig() requesting http://localhost:8000/api/config...");
    try {
      const res = await fetch(`${API_BASE}/api/config`);
      if (!res.ok) {
        console.error("❌ [useDraftStore] fetchConfig HTTP error:", res.status);
        return;
      }
      const data = await res.json();
      console.log("✅ [useDraftStore] fetchConfig response received:", data);
      set({
        espnLeagueId: data.league_id ? String(data.league_id) : "",
        espnSeasonYear: data.season_year || 2026,
        espnS2: data.espn_s2 || "",
        espnSwid: data.swid || "",
        userTeamSlot: data.user_team_slot || 1,
        numTeams: data.num_teams || 12,
        espnTeams: data.espn_teams || [],
        scoringFormat: data.scoring_format || "HALF_PPR",
        is3rr: data.is_3rr ?? false,
        draftStarted: data.draft_started ?? false,
      });
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to fetch config from backend:", err);
    }
  },

  updateConfig: async (userTeamSlot?: number, numTeams?: number, is3rr?: boolean) => {
    console.log("⚙️ [useDraftStore] updateConfig requested:", { userTeamSlot, numTeams, is3rr });
    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_team_slot: userTeamSlot,
          num_teams: numTeams,
          is_3rr: is3rr,
          draft_id: get().draftId,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        console.log("✅ [useDraftStore] Config updated successfully:", data);
        if (data.state) {
          const s = data.state;
          set({
            userTeamSlot: s.user_team_slot,
            numTeams: s.num_teams,
            picksUntilUserTurn: s.picks_until_user_turn,
            isUserOnClock: s.is_user_on_clock,
            userRoster: s.user_roster,
            rosterByPosition: s.roster_by_position,
            adaRankings: s.ada_rankings,
            is3rr: s.is_3rr ?? false,
          });
        }
      }
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to update config:", err);
    }
  },

  syncESPN: async (params) => {
    console.log("🔄 [useDraftStore] syncESPN requested:", params);
    set({ isSyncing: true, syncMessage: null });
    try {
      const res = await fetch(`${API_BASE}/api/sync_espn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          league_id: params.league_id ? Number(params.league_id) : undefined,
          season_year: params.season_year ? Number(params.season_year) : undefined,
          espn_s2: params.espn_s2,
          swid: params.swid,
          use_multi_source: params.use_multi_source ?? true,
          draft_id: get().draftId,
        }),
      });

      const data = await res.json();
      console.log("✅ [useDraftStore] syncESPN API response:", data);
      if (!res.ok) {
        throw new Error(data.detail || "ESPN Sync failed");
      }

      set({
        syncMessage: data.message || "ESPN Sync completed successfully!",
        espnTeams: data.teams || [],
        scoringFormat: data.scoring_format || "HALF_PPR",
      });

      if (data.state) {
        const s = data.state;
        set({
          userTeamSlot: s.user_team_slot,
          numTeams: s.num_teams,
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          is3rr: s.is_3rr ?? false,
          draftStarted: s.draft_started ?? false,
        });
      }
    } catch (err: any) {
      console.error("❌ [useDraftStore] Error syncing ESPN:", err);
      set({ syncMessage: `Error: ${err.message || "Failed to sync"}` });
    } finally {
      set({ isSyncing: false });
    }
  },

  fetchState: async () => {
    console.log("📡 [useDraftStore] fetchState() requesting http://localhost:8000/api/state...");
    try {
      const res = await fetch(`${API_BASE}/api/state?draft_id=${get().draftId}&user_team_slot=${get().userTeamSlot}`);
      if (!res.ok) {
        console.error("❌ [useDraftStore] fetchState HTTP error:", res.status);
        return;
      }
      const data: DraftStatePayload = await res.json();
      console.log("✅ [useDraftStore] fetchState response received with", data.ada_rankings?.length || 0, "rankings");
      set({
        userTeamSlot: data.user_team_slot,
        numTeams: data.num_teams || 12,
        currentPick: data.current_pick,
        currentRound: data.current_round,
        teamOnClock: data.team_on_clock,
        picksUntilUserTurn: data.picks_until_user_turn,
        isUserOnClock: data.is_user_on_clock,
        draftLog: data.draft_log,
        userRoster: data.user_roster,
        rosterByPosition: data.roster_by_position || {
          QB: [], RB: [], WR: [], TE: [], FLEX: [], SUPERFLEX: [], K: [], DST: [], BENCH: []
        },
        adaRankings: data.ada_rankings || [],
        agentAdvisories: data.agent_advisories,
        espnTeams: data.espn_teams || get().espnTeams,
        scoringFormat: data.scoring_format || get().scoringFormat,
        is3rr: data.is_3rr ?? false,
        draftStarted: data.draft_started ?? false,
      });
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to fetch state from backend:", err);
    }
  },

  addKeeper: async (playerId: string, teamSlot: number, roundNo: number) => {
    console.log("🔒 [useDraftStore] addKeeper requested:", { playerId, teamSlot, roundNo });
    set({ isSubmitting: true });
    try {
      const res = await fetch(`${API_BASE}/api/keepers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          player_id: playerId,
          team_slot: teamSlot,
          round_no: roundNo,
          draft_id: get().draftId,
        }),
      });

      if (!res.ok) {
        throw new Error("Keeper lock failed");
      }

      const data = await res.json();
      console.log("✅ [useDraftStore] Keeper locked:", data);
      if (data.state) {
        const s = data.state;
        set({
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          agentAdvisories: s.agent_advisories,
        });
      }
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to add keeper:", err);
    } finally {
      set({ isSubmitting: false });
    }
  },

  undoKeeper: async () => {
    console.log("⏪ [useDraftStore] undoKeeper requested");
    set({ isSubmitting: true });
    try {
      const res = await fetch(`${API_BASE}/api/keepers/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft_id: get().draftId }),
      });

      if (!res.ok) {
        throw new Error("Keeper undo failed");
      }

      const data = await res.json();
      console.log("✅ [useDraftStore] Keeper undone:", data);
      if (data.state) {
        const s = data.state;
        set({
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          agentAdvisories: s.agent_advisories,
        });
      }
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to undo keeper:", err);
    } finally {
      set({ isSubmitting: false });
    }
  },

  startDraft: async () => {
    console.log("🚀 [useDraftStore] startDraft() requested");
    try {
      const res = await fetch(`${API_BASE}/api/draft/start?draft_id=${get().draftId}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        console.log("✅ [useDraftStore] Draft started successfully:", data);
        if (data.state) {
          const s = data.state;
          set({
            currentPick: s.current_pick,
            currentRound: s.current_round,
            teamOnClock: s.team_on_clock,
            picksUntilUserTurn: s.picks_until_user_turn,
            isUserOnClock: s.is_user_on_clock,
            draftLog: s.draft_log,
            userRoster: s.user_roster,
            rosterByPosition: s.roster_by_position,
            adaRankings: s.ada_rankings,
            is3rr: s.is_3rr ?? false,
            draftStarted: s.draft_started ?? false,
          });
        }
      }
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to start draft:", err);
    }
  },

  triggerDebate: async () => {
    console.log("🤖 [useDraftStore] triggerDebate() requested");
    set({ isDeliberating: true });
    try {
      const res = await fetch(`${API_BASE}/api/draft/deliberate?draft_id=${get().draftId}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        console.log("✅ [useDraftStore] Debate completed successfully:", data);
        if (data.state) {
          const s = data.state;
          set({
            agentAdvisories: s.agent_advisories,
          });
        }
      }
    } catch (err) {
      console.error("❌ [useDraftStore] Failed to trigger debate:", err);
    } finally {
      set({ isDeliberating: false });
    }
  },

  recordPick: async (playerId: string, isUserPick: boolean = true, pickNo?: number, teamSlot?: number) => {
    const { draftId, currentPick, currentRound, teamOnClock, adaRankings, draftLog } = get();

    const targetPlayer = adaRankings.find((p) => p.player_id === playerId);
    const playerName = targetPlayer?.full_name || targetPlayer?.player_name || "Unknown Player";
    const position = targetPlayer?.position || "FLEX";

    const targetPickNo = pickNo !== undefined ? pickNo : currentPick;
    const targetTeamSlot = teamSlot !== undefined ? teamSlot : (isUserPick ? get().userTeamSlot : teamOnClock);

    const optimisticPick: PickEvent = {
      draft_id: draftId,
      pick_no: targetPickNo,
      round_no: Math.floor((targetPickNo - 1) / get().numTeams) + 1,
      team_slot: targetTeamSlot,
      player_id: playerId,
      player_name: playerName,
      position: position,
      picked_by_user: isUserPick,
      event_type: "PICK",
      source: "manual",
    };

    set({
      isSubmitting: true,
      draftLog: [...draftLog.filter((p) => p.pick_no !== targetPickNo), optimisticPick],
      adaRankings: adaRankings.filter((p) => p.player_id !== playerId),
    });

    try {
      const res = await fetch(`${API_BASE}/api/picks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          player_id: playerId,
          pick_number: targetPickNo,
          drafted_by_user: isUserPick,
          draft_id: draftId,
          team_slot: targetTeamSlot,
        }),
      });

      if (!res.ok) {
        throw new Error("Pick submission failed");
      }

      const responseData = await res.json();
      if (responseData.state) {
        const s = responseData.state;
        set({
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          agentAdvisories: s.agent_advisories,
        });
      }
    } catch (err) {
      console.error("Failed to record pick, rolling back optimistic update:", err);
      await get().fetchState();
    } finally {
      set({ isSubmitting: false });
    }
  },

  deletePick: async (pickNo: number) => {
    console.log("🗑️ [useDraftStore] deletePick requested for pick #:", pickNo);
    set({ isSubmitting: true });
    try {
      const res = await fetch(`${API_BASE}/api/picks/${pickNo}?draft_id=${get().draftId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error("Delete pick failed");
      }

      const data = await res.json();
      if (data.state) {
        const s = data.state;
        set({
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          agentAdvisories: s.agent_advisories,
        });
      }
    } catch (err) {
      console.error("Failed to delete pick:", err);
      await get().fetchState();
    } finally {
      set({ isSubmitting: false });
    }
  },

  undoPick: async () => {
    const { draftId } = get();
    set({ isSubmitting: true });

    try {
      const res = await fetch(`${API_BASE}/api/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft_id: draftId }),
      });

      if (!res.ok) {
        throw new Error("Undo failed");
      }

      const data = await res.json();
      if (data.state) {
        const s = data.state;
        set({
          currentPick: s.current_pick,
          currentRound: s.current_round,
          teamOnClock: s.team_on_clock,
          picksUntilUserTurn: s.picks_until_user_turn,
          isUserOnClock: s.is_user_on_clock,
          draftLog: s.draft_log,
          userRoster: s.user_roster,
          rosterByPosition: s.roster_by_position,
          adaRankings: s.ada_rankings,
          agentAdvisories: s.agent_advisories,
        });
      }
    } catch (err) {
      console.error("Failed to execute undo:", err);
      await get().fetchState();
    } finally {
      set({ isSubmitting: false });
    }
  },

  resetDraft: async () => {
    const { draftId } = get();
    try {
      const res = await fetch(`${API_BASE}/api/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft_id: draftId }),
      });

      if (res.ok) {
        await get().fetchState();
      }
    } catch (err) {
      console.error("Failed to reset draft:", err);
    }
  },

  connectWebSocket: () => {
    const { draftId, wsInstance } = get();
    if (wsInstance && (wsInstance.readyState === WebSocket.OPEN || wsInstance.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      console.log("⚡ [useDraftStore] Connecting to WebSocket ws://localhost:8000/ws/draft...");
      const socket = new WebSocket(`${WS_BASE}/ws/draft?draft_id=${draftId}`);

      socket.onopen = () => {
        console.log("⚡ [useDraftStore] WebSocket connected successfully!");
        set({ wsConnected: true, wsInstance: socket });
      };

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log("⚡ [useDraftStore] WS Message received:", message.type);
          if (message.state) {
            const s = message.state;
            set({
              currentPick: s.current_pick,
              currentRound: s.current_round,
              teamOnClock: s.team_on_clock,
              picksUntilUserTurn: s.picks_until_user_turn,
              isUserOnClock: s.is_user_on_clock,
              draftLog: s.draft_log,
              userRoster: s.user_roster,
              rosterByPosition: s.roster_by_position,
              adaRankings: s.ada_rankings,
              agentAdvisories: s.agent_advisories,
              espnTeams: s.espn_teams || get().espnTeams,
              scoringFormat: s.scoring_format || get().scoringFormat,
              is3rr: s.is_3rr ?? false,
              draftStarted: s.draft_started ?? false,
            });
          }
        } catch (e) {
          console.error("Error parsing WS message:", e);
        }
      };

      socket.onclose = () => {
        console.warn("⚡ [useDraftStore] WebSocket closed. Falling back to REST polling...");
        set({ wsConnected: false, wsInstance: null });
        setTimeout(() => {
          get().connectWebSocket();
        }, 3000);
      };

      socket.onerror = (err) => {
        console.error("⚡ [useDraftStore] WebSocket error:", err);
        socket.close();
      };
    } catch (err) {
      console.error("Failed to initiate WebSocket:", err);
      set({ wsConnected: false });
    }
  },
}));

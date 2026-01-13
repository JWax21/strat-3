"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  BarChart3,
  Clock,
  Filter,
  Search,
  List,
  GitCompare,
  Eye,
  ExternalLink,
  DollarSign,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { clsx } from "clsx";

type TabType = "arbitrage" | "all-markets";

interface MarketMatch {
  normalized_name: string;
  game_date: string | null;
  sport?: string | null;
  market_for_team?: string;
  away_team?: string;
  home_team?: string;
  polymarket: {
    id: string;
    name?: string;
    yes_price: number;
    no_price: number;
    slug?: string;
    url?: string;
  };
  kalshi: {
    id: string;
    name?: string;
    yes_price: number;
    no_price: number;
    url?: string;
  };
  price_diff_yes: number;
  price_diff_no?: number;
}

interface AllMarketsData {
  polymarket: {
    total: number;
    single_game: { count: number; markets: MarketItem[] };
    futures: { count: number; markets: MarketItem[] };
  };
  kalshi: {
    total: number;
    single_game: { count: number; markets: MarketItem[] };
    futures: { count: number; markets: MarketItem[] };
  };
  matches?: {
    count: number;
    markets: MarketMatch[];
  };
  last_updated: string | null;
}

interface MarketItem {
  id: string;
  name: string;
  normalized_name?: string;
  away_team?: string | null;
  home_team?: string | null;
  game_date?: string | null;
  sport?: string | null;
  slug?: string;
  series?: string;
  yes_price: number;
  no_price: number;
  category: string;
  market_type?: string; // game_winner, spread, over_under, player_prop_points, etc.
  end_date?: string;
  expiration?: string;
}

interface ArbitrageOpportunity {
  polymarket: {
    id: string;
    question: string;
    yes_price: number;
    no_price: number;
    url: string;
    end_date: string | null;
    // Market metrics
    volume?: number;
    volume_24h?: number | null;
    open_interest?: number | null;
    liquidity?: number;
    fetched_at?: string;
  };
  kalshi: {
    id: string;
    question: string;
    yes_price: number;
    no_price: number;
    url: string;
    expected_expiration_time: string | null;
    close_time: string | null;
    // Market metrics
    volume?: number;
    volume_24h?: number;
    open_interest?: number;
    liquidity?: number | null;
    fetched_at?: string;
  };
  league: string;
  market_type: string;
  team: string | null;
  price_difference: number;
  price_difference_percent: number;
  profit_bps: number;
  buy_on: string;
  sell_on: string;
  match_score: number;
  match_reason: string;
}

interface Summary {
  total: number;
  by_league?: Record<string, number>;
  avg_difference?: number;
}

interface ApiResponse {
  opportunities: ArbitrageOpportunity[];
  summary: Summary;
  last_updated: string | null;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>("arbitrage");
  const [data, setData] = useState<ApiResponse | null>(null);
  const [allMarketsData, setAllMarketsData] = useState<AllMarketsData | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minDifference, setMinDifference] = useState<number>(2);
  const [searchQuery, setSearchQuery] = useState("");
  const [expiringWithin48h, setExpiringWithin48h] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const isLocalhost = API_BASE.includes("localhost");

  const fetchData = useCallback(async () => {
    // Skip fetch if pointing to localhost in production
    if (
      isLocalhost &&
      typeof window !== "undefined" &&
      !window.location.hostname.includes("localhost")
    ) {
      setError(
        "Backend API not configured. Set NEXT_PUBLIC_API_URL environment variable in Vercel."
      );
      setLoading(false);
      return;
    }
    try {
      let url = `${API_BASE}/api/sports/arbitrage?min_difference=${minDifference}&limit=100`;
      if (expiringWithin48h) {
        url += "&expiring_within_hours=48";
      }
      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to fetch data");
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [API_BASE, isLocalhost, minDifference, expiringWithin48h]);

  const fetchAllMarkets = useCallback(async () => {
    if (
      isLocalhost &&
      typeof window !== "undefined" &&
      !window.location.hostname.includes("localhost")
    ) {
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/sports/all-markets`);
      if (!response.ok) throw new Error("Failed to fetch all markets");
      const result = await response.json();
      setAllMarketsData(result);
    } catch (err) {
      console.error("Failed to fetch all markets:", err);
    }
  }, [API_BASE, isLocalhost]);

  const triggerRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API_BASE}/api/sports/refresh`, { method: "POST" });
      // Wait for the backend to process (sports scan takes longer)
      await new Promise((resolve) => setTimeout(resolve, 8000));
      await fetchData();
      await fetchAllMarkets();
    } catch (err) {
      setError("Failed to refresh data");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchAllMarkets();
    const interval = setInterval(() => {
      fetchData();
      fetchAllMarkets();
    }, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData, fetchAllMarkets]);

  const filteredOpportunities =
    data?.opportunities.filter((opp) => {
      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return (
        opp.polymarket.question.toLowerCase().includes(query) ||
        opp.kalshi.question.toLowerCase().includes(query) ||
        opp.kalshi.id.toLowerCase().includes(query) ||
        opp.league?.toLowerCase().includes(query) ||
        opp.team?.toLowerCase().includes(query)
      );
    }) || [];

  return (
    <div className="min-h-screen bg-midnight-950 bg-grid relative">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-glow-cyan opacity-30" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-glow-purple opacity-20" />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-midnight-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-electric-cyan/20 to-electric-purple/20 flex items-center justify-center border border-electric-cyan/30">
                  <Zap className="w-5 h-5 text-electric-cyan" />
                </div>
                <div>
                  <h1 className="text-xl font-display font-semibold tracking-tight">
                    <span className="text-gradient-cyan">Arbitrage</span>{" "}
                    Scanner
                  </h1>
                  <p className="text-xs text-white/40 font-mono">
                    Polymarket × Kalshi
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Tabs */}
              <div className="flex items-center rounded-lg bg-midnight-800 border border-white/10 p-1">
                <button
                  onClick={() => setActiveTab("arbitrage")}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                    activeTab === "arbitrage"
                      ? "bg-electric-cyan/20 text-electric-cyan"
                      : "text-white/50 hover:text-white/70"
                  )}
                >
                  <GitCompare className="w-4 h-4" />
                  Arbitrage
                </button>
                <button
                  onClick={() => setActiveTab("all-markets")}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                    activeTab === "all-markets"
                      ? "bg-electric-purple/20 text-electric-purple"
                      : "text-white/50 hover:text-white/70"
                  )}
                >
                  <List className="w-4 h-4" />
                  All Markets
                </button>
              </div>

              {/* Status indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
                <div
                  className={clsx(
                    "w-2 h-2 rounded-full",
                    data?.last_updated
                      ? "bg-profit live-indicator"
                      : "bg-yellow-500"
                  )}
                />
                <span className="text-xs text-white/60">
                  {data?.last_updated
                    ? formatDistanceToNow(new Date(data.last_updated), {
                        addSuffix: true,
                      })
                    : "No data"}
                </span>
              </div>

              {/* Refresh button */}
              <button
                onClick={triggerRefresh}
                disabled={refreshing}
                className={clsx(
                  "flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all",
                  "bg-electric-cyan/10 text-electric-cyan border border-electric-cyan/30",
                  "hover:bg-electric-cyan/20 hover:border-electric-cyan/50",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                <RefreshCw
                  className={clsx("w-4 h-4", refreshing && "animate-spin")}
                />
                {refreshing ? "Scanning..." : "Refresh"}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 relative z-10">
        {activeTab === "arbitrage" ? (
          <>
            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <StatCard
                icon={<BarChart3 className="w-5 h-5" />}
                label="Opportunities"
                value={data?.summary.total ?? 0}
                color="cyan"
              />
              <StatCard
                icon={<TrendingUp className="w-5 h-5" />}
                label="NFL Markets"
                value={data?.summary.by_league?.nfl ?? 0}
                color="profit"
              />
              <StatCard
                icon={<Activity className="w-5 h-5" />}
                label="Avg Difference"
                value={`${(data?.summary.avg_difference ?? 0).toFixed(1)}%`}
                color="purple"
              />
              <StatCard
                icon={<Zap className="w-5 h-5" />}
                label="NBA Markets"
                value={data?.summary.by_league?.nba ?? 0}
                color="orange"
              />
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-4 mb-6">
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-midnight-800 border border-white/10">
                <Search className="w-4 h-4 text-white/40" />
                <input
                  type="text"
                  placeholder="Search markets..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-transparent text-sm text-white placeholder-white/30 outline-none w-48"
                />
              </div>

              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-midnight-800 border border-white/10">
                <Filter className="w-4 h-4 text-white/40" />
                <span className="text-xs text-white/40">Min Diff:</span>
                <input
                  type="number"
                  min={0}
                  max={50}
                  step={0.5}
                  value={minDifference}
                  onChange={(e) =>
                    setMinDifference(parseFloat(e.target.value) || 0)
                  }
                  className="bg-transparent text-sm text-white outline-none w-16 text-center"
                />
                <span className="text-xs text-white/40">%</span>
              </div>

              {/* Expiration Toggle */}
              <button
                onClick={() => setExpiringWithin48h(!expiringWithin48h)}
                className={clsx(
                  "flex items-center gap-2 px-4 py-2 rounded-lg border transition-all",
                  expiringWithin48h
                    ? "bg-electric-orange/20 border-electric-orange/50 text-electric-orange"
                    : "bg-midnight-800 border-white/10 text-white/60 hover:border-white/20"
                )}
              >
                <Clock className="w-4 h-4" />
                <span className="text-xs font-medium">
                  {expiringWithin48h ? "Expiring in 48h" : "All Expirations"}
                </span>
                <div
                  className={clsx(
                    "w-8 h-4 rounded-full transition-all relative",
                    expiringWithin48h ? "bg-electric-orange/40" : "bg-white/10"
                  )}
                >
                  <div
                    className={clsx(
                      "absolute top-0.5 w-3 h-3 rounded-full transition-all",
                      expiringWithin48h
                        ? "right-0.5 bg-electric-orange"
                        : "left-0.5 bg-white/40"
                    )}
                  />
                </div>
              </button>

              <div className="text-xs text-white/40">
                Showing {filteredOpportunities.length} opportunities
              </div>
            </div>

            {/* Loading state */}
            {loading && (
              <div className="grid grid-cols-1 gap-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-32 rounded-xl skeleton" />
                ))}
              </div>
            )}

            {/* Error state */}
            {error && (
              <div className="flex items-center justify-center p-12 rounded-xl bg-loss/10 border border-loss/30">
                <AlertTriangle className="w-6 h-6 text-loss mr-3" />
                <span className="text-loss">{error}</span>
              </div>
            )}

            {/* Empty state */}
            {!loading && !error && filteredOpportunities.length === 0 && (
              <div className="flex flex-col items-center justify-center p-16 rounded-xl card-glass">
                <Activity className="w-12 h-12 text-white/20 mb-4" />
                <h3 className="text-lg font-medium text-white/60 mb-2">
                  No opportunities found
                </h3>
                <p className="text-sm text-white/40 mb-4">
                  Click refresh to scan for arbitrage opportunities
                </p>
                <button
                  onClick={triggerRefresh}
                  className="px-4 py-2 rounded-lg bg-electric-cyan/10 text-electric-cyan border border-electric-cyan/30 text-sm"
                >
                  Start Scanning
                </button>
              </div>
            )}

            {/* Opportunities list */}
            <AnimatePresence>
              <div className="grid grid-cols-1 gap-4">
                {filteredOpportunities.map((opp, index) => (
                  <OpportunityCard
                    key={index}
                    opportunity={opp}
                    index={index}
                  />
                ))}
              </div>
            </AnimatePresence>
          </>
        ) : (
          <AllMarketsTab
            data={allMarketsData}
            loading={loading}
            onRefresh={triggerRefresh}
            refreshing={refreshing}
          />
        )}
      </main>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: "cyan" | "profit" | "purple" | "orange";
}) {
  const colors = {
    cyan: "text-electric-cyan bg-electric-cyan/10 border-electric-cyan/30",
    profit: "text-profit bg-profit/10 border-profit/30",
    purple:
      "text-electric-purple bg-electric-purple/10 border-electric-purple/30",
    orange:
      "text-electric-orange bg-electric-orange/10 border-electric-orange/30",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card-glass rounded-xl p-4 card-hover"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={clsx("p-2 rounded-lg border", colors[color])}>
          {icon}
        </div>
        <span className="text-xs text-white/50 uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold font-mono animate-number">{value}</div>
    </motion.div>
  );
}

function OpportunityCard({
  opportunity,
  index,
}: {
  opportunity: ArbitrageOpportunity;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);

  const isProfitable = opportunity.price_difference_percent > 2;
  const profitColor = isProfitable ? "text-profit" : "text-white/60";

  const leagueColors: Record<string, string> = {
    nfl: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    nba: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    mlb: "bg-red-500/20 text-red-400 border-red-500/30",
    nhl: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  };

  // Get expiration time (prefer Kalshi's expected_expiration_time)
  const expirationTime =
    opportunity.kalshi.expected_expiration_time ||
    opportunity.polymarket.end_date;
  const expirationDate = expirationTime ? new Date(expirationTime) : null;
  const isExpiringSoon =
    expirationDate &&
    expirationDate.getTime() - Date.now() < 48 * 60 * 60 * 1000;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={clsx(
        "card-glass rounded-xl overflow-hidden card-hover cursor-pointer",
        isProfitable && "border-profit/20"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span
                className={clsx(
                  "px-2 py-0.5 rounded text-xs font-medium uppercase border",
                  leagueColors[opportunity.league] ||
                    "bg-white/10 text-white/60"
                )}
              >
                {opportunity.league}
              </span>
              <span className="px-2 py-0.5 rounded text-xs bg-white/5 text-white/50">
                {opportunity.market_type}
              </span>
              {opportunity.team && (
                <span className="px-2 py-0.5 rounded text-xs bg-electric-purple/20 text-electric-purple">
                  {opportunity.team}
                </span>
              )}
              {expirationDate && (
                <span
                  className={clsx(
                    "px-2 py-0.5 rounded text-xs flex items-center gap-1",
                    isExpiringSoon
                      ? "bg-electric-orange/20 text-electric-orange border border-electric-orange/30"
                      : "bg-white/5 text-white/50"
                  )}
                >
                  <Clock className="w-3 h-3" />
                  {formatDistanceToNow(expirationDate, { addSuffix: true })}
                </span>
              )}
            </div>
            <h3 className="text-sm font-medium text-white/90 line-clamp-2">
              {opportunity.polymarket.question}
            </h3>
          </div>

          <div className="text-right">
            <div className={clsx("text-2xl font-bold font-mono", profitColor)}>
              {opportunity.price_difference_percent.toFixed(1)}%
            </div>
            <div className="text-xs text-white/40">price diff</div>
          </div>
        </div>

        {/* Price comparison */}
        <div className="grid grid-cols-2 gap-4">
          <PriceCard
            platform="polymarket"
            yesPrice={opportunity.polymarket.yes_price}
            noPrice={opportunity.polymarket.no_price}
            isBuyYes={opportunity.buy_on === "polymarket"}
            isBuyNo={opportunity.sell_on === "polymarket"}
            volume={opportunity.polymarket.volume}
            volume24h={opportunity.polymarket.volume_24h}
            openInterest={opportunity.polymarket.open_interest}
            liquidity={opportunity.polymarket.liquidity}
            fetchedAt={opportunity.polymarket.fetched_at}
          />
          <PriceCard
            platform="kalshi"
            yesPrice={opportunity.kalshi.yes_price}
            noPrice={opportunity.kalshi.no_price}
            isBuyYes={opportunity.buy_on === "kalshi"}
            isBuyNo={opportunity.sell_on === "kalshi"}
            volume={opportunity.kalshi.volume}
            volume24h={opportunity.kalshi.volume_24h}
            openInterest={opportunity.kalshi.open_interest}
            liquidity={opportunity.kalshi.liquidity}
            fetchedAt={opportunity.kalshi.fetched_at}
          />
        </div>

        {/* Expanded details */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-4 pt-4 border-t border-white/10"
            >
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-white/40 text-xs mb-1">
                    Profit Potential
                  </div>
                  <div className={clsx("font-mono font-bold", profitColor)}>
                    {opportunity.profit_bps.toFixed(0)} bps
                  </div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Match Score</div>
                  <div className="font-mono">
                    {(opportunity.match_score * 100).toFixed(0)}%
                  </div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Match Reason</div>
                  <div className="font-mono text-white/60">
                    {opportunity.match_reason}
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <a
                  href={opportunity.polymarket.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-3 rounded-lg bg-white/5 text-xs font-mono text-electric-cyan hover:bg-white/10 transition"
                  onClick={(e) => e.stopPropagation()}
                >
                  View on Polymarket →
                </a>
                <a
                  href={opportunity.kalshi.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-3 rounded-lg bg-white/5 text-xs font-mono text-electric-purple hover:bg-white/10 transition"
                  onClick={(e) => e.stopPropagation()}
                >
                  View on Kalshi →
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function PriceCard({
  platform,
  yesPrice,
  noPrice,
  isBuyYes,
  isBuyNo,
  volume,
  volume24h,
  openInterest,
  liquidity,
  fetchedAt,
}: {
  platform: "polymarket" | "kalshi";
  yesPrice: number;
  noPrice: number;
  isBuyYes: boolean;
  isBuyNo: boolean;
  volume?: number;
  volume24h?: number | null;
  openInterest?: number | null;
  liquidity?: number | null;
  fetchedAt?: string;
}) {
  const badgeClass =
    platform === "polymarket" ? "badge-polymarket" : "badge-kalshi";

  // Format numbers compactly
  const formatNumber = (num: number | null | undefined): string => {
    if (num === null || num === undefined) return "—";
    if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
    if (num >= 1_000) return `$${(num / 1_000).toFixed(1)}K`;
    return `$${num.toFixed(0)}`;
  };

  return (
    <div className="p-3 rounded-lg bg-white/5">
      <div className="flex items-center justify-between mb-2">
        <span
          className={clsx(
            "px-2 py-0.5 rounded text-xs font-medium",
            badgeClass
          )}
        >
          {platform === "polymarket" ? "Polymarket" : "Kalshi"}
        </span>
        {fetchedAt && (
          <span className="text-[10px] text-white/30 font-mono">
            {new Date(fetchedAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div
          className={clsx(
            "p-2 rounded",
            isBuyYes ? "bg-profit/10 border border-profit/30" : "bg-white/5"
          )}
        >
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs text-white/50">YES</span>
            {isBuyYes && <ArrowUpRight className="w-3 h-3 text-profit" />}
          </div>
          <div
            className={clsx(
              "font-mono font-bold",
              isBuyYes ? "text-profit" : "text-white/80"
            )}
          >
            {(yesPrice * 100).toFixed(1)}¢
          </div>
        </div>

        <div
          className={clsx(
            "p-2 rounded",
            isBuyNo ? "bg-profit/10 border border-profit/30" : "bg-white/5"
          )}
        >
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs text-white/50">NO</span>
            {isBuyNo && <ArrowDownRight className="w-3 h-3 text-profit" />}
          </div>
          <div
            className={clsx(
              "font-mono font-bold",
              isBuyNo ? "text-profit" : "text-white/80"
            )}
          >
            {(noPrice * 100).toFixed(1)}¢
          </div>
        </div>
      </div>

      {/* Market metrics row */}
      <div className="mt-2 pt-2 border-t border-white/5 grid grid-cols-3 gap-1 text-[10px]">
        <div className="text-center">
          <div className="text-white/30">24h Vol</div>
          <div className="text-white/60 font-mono">
            {formatNumber(volume24h)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-white/30">Open Int</div>
          <div className="text-white/60 font-mono">
            {openInterest !== null && openInterest !== undefined
              ? formatNumber(openInterest)
              : "—"}
          </div>
        </div>
        <div className="text-center">
          <div className="text-white/30">Liquidity</div>
          <div className="text-white/60 font-mono">
            {formatNumber(liquidity)}
          </div>
        </div>
      </div>
    </div>
  );
}

interface UnifiedMarket {
  key: string;
  normalizedName: string;
  sport: string | null;
  gameDate: string | null;
  polymarket: MarketItem | null;
  kalshi: MarketItem | null;
}

function UnifiedMarketsTable({
  polyMarkets,
  kalshiMarkets,
  sportColors,
  marketTypeFilter,
}: {
  polyMarkets: MarketItem[];
  kalshiMarkets: MarketItem[];
  sportColors: Record<string, string>;
  marketTypeFilter: "moneyline" | "spread" | "over_under" | "props" | "all";
}) {
  // Helper to check market type based on API market_type field
  const matchesMarketType = (market: MarketItem): boolean => {
    const marketType = market.market_type || "";

    switch (marketTypeFilter) {
      case "moneyline":
        return marketType === "game_winner";
      case "spread":
        return marketType === "spread";
      case "over_under":
        return marketType === "over_under";
      case "props":
        return marketType.startsWith("player_prop");
      case "all":
        return true;
      default:
        return marketType === "game_winner"; // Default to moneyline
    }
  };

  // Filter markets by selected type
  const polyFiltered = polyMarkets.filter(matchesMarketType);
  const kalshiFiltered = kalshiMarkets.filter(matchesMarketType);

  // Deduplicate Polymarket markets by normalized_name + game_date + market_type
  const polyByGame = new Map<string, MarketItem>();
  for (const poly of polyFiltered) {
    // For props, include player name in key to avoid deduping different players
    const propKey = poly.market_type?.startsWith("player_prop")
      ? `-${poly.name.slice(0, 30)}`
      : "";
    const key = `${poly.normalized_name || poly.name}-${poly.game_date || ""}-${
      poly.sport || ""
    }-${poly.market_type || ""}${propKey}`;
    // Keep the first one (or could keep by highest volume)
    if (!polyByGame.has(key)) {
      polyByGame.set(key, poly);
    }
  }
  const dedupedPoly = Array.from(polyByGame.values());

  // Deduplicate Kalshi markets - they have 2 markets per game (one for each team to win)
  // Group by normalized_name + game_date + market_type and keep one (they have the same odds inverted)
  const kalshiByGame = new Map<string, MarketItem>();
  for (const kalshi of kalshiFiltered) {
    // For props, include player name in key to avoid deduping different players
    const propKey = kalshi.market_type?.startsWith("player_prop")
      ? `-${kalshi.name.slice(0, 30)}`
      : "";
    const key = `${kalshi.normalized_name || kalshi.name}-${
      kalshi.game_date || ""
    }-${kalshi.sport || ""}-${kalshi.market_type || ""}${propKey}`;
    // Keep the first one - the odds are just inverted on the second one
    if (!kalshiByGame.has(key)) {
      kalshiByGame.set(key, kalshi);
    }
  }
  const dedupedKalshi = Array.from(kalshiByGame.values());

  // Create a unified list by matching markets on normalized name
  const unifiedMarkets: UnifiedMarket[] = [];
  const usedKalshiIds = new Set<string>();

  // First, add all Polymarket markets and try to find matching Kalshi markets
  for (const poly of dedupedPoly) {
    const normalizedName = poly.normalized_name || poly.name;
    const polyKey = `${normalizedName}-${poly.game_date || ""}-${
      poly.sport || ""
    }`;

    // Find matching Kalshi market by normalized name and date (using deduplicated list)
    const matchingKalshi = dedupedKalshi.find((k) => {
      const kNormalized = k.normalized_name || k.name;
      const kKey = `${kNormalized}-${k.game_date || ""}-${k.sport || ""}`;
      return kKey === polyKey && !usedKalshiIds.has(k.id);
    });

    if (matchingKalshi) {
      usedKalshiIds.add(matchingKalshi.id);
    }

    unifiedMarkets.push({
      key: polyKey,
      normalizedName,
      sport: poly.sport || null,
      gameDate: poly.game_date || null,
      polymarket: poly,
      kalshi: matchingKalshi || null,
    });
  }

  // Add remaining Kalshi markets that weren't matched (using deduplicated list)
  for (const kalshi of dedupedKalshi) {
    if (!usedKalshiIds.has(kalshi.id)) {
      const normalizedName = kalshi.normalized_name || kalshi.name;
      unifiedMarkets.push({
        key: `kalshi-${kalshi.id}`,
        normalizedName,
        sport: kalshi.sport || null,
        gameDate: kalshi.game_date || null,
        polymarket: null,
        kalshi: kalshi,
      });
    }
  }

  // Sort by sport, then by date, then by name
  unifiedMarkets.sort((a, b) => {
    if (a.sport !== b.sport)
      return (a.sport || "").localeCompare(b.sport || "");
    if (a.gameDate !== b.gameDate)
      return (a.gameDate || "").localeCompare(b.gameDate || "");
    return a.normalizedName.localeCompare(b.normalizedName);
  });

  const matchedCount = unifiedMarkets.filter(
    (m) => m.polymarket && m.kalshi
  ).length;

  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-white/10 bg-gradient-to-r from-electric-cyan/5 to-electric-purple/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm text-white/90 font-medium">
              All Markets
            </span>
            <span className="text-xs text-white/50">
              {unifiedMarkets.length} total • {matchedCount} matched on both
              platforms
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge-polymarket px-2 py-0.5 rounded text-xs">
              Polymarket
            </span>
            <span className="badge-kalshi px-2 py-0.5 rounded text-xs">
              Kalshi
            </span>
          </div>
        </div>
      </div>
      <div className="max-h-[600px] overflow-y-auto">
        {unifiedMarkets.length === 0 ? (
          <div className="p-8 text-center text-white/40">No markets found</div>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-midnight-800 z-10">
              <tr className="text-xs text-white/50 uppercase">
                <th className="text-left p-3 w-12">Sport</th>
                <th className="text-left p-3">Event</th>
                <th className="text-center p-3 w-24">Date</th>
                <th className="text-center p-3 w-32 border-l border-white/10">
                  <span className="text-electric-cyan">Polymarket</span>
                </th>
                <th className="text-center p-3 w-32 border-l border-white/10">
                  <span className="text-electric-purple">Kalshi</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {unifiedMarkets.map((market, i) => (
                <tr
                  key={market.key + i}
                  className="hover:bg-white/5 transition"
                >
                  <td className="p-3">
                    {market.sport && (
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-[10px] font-medium uppercase border",
                          sportColors[market.sport] ||
                            "bg-white/10 text-white/60 border-white/20"
                        )}
                      >
                        {market.sport}
                      </span>
                    )}
                  </td>
                  <td className="p-3">
                    <div className="text-sm text-white/90 font-medium">
                      {market.normalizedName}
                    </div>
                  </td>
                  <td className="p-3 text-center">
                    <span className="text-xs text-white/50 font-mono">
                      {market.gameDate || "—"}
                    </span>
                  </td>
                  <td className="p-3 border-l border-white/10">
                    {market.polymarket ? (
                      <div className="flex justify-center gap-3">
                        <span className="font-mono text-profit text-sm">
                          {(market.polymarket.yes_price * 100).toFixed(0)}¢
                        </span>
                        <span className="text-white/30">/</span>
                        <span className="font-mono text-loss text-sm">
                          {(market.polymarket.no_price * 100).toFixed(0)}¢
                        </span>
                      </div>
                    ) : (
                      <span className="text-white/20 text-center block">—</span>
                    )}
                  </td>
                  <td className="p-3 border-l border-white/10">
                    {market.kalshi ? (
                      <div className="flex justify-center gap-3">
                        <span className="font-mono text-profit text-sm">
                          {(market.kalshi.yes_price * 100).toFixed(0)}¢
                        </span>
                        <span className="text-white/30">/</span>
                        <span className="font-mono text-loss text-sm">
                          {(market.kalshi.no_price * 100).toFixed(0)}¢
                        </span>
                      </div>
                    ) : (
                      <span className="text-white/20 text-center block">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Watchlist component - shows arbitrage opportunities where YES+NO < $1
function WatchlistView({
  matches,
  sportColors,
}: {
  matches: MarketMatch[];
  sportColors: Record<string, string>;
}) {
  // Calculate arbitrage opportunities
  // Arbitrage exists when buying YES on one platform and NO on the other costs < $1
  const opportunities = matches
    .map((match) => {
      const polyYes = match.polymarket.yes_price;
      const polyNo = match.polymarket.no_price;
      const kalshiYes = match.kalshi.yes_price;
      const kalshiNo = match.kalshi.no_price;

      // Strategy 1: Buy Poly YES + Kalshi NO (betting on away team via Poly, home team via Kalshi)
      const cost1 = polyYes + kalshiNo;
      const profit1 = 1.0 - cost1;

      // Strategy 2: Buy Poly NO + Kalshi YES (betting on home team via Poly, away team via Kalshi)
      const cost2 = polyNo + kalshiYes;
      const profit2 = 1.0 - cost2;

      // Choose the better strategy
      const bestProfit = Math.max(profit1, profit2);
      const strategy = profit1 >= profit2 ? 1 : 2;

      return {
        ...match,
        strategy,
        cost: strategy === 1 ? cost1 : cost2,
        profit: bestProfit,
        profitPercent: bestProfit * 100,
        polyBuy: strategy === 1 ? "YES" : "NO",
        polyPrice: strategy === 1 ? polyYes : polyNo,
        kalshiBuy: strategy === 1 ? "NO" : "YES",
        kalshiPrice: strategy === 1 ? kalshiNo : kalshiYes,
      };
    })
    .filter((opp) => opp.profit > 0) // Only show profitable opportunities
    .sort((a, b) => b.profit - a.profit); // Sort by profit descending

  // Flag suspicious entries (>15% profit might indicate flipped sides)
  const isSuspicious = (profitPercent: number) => profitPercent > 15;

  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="p-4 border-b border-white/10 bg-yellow-500/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-yellow-400" />
            <span className="text-sm text-white/90 font-medium">
              Arbitrage Watchlist
            </span>
            <span className="text-sm text-white/60">
              ({opportunities.length} opportunities where YES + NO &lt; $1)
            </span>
          </div>
          {opportunities.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-profit">
              <DollarSign className="w-3 h-3" />
              Best: {(opportunities[0]?.profitPercent || 0).toFixed(1)}% profit
            </div>
          )}
        </div>
      </div>

      <div className="max-h-[700px] overflow-y-auto">
        {opportunities.length === 0 ? (
          <div className="p-8 text-center text-white/40">
            <Eye className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p className="mb-2">No arbitrage opportunities found</p>
            <p className="text-xs">
              Opportunities appear when buying YES on one platform and NO on the
              other costs less than $1
            </p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {opportunities.map((opp, i) => (
              <div
                key={i}
                className={clsx(
                  "p-4 hover:bg-white/5 transition",
                  isSuspicious(opp.profitPercent) &&
                    "bg-red-500/5 border-l-2 border-red-500"
                )}
              >
                {/* Header row */}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      {opp.sport && (
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded text-[10px] font-medium uppercase border",
                            sportColors[opp.sport] ||
                              "bg-white/10 text-white/60 border-white/20"
                          )}
                        >
                          {opp.sport}
                        </span>
                      )}
                      <span className="text-white/90 font-medium">
                        {opp.normalized_name}
                      </span>
                    </div>
                    <div className="text-xs text-white/50">
                      {opp.game_date || "—"}
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={clsx(
                        "text-lg font-bold font-mono",
                        isSuspicious(opp.profitPercent)
                          ? "text-red-400"
                          : "text-profit"
                      )}
                    >
                      +{opp.profitPercent.toFixed(1)}%
                    </div>
                    <div className="text-xs text-white/50">
                      Cost: {(opp.cost * 100).toFixed(0)}¢
                    </div>
                  </div>
                </div>

                {/* Strategy display */}
                <div className="grid grid-cols-2 gap-4 mb-3">
                  {/* Polymarket side */}
                  <div className="bg-electric-cyan/5 rounded-lg p-3 border border-electric-cyan/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-electric-cyan font-medium uppercase">
                        Polymarket
                      </span>
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-bold",
                          opp.polyBuy === "YES"
                            ? "bg-profit/20 text-profit"
                            : "bg-loss/20 text-loss"
                        )}
                      >
                        BUY {opp.polyBuy}
                      </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-white mb-1">
                      {(opp.polyPrice * 100).toFixed(0)}¢
                    </div>
                  </div>

                  {/* Kalshi side */}
                  <div className="bg-electric-purple/5 rounded-lg p-3 border border-electric-purple/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-electric-purple font-medium uppercase">
                        Kalshi
                      </span>
                      <span
                        className={clsx(
                          "px-2 py-0.5 rounded text-xs font-bold",
                          opp.kalshiBuy === "YES"
                            ? "bg-profit/20 text-profit"
                            : "bg-loss/20 text-loss"
                        )}
                      >
                        BUY {opp.kalshiBuy}
                      </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-white mb-1">
                      {(opp.kalshiPrice * 100).toFixed(0)}¢
                    </div>
                  </div>
                </div>

                {/* Market links */}
                <div className="text-xs text-white/40 space-y-1">
                  <div className="flex items-center gap-1">
                    <span className="text-white/30">Polymarket:</span>
                    {opp.polymarket.url ? (
                      <a
                        href={opp.polymarket.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-electric-cyan/60 hover:text-electric-cyan flex items-center gap-1 truncate"
                      >
                        {opp.polymarket.name ||
                          opp.polymarket.slug ||
                          opp.polymarket.id}
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    ) : (
                      <span>{opp.polymarket.name || opp.polymarket.id}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-white/30">Kalshi:</span>
                    {opp.kalshi.url ? (
                      <a
                        href={opp.kalshi.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-electric-purple/60 hover:text-electric-purple flex items-center gap-1 truncate"
                      >
                        {opp.kalshi.name || opp.kalshi.id}
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    ) : (
                      <span>{opp.kalshi.name || opp.kalshi.id}</span>
                    )}
                  </div>
                </div>

                {/* Warning for suspicious entries */}
                {isSuspicious(opp.profitPercent) && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-red-400 bg-red-500/10 rounded p-2">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>
                      High spread detected - verify sides are correct before
                      trading
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AllMarketsTab({
  data,
  loading,
  onRefresh,
  refreshing,
}: {
  data: AllMarketsData | null;
  loading: boolean;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const [marketType, setMarketType] = useState<
    "single_game" | "futures" | "matches" | "watchlist"
  >("single_game");
  const [betType, setBetType] = useState<
    "moneyline" | "spread" | "over_under" | "props" | "all"
  >("moneyline");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSport, setSelectedSport] = useState<string | null>(null);

  // Use normalized_name from API if available, otherwise truncate original name
  const getDisplayName = (market: MarketItem): string => {
    if (market.normalized_name && market.normalized_name !== market.name) {
      return market.normalized_name;
    }
    // Fallback: truncate original name
    return market.name.length > 60
      ? market.name.substring(0, 60) + "..."
      : market.name;
  };

  // Get additional info (sport + date) for display
  const getMarketMeta = (market: MarketItem): string => {
    const parts: string[] = [];
    if (market.sport) parts.push(market.sport.toUpperCase());
    if (market.game_date) parts.push(market.game_date);
    return parts.join(" • ");
  };

  // Get markets based on selected type
  const polyMarkets =
    marketType !== "matches"
      ? data?.polymarket[marketType as "single_game" | "futures"]?.markets || []
      : [];
  const kalshiMarkets =
    marketType !== "matches"
      ? data?.kalshi[marketType as "single_game" | "futures"]?.markets || []
      : [];
  const matches = data?.matches?.markets || [];

  // Extract unique sports from both platforms
  const allSports = new Set<string>();
  polyMarkets.forEach((m) => m.sport && allSports.add(m.sport.toLowerCase()));
  kalshiMarkets.forEach((m) => m.sport && allSports.add(m.sport.toLowerCase()));
  const sportsList = Array.from(allSports).sort();

  // Sport colors for badges
  const sportColors: Record<string, string> = {
    nba: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    nfl: "bg-green-500/20 text-green-400 border-green-500/30",
    nhl: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
    mlb: "bg-red-500/20 text-red-400 border-red-500/30",
    ncaa_mbb: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    ncaa_wbb: "bg-pink-500/20 text-pink-400 border-pink-500/30",
    ufc: "bg-red-600/20 text-red-500 border-red-600/30",
    tennis: "bg-lime-500/20 text-lime-400 border-lime-500/30",
    golf: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    f1: "bg-red-500/20 text-red-400 border-red-500/30",
    nascar: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  };

  // Filter by search AND sport
  const filteredPoly = polyMarkets.filter((m) => {
    const matchesSearch =
      !searchQuery ||
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.normalized_name &&
        m.normalized_name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesSport =
      !selectedSport || m.sport?.toLowerCase() === selectedSport;
    return matchesSearch && matchesSport;
  });
  const filteredKalshi = kalshiMarkets.filter((m) => {
    const matchesSearch =
      !searchQuery ||
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.normalized_name &&
        m.normalized_name.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesSport =
      !selectedSport || m.sport?.toLowerCase() === selectedSport;
    return matchesSearch && matchesSport;
  });
  const filteredMatches = matches.filter(
    (m) =>
      !searchQuery ||
      m.normalized_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (!data && !loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 rounded-xl card-glass">
        <List className="w-12 h-12 text-white/20 mb-4" />
        <h3 className="text-lg font-medium text-white/60 mb-2">
          No market data
        </h3>
        <p className="text-sm text-white/40 mb-4">
          Click refresh to fetch markets from both platforms
        </p>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="px-4 py-2 rounded-lg bg-electric-cyan/10 text-electric-cyan border border-electric-cyan/30 text-sm"
        >
          {refreshing ? "Scanning..." : "Fetch Markets"}
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<BarChart3 className="w-5 h-5" />}
          label="Polymarket Total"
          value={data?.polymarket.total ?? 0}
          color="cyan"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="Poly Single Games"
          value={data?.polymarket.single_game?.count ?? 0}
          color="profit"
        />
        <StatCard
          icon={<Activity className="w-5 h-5" />}
          label="Kalshi Total"
          value={data?.kalshi.total ?? 0}
          color="purple"
        />
        <StatCard
          icon={<Zap className="w-5 h-5" />}
          label="Kalshi Single Games"
          value={data?.kalshi.single_game?.count ?? 0}
          color="orange"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="flex items-center rounded-lg bg-midnight-800 border border-white/10 p-1">
          <button
            onClick={() => setMarketType("watchlist")}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1.5",
              marketType === "watchlist"
                ? "bg-yellow-500/20 text-yellow-400"
                : "text-white/50 hover:text-white/70"
            )}
          >
            <Eye className="w-3.5 h-3.5" />
            Watchlist
          </button>
          <button
            onClick={() => setMarketType("single_game")}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-all",
              marketType === "single_game"
                ? "bg-electric-orange/20 text-electric-orange"
                : "text-white/50 hover:text-white/70"
            )}
          >
            Single Games
          </button>
          <button
            onClick={() => setMarketType("futures")}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-all",
              marketType === "futures"
                ? "bg-electric-purple/20 text-electric-purple"
                : "text-white/50 hover:text-white/70"
            )}
          >
            Futures / Awards
          </button>
          <button
            onClick={() => setMarketType("matches")}
            className={clsx(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-all",
              marketType === "matches"
                ? "bg-profit/20 text-profit"
                : "text-white/50 hover:text-white/70"
            )}
          >
            Matches ({data?.matches?.count ?? 0})
          </button>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-midnight-800 border border-white/10">
          <Search className="w-4 h-4 text-white/40" />
          <input
            type="text"
            placeholder="Search markets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-sm text-white placeholder-white/30 outline-none w-48"
          />
        </div>
      </div>

      {/* Sport Filter */}
      {marketType !== "matches" && sportsList.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <span className="text-xs text-white/40 uppercase tracking-wider mr-2">
            Sport:
          </span>
          <button
            onClick={() => setSelectedSport(null)}
            className={clsx(
              "px-3 py-1 rounded-full text-xs font-medium transition-all border",
              selectedSport === null
                ? "bg-white/10 text-white border-white/30"
                : "bg-transparent text-white/50 border-white/10 hover:border-white/20"
            )}
          >
            All
          </button>
          {sportsList.map((sport) => (
            <button
              key={sport}
              onClick={() =>
                setSelectedSport(selectedSport === sport ? null : sport)
              }
              className={clsx(
                "px-3 py-1 rounded-full text-xs font-medium transition-all border",
                selectedSport === sport
                  ? sportColors[sport] ||
                      "bg-white/10 text-white border-white/30"
                  : "bg-transparent text-white/50 border-white/10 hover:border-white/20"
              )}
            >
              {sport.toUpperCase()}
            </button>
          ))}
          {selectedSport && (
            <span className="text-xs text-white/40 ml-2">
              ({filteredPoly.length} Poly / {filteredKalshi.length} Kalshi)
            </span>
          )}
        </div>
      )}

      {/* Bet Type Filter */}
      {marketType !== "matches" && (
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <span className="text-xs text-white/40 uppercase tracking-wider mr-2">
            Bet Type:
          </span>
          {[
            { key: "moneyline", label: "Moneyline" },
            { key: "spread", label: "Spread" },
            { key: "over_under", label: "O/U Totals" },
            { key: "props", label: "Player Props" },
            { key: "all", label: "All Types" },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setBetType(key as typeof betType)}
              className={clsx(
                "px-3 py-1 rounded-full text-xs font-medium transition-all border",
                betType === key
                  ? "bg-electric-purple/20 text-electric-purple border-electric-purple/30"
                  : "bg-transparent text-white/50 border-white/10 hover:border-white/20"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Watchlist View - Arbitrage Opportunities */}
      {marketType === "watchlist" && (
        <WatchlistView matches={matches} sportColors={sportColors} />
      )}

      {/* Matches View */}
      {marketType === "matches" && (
        <div className="card-glass rounded-xl overflow-hidden">
          <div className="p-4 border-b border-white/10 bg-profit/5">
            <div className="flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-profit" />
              <span className="text-sm text-white/90 font-medium">
                Matched Markets
              </span>
              <span className="text-sm text-white/60">
                ({filteredMatches.length} matches found)
              </span>
            </div>
          </div>
          <div className="max-h-[600px] overflow-y-auto">
            {filteredMatches.length === 0 ? (
              <div className="p-8 text-center text-white/40">
                <GitCompare className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <p className="mb-2">
                  No matching markets found between platforms
                </p>
                <p className="text-xs">
                  Markets must have the same teams and game date to match
                </p>
              </div>
            ) : (
              <table className="w-full">
                <thead className="sticky top-0 bg-midnight-800">
                  <tr className="text-xs text-white/50 uppercase">
                    <th className="text-left p-3">Game</th>
                    <th className="text-center p-3">Date</th>
                    <th className="text-right p-3">Poly Yes</th>
                    <th className="text-right p-3">Kalshi Yes</th>
                    <th className="text-right p-3">Diff</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredMatches.map((match, i) => (
                    <tr key={i} className="hover:bg-white/5 transition">
                      <td className="p-3">
                        <div className="text-sm text-white/90 font-medium">
                          {match.normalized_name}
                        </div>
                      </td>
                      <td className="p-3 text-center">
                        <span className="text-xs text-white/60 font-mono">
                          {match.game_date || "—"}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span className="font-mono text-electric-cyan font-medium">
                          {match.polymarket?.yes_price != null
                            ? `${(match.polymarket.yes_price * 100).toFixed(
                                0
                              )}¢`
                            : "—"}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span className="font-mono text-electric-purple font-medium">
                          {match.kalshi?.yes_price != null
                            ? `${(match.kalshi.yes_price * 100).toFixed(0)}¢`
                            : "—"}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <span
                          className={clsx(
                            "font-mono font-medium",
                            (match.price_diff_yes ?? 0) >= 3
                              ? "text-profit"
                              : "text-white/50"
                          )}
                        >
                          {match.price_diff_yes != null
                            ? `${match.price_diff_yes.toFixed(1)}%`
                            : "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Unified market table (for single_game and futures) */}
      {marketType !== "matches" && (
        <UnifiedMarketsTable
          polyMarkets={filteredPoly}
          kalshiMarkets={filteredKalshi}
          sportColors={sportColors}
          marketTypeFilter={betType}
        />
      )}

      {/* Last updated */}
      {data?.last_updated && (
        <div className="mt-4 text-center text-xs text-white/40">
          Last updated:{" "}
          {formatDistanceToNow(new Date(data.last_updated), {
            addSuffix: true,
          })}
        </div>
      )}
    </div>
  );
}

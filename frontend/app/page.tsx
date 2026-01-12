'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
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
  Search
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'

interface ArbitrageOpportunity {
  matched_market: {
    polymarket: {
      question: string
      yes_price: number
      no_price: number
      volume: number
      category: string
    }
    kalshi: {
      question: string
      ticker: string
      yes_price: number
      no_price: number
      volume: number
      category: string
    }
    similarity_score: number
  }
  poly_yes_price: number
  poly_no_price: number
  kalshi_yes_price: number
  kalshi_no_price: number
  price_difference: number
  price_difference_percent: number
  potential_profit_bps: number
  buy_yes_on: string
  buy_no_on: string
  profitable: boolean
  description: string
  detected_at: string
}

interface Summary {
  total_opportunities: number
  profitable_count: number
  avg_price_difference_percent: number
  max_price_difference_percent: number
  avg_profit_bps: number
  max_profit_bps: number
}

interface ApiResponse {
  opportunities: ArbitrageOpportunity[]
  summary: Summary
  last_updated: string | null
  is_stale: boolean
}

export default function Dashboard() {
  const [data, setData] = useState<ApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [minDifference, setMinDifference] = useState<number>(2)
  const [searchQuery, setSearchQuery] = useState('')

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const isLocalhost = API_BASE.includes('localhost')

  const fetchData = useCallback(async () => {
    // Skip fetch if pointing to localhost in production
    if (isLocalhost && typeof window !== 'undefined' && !window.location.hostname.includes('localhost')) {
      setError('Backend API not configured. Set NEXT_PUBLIC_API_URL environment variable in Vercel.')
      setLoading(false)
      return
    }
    try {
      const response = await fetch(`${API_BASE}/api/arbitrage?min_difference=${minDifference}&limit=100`)
      if (!response.ok) throw new Error('Failed to fetch data')
      const result = await response.json()
      setData(result)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [minDifference])

  const triggerRefresh = async () => {
    setRefreshing(true)
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      await fetch(`${apiBase}/api/arbitrage/refresh`, { method: 'POST' })
      // Wait a bit for the backend to process
      await new Promise(resolve => setTimeout(resolve, 3000))
      await fetchData()
    } catch (err) {
      setError('Failed to refresh data')
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [fetchData])

  const filteredOpportunities = data?.opportunities.filter(opp => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      opp.matched_market.polymarket.question.toLowerCase().includes(query) ||
      opp.matched_market.kalshi.question.toLowerCase().includes(query) ||
      opp.matched_market.kalshi.ticker.toLowerCase().includes(query)
    )
  }) || []

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
                    <span className="text-gradient-cyan">Arbitrage</span> Scanner
                  </h1>
                  <p className="text-xs text-white/40 font-mono">Polymarket × Kalshi</p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Status indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
                <div className={clsx(
                  "w-2 h-2 rounded-full",
                  data?.is_stale ? "bg-yellow-500" : "bg-profit live-indicator"
                )} />
                <span className="text-xs text-white/60">
                  {data?.last_updated 
                    ? formatDistanceToNow(new Date(data.last_updated), { addSuffix: true })
                    : 'No data'}
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
                <RefreshCw className={clsx("w-4 h-4", refreshing && "animate-spin")} />
                {refreshing ? 'Scanning...' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 relative z-10">
        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={<BarChart3 className="w-5 h-5" />}
            label="Opportunities"
            value={data?.summary.total_opportunities ?? 0}
            color="cyan"
          />
          <StatCard
            icon={<TrendingUp className="w-5 h-5" />}
            label="Profitable"
            value={data?.summary.profitable_count ?? 0}
            color="profit"
          />
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Avg Difference"
            value={`${(data?.summary.avg_price_difference_percent ?? 0).toFixed(1)}%`}
            color="purple"
          />
          <StatCard
            icon={<Zap className="w-5 h-5" />}
            label="Max Profit"
            value={`${(data?.summary.max_profit_bps ?? 0).toFixed(0)} bps`}
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
              onChange={(e) => setMinDifference(parseFloat(e.target.value) || 0)}
              className="bg-transparent text-sm text-white outline-none w-16 text-center"
            />
            <span className="text-xs text-white/40">%</span>
          </div>

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
            <h3 className="text-lg font-medium text-white/60 mb-2">No opportunities found</h3>
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
              <OpportunityCard key={index} opportunity={opp} index={index} />
            ))}
          </div>
        </AnimatePresence>
      </main>
    </div>
  )
}

function StatCard({ 
  icon, 
  label, 
  value, 
  color 
}: { 
  icon: React.ReactNode
  label: string
  value: string | number
  color: 'cyan' | 'profit' | 'purple' | 'orange'
}) {
  const colors = {
    cyan: 'text-electric-cyan bg-electric-cyan/10 border-electric-cyan/30',
    profit: 'text-profit bg-profit/10 border-profit/30',
    purple: 'text-electric-purple bg-electric-purple/10 border-electric-purple/30',
    orange: 'text-electric-orange bg-electric-orange/10 border-electric-orange/30',
  }

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
        <span className="text-xs text-white/50 uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold font-mono animate-number">{value}</div>
    </motion.div>
  )
}

function OpportunityCard({ opportunity, index }: { opportunity: ArbitrageOpportunity; index: number }) {
  const [expanded, setExpanded] = useState(false)
  
  const isProfitable = opportunity.profitable
  const profitColor = isProfitable ? 'text-profit' : 'text-white/60'
  
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
              {isProfitable && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-profit/20 text-profit border border-profit/30">
                  PROFITABLE
                </span>
              )}
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-white/5 text-white/50">
                {opportunity.matched_market.kalshi.ticker}
              </span>
            </div>
            <h3 className="text-sm font-medium text-white/90 line-clamp-2">
              {opportunity.matched_market.polymarket.question}
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
            yesPrice={opportunity.poly_yes_price}
            noPrice={opportunity.poly_no_price}
            isBuyYes={opportunity.buy_yes_on === 'polymarket'}
            isBuyNo={opportunity.buy_no_on === 'polymarket'}
          />
          <PriceCard
            platform="kalshi"
            yesPrice={opportunity.kalshi_yes_price}
            noPrice={opportunity.kalshi_no_price}
            isBuyYes={opportunity.buy_yes_on === 'kalshi'}
            isBuyNo={opportunity.buy_no_on === 'kalshi'}
          />
        </div>

        {/* Expanded details */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="mt-4 pt-4 border-t border-white/10"
            >
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-white/40 text-xs mb-1">Profit Potential</div>
                  <div className={clsx("font-mono font-bold", profitColor)}>
                    {opportunity.potential_profit_bps.toFixed(0)} bps
                  </div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Match Score</div>
                  <div className="font-mono">
                    {(opportunity.matched_market.similarity_score * 100).toFixed(0)}%
                  </div>
                </div>
                <div>
                  <div className="text-white/40 text-xs mb-1">Detected</div>
                  <div className="font-mono text-white/60">
                    {formatDistanceToNow(new Date(opportunity.detected_at), { addSuffix: true })}
                  </div>
                </div>
              </div>
              
              <div className="mt-4 p-3 rounded-lg bg-white/5 text-xs font-mono text-white/60">
                <span className="text-white/40">Strategy:</span> {opportunity.description}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function PriceCard({ 
  platform, 
  yesPrice, 
  noPrice, 
  isBuyYes, 
  isBuyNo 
}: {
  platform: 'polymarket' | 'kalshi'
  yesPrice: number
  noPrice: number
  isBuyYes: boolean
  isBuyNo: boolean
}) {
  const badgeClass = platform === 'polymarket' ? 'badge-polymarket' : 'badge-kalshi'
  
  return (
    <div className="p-3 rounded-lg bg-white/5">
      <div className="flex items-center justify-between mb-2">
        <span className={clsx("px-2 py-0.5 rounded text-xs font-medium", badgeClass)}>
          {platform === 'polymarket' ? 'Polymarket' : 'Kalshi'}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-2">
        <div className={clsx(
          "p-2 rounded",
          isBuyYes ? "bg-profit/10 border border-profit/30" : "bg-white/5"
        )}>
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs text-white/50">YES</span>
            {isBuyYes && <ArrowUpRight className="w-3 h-3 text-profit" />}
          </div>
          <div className={clsx("font-mono font-bold", isBuyYes ? "text-profit" : "text-white/80")}>
            {(yesPrice * 100).toFixed(1)}¢
          </div>
        </div>
        
        <div className={clsx(
          "p-2 rounded",
          isBuyNo ? "bg-profit/10 border border-profit/30" : "bg-white/5"
        )}>
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs text-white/50">NO</span>
            {isBuyNo && <ArrowDownRight className="w-3 h-3 text-profit" />}
          </div>
          <div className={clsx("font-mono font-bold", isBuyNo ? "text-profit" : "text-white/80")}>
            {(noPrice * 100).toFixed(1)}¢
          </div>
        </div>
      </div>
    </div>
  )
}


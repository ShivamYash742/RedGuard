"use client"
import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { Search, Play, Activity, ShieldCheck, Zap } from 'lucide-react'
import { Button } from './ui/button'

interface TopBarProps {
  onOpenSearch: () => void
}

export default function TopBar({ onOpenSearch }: TopBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health')
        if (res.ok) {
          const data = await res.json()
          setIsBackendHealthy(data.status === 'ok')
        } else {
          setIsBackendHealthy(false)
        }
      } catch {
        setIsBackendHealthy(false)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const getPageTitle = (path: string) => {
    if (path === '/') return 'Dashboard Overview'
    if (path.startsWith('/attack-families')) return 'Attack Families'
    if (path.startsWith('/probes')) return 'Probes Directory'
    if (path.startsWith('/scenarios')) return 'Scenarios & Agents'
    if (path.startsWith('/benchmark') || path.startsWith('/scan')) return 'Live Benchmark Engine'
    if (path.startsWith('/results')) return 'Evaluation Results & Analytics'
    if (path.startsWith('/comparison')) return 'Model Comparison Leaderboard'
    if (path.startsWith('/reports')) return 'Security Audit Reports'
    if (path.startsWith('/history')) return 'Benchmark History'
    if (path.startsWith('/datasets')) return 'Dataset Coverage'
    return 'RedGuard Security'
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border/60 bg-background/80 px-6 backdrop-blur-md">
      {/* Title & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-primary" />
          <h1 className="text-base font-semibold text-foreground tracking-tight">
            {getPageTitle(pathname)}
          </h1>
        </div>
        <span className="hidden md:inline-block text-xs font-mono px-2 py-0.5 rounded bg-muted/60 text-muted-foreground border border-border/40">
          v1.0.0
        </span>
      </div>

      {/* Center Search Trigger */}
      <div className="flex-1 max-w-md mx-4 hidden sm:block">
        <button
          onClick={onOpenSearch}
          className="w-full flex items-center justify-between h-9 px-3 text-xs text-muted-foreground bg-card/60 hover:bg-card border border-border/60 rounded-lg transition-all shadow-sm group"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
            <span>Search probes, families, scenarios, models...</span>
          </div>
          <kbd className="hidden lg:inline-block px-1.5 py-0.5 text-[10px] font-mono rounded bg-muted text-muted-foreground border border-border/40">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right Action Controls */}
      <div className="flex items-center gap-3">
        {/* Backend Status Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-card border border-border/60 text-xs font-mono">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
              isBackendHealthy === true ? 'bg-emerald-400' : isBackendHealthy === false ? 'bg-amber-400' : 'bg-slate-400'
            }`} />
            <span className={`relative inline-flex rounded-full h-2 w-2 ${
              isBackendHealthy === true ? 'bg-emerald-500' : isBackendHealthy === false ? 'bg-amber-500' : 'bg-slate-500'
            }`} />
          </span>
          <span className="text-muted-foreground text-[11px]">
            {isBackendHealthy === true ? 'FastAPI Online' : isBackendHealthy === false ? 'Mock Data Active' : 'Checking API...'}
          </span>
        </div>

        {/* Quick Launch CTA */}
        <Button 
          onClick={() => router.push('/benchmark')} 
          size="sm" 
          className="gap-1.5 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-500 text-white shadow-md shadow-primary/20"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          <span className="hidden sm:inline">New Benchmark</span>
        </Button>
      </div>
    </header>
  )
}

"use client"
import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  LayoutDashboard, ShieldAlert, Terminal, Boxes, PlayCircle, 
  BarChart3, Trophy, FileText, History, Database, ChevronLeft, ChevronRight,
  ShieldCheck, ExternalLink
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  const navItems = [
    { label: 'Dashboard', href: '/', icon: LayoutDashboard },
    { label: 'Attack Families', href: '/attack-families', icon: ShieldAlert, badge: '8' },
    { label: 'Probes Directory', href: '/probes', icon: Terminal, badge: '50+' },
    { label: 'Scenarios', href: '/scenarios', icon: Boxes },
    { label: 'Live Benchmark', href: '/benchmark', icon: PlayCircle, highlight: true },
    { label: 'Results & Analytics', href: '/results', icon: BarChart3 },
    { label: 'Model Leaderboard', href: '/comparison', icon: Trophy },
    { label: 'Audit Reports', href: '/reports', icon: FileText },
    { label: 'Benchmark History', href: '/history', icon: History },
    { label: 'Dataset Coverage', href: '/datasets', icon: Database },
  ]

  return (
    <aside className={cn(
      "relative z-40 flex flex-col h-screen border-r border-border/60 bg-card/90 backdrop-blur-md transition-all duration-300 select-none",
      collapsed ? "w-16" : "w-64"
    )}>
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-border/60">
        <Link href="/" className="flex items-center gap-3 overflow-hidden">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500 via-primary to-indigo-600 shadow-lg shadow-rose-500/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-extrabold text-base tracking-wider gradient-text-red">REDGUARD</span>
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">AI Safety Benchmark</span>
            </div>
          )}
        </Link>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group relative",
                isActive 
                  ? "bg-primary/15 text-primary border border-primary/20 shadow-sm" 
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                item.highlight && !isActive && "text-rose-400 hover:text-rose-300"
              )}
            >
              <Icon className={cn(
                "w-5 h-5 shrink-0 transition-transform group-hover:scale-110",
                isActive ? "text-primary" : item.highlight ? "text-rose-500" : "text-muted-foreground group-hover:text-foreground"
              )} />

              {!collapsed && (
                <div className="flex flex-1 items-center justify-between overflow-hidden">
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border/40">
                      {item.badge}
                    </span>
                  )}
                  {item.highlight && (
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                    </span>
                  )}
                </div>
              )}
            </Link>
          )
        })}
      </div>

      {/* Footer Info */}
      {!collapsed && (
        <div className="p-3 m-3 rounded-xl bg-muted/40 border border-border/40 text-xs">
          <div className="flex items-center justify-between font-mono text-[11px] text-muted-foreground mb-1">
            <span>DPI Engine</span>
            <span className="text-emerald-400">Active</span>
          </div>
          <p className="text-[11px] text-muted-foreground line-clamp-2">
            Multi-modal red-teaming benchmark for ReAct agent safety.
          </p>
        </div>
      )}
    </aside>
  )
}

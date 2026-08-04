import React from 'react'
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: string | number
  subtext?: string
  trend?: string
  trendUp?: boolean
  icon?: LucideIcon
  variant?: 'default' | 'danger' | 'success' | 'indigo'
}

export default function StatCard({
  label,
  value,
  subtext,
  trend,
  trendUp,
  icon: Icon,
  variant = 'default'
}: StatCardProps) {
  const getGlow = () => {
    if (variant === 'danger') return 'border-rose-500/30 hover:border-rose-500/60 shadow-rose-500/5'
    if (variant === 'success') return 'border-emerald-500/30 hover:border-emerald-500/60 shadow-emerald-500/5'
    if (variant === 'indigo') return 'border-indigo-500/30 hover:border-indigo-500/60 shadow-indigo-500/5'
    return 'border-border/60 hover:border-primary/50'
  }

  const getIconColor = () => {
    if (variant === 'danger') return 'text-rose-400 bg-rose-500/10 border-rose-500/20'
    if (variant === 'success') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
    if (variant === 'indigo') return 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20'
    return 'text-primary bg-primary/10 border-primary/20'
  }

  return (
    <div className={cn(
      "glass-card p-5 rounded-xl border transition-all duration-300 hover:-translate-y-1 shadow-lg",
      getGlow()
    )}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{label}</span>
        {Icon && (
          <div className={cn("p-2 rounded-lg border", getIconColor())}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className="text-3xl font-extrabold tracking-tight text-foreground font-mono">
          {value}
        </span>
        {trend && (
          <div className={cn(
            "flex items-center text-xs font-mono font-medium px-2 py-0.5 rounded-full border",
            trendUp ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" : "text-rose-400 bg-rose-500/10 border-rose-500/20"
          )}>
            {trendUp ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
            {trend}
          </div>
        )}
      </div>

      {subtext && (
        <p className="mt-2 text-xs text-muted-foreground line-clamp-1">{subtext}</p>
      )}
    </div>
  )
}

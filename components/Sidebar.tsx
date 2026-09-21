"use client"
import React, { useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Boxes,
  PlayCircle,
  FlaskConical,
  Award,
  Settings,
  X,
} from 'lucide-react'
import { benchmarkDataService } from '@/lib/data-service'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname()
  const probeCount = benchmarkDataService.getAllProbes().length

  useEffect(() => {
    onClose()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  const navItems = [
    { name: 'Overview', path: '/', icon: LayoutDashboard },
    { name: 'Corpus', path: '/corpus', icon: Boxes, count: String(probeCount) },
    { name: 'Runs', path: '/runs', icon: PlayCircle },
    { name: 'Lab', path: '/lab', icon: FlaskConical, count: 'β' },
    { name: 'Models', path: '/models', icon: Award },
    { name: 'Settings', path: '/settings', icon: Settings },
  ]

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`w-64 border-r border-[var(--border-subtle)] bg-[var(--surface-raised)] flex flex-col h-[calc(100vh-3.5rem)] shrink-0 fixed top-14 left-0 z-40 transition-transform duration-200 lg:sticky lg:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
      >
        {/* Section Header */}
        <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
          <span>Navigation</span>
          <button onClick={onClose} className="p-0.5 rounded hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)] lg:hidden">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Nav List */}
        <nav className="flex-1 overflow-y-auto p-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path))
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`flex items-center justify-between px-3 py-2 rounded-[var(--radius)] text-xs font-medium transition-colors ${isActive
                    ? 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/25 font-semibold'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)]'
                  }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className={`h-4 w-4 ${isActive ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`} />
                  <span>{item.name}</span>
                </div>
                {item.count && (
                  <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-[var(--surface-base)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                    {item.count}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        {/* Bottom build tag */}
        <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--surface-base)] text-[11px] text-[var(--text-muted)] font-mono">
          RedGuard v2.7.5
        </div>
      </aside>
    </>
  )
}

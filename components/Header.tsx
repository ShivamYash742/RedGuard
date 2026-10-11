"use client"
import React, { useSyncExternalStore } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { Search, Moon, Sun, Play, Layers, Menu } from 'lucide-react'

interface HeaderProps {
  onOpenSearch: () => void
  onOpenSidebar: () => void
}

// The inline script in app/layout.tsx sets the class before hydration; the
// <html> class is the single source of truth for the theme.
const subscribeTheme = (onChange: () => void) => {
  window.addEventListener('themechange', onChange)
  return () => window.removeEventListener('themechange', onChange)
}
const readTheme = () => document.documentElement.classList.contains('dark')

export default function Header({ onOpenSearch, onOpenSidebar }: HeaderProps) {
  const isDark = useSyncExternalStore(subscribeTheme, readTheme, () => true)

  const toggleTheme = () => {
    const next = !isDark
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
    window.dispatchEvent(new Event('themechange'))
  }

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--surface-raised)]/95 px-4 sm:px-6 backdrop-blur-md">
      {/* Left: Brand logo & version tags */}
      <div className="flex items-center gap-4">
        <button
          onClick={onOpenSidebar}
          aria-label="Open navigation"
          className="p-1.5 -ml-1.5 rounded-md text-[var(--text-secondary)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)] transition-colors lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link href="/" className="flex items-center gap-2.5 text-sm font-bold tracking-tight text-[var(--text-primary)]">
          <div className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)] bg-[var(--primary)]/15 p-1 border border-[var(--primary)]/35">
            <Image src="/shield.svg" alt="RedGuard Shield Logo" width={20} height={20} className="h-5 w-5" unoptimized />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-black leading-none text-[var(--text-primary)] tracking-tight">RedGuard</span>
            <span className="text-[10px] font-mono text-[var(--primary)] leading-none mt-0.5 font-semibold whitespace-nowrap">AI Security Benchmark</span>
          </div>
        </Link>

        <div className="hidden sm:flex items-center gap-2 border-l border-[var(--border-subtle)] pl-4 text-xs font-mono">
          <span className="inline-flex items-center gap-1 rounded-[var(--radius)] bg-[var(--surface-base)] px-2 py-0.5 text-[var(--text-secondary)] border border-[var(--border-subtle)]">
            <Layers className="h-3 w-3 text-[var(--primary)]" /> Benchmark v3.0.0
          </span>
        </div>
      </div>

      {/* Middle: Search bar trigger */}
      <div className="mx-2 sm:mx-6 md:flex-1 md:max-w-md">
        <button
          onClick={onOpenSearch}
          aria-label="Search"
          className="flex md:w-full items-center justify-between rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-3 py-1.5 text-xs text-[var(--text-muted)] transition-colors hover:border-[var(--border-default)]"
        >
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5" />
            <span className="hidden md:inline">Search probes, attack families, scenarios, models...</span>
          </div>
          <kbd className="hidden sm:inline-block font-mono text-[10px] bg-[var(--surface-raised)] border border-[var(--border-subtle)] px-1.5 py-0.5 rounded text-[var(--text-muted)]">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: theme toggle and Run CTA */}
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={toggleTheme}
          title="Toggle Light/Dark Theme"
          className="p-1.5 rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--surface-base)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {isDark ? <Sun className="h-4 w-4 text-[var(--warning)]" /> : <Moon className="h-4 w-4 text-[var(--text-secondary)]" />}
        </button>

        <Link
          href="/runs"
          aria-label="Run Benchmark"
          className="flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--primary)] px-3 py-1.5 text-xs font-semibold text-[var(--primary-foreground)] shadow-xs transition-colors hover:bg-[var(--primary-hover)]"
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span className="hidden sm:inline">Run Benchmark</span>
        </Link>
      </div>
    </header>
  )
}

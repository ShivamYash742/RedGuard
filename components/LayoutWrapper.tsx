"use client"
import React, { useState } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { GlobalSearch } from './GlobalSearch'

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const [isSearchOpen, setIsSearchOpen] = useState(false)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main viewport */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar onOpenSearch={() => setIsSearchOpen(true)} />

        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-8">
            {children}
          </div>
        </main>
      </div>

      {/* Command Palette Search Modal */}
      <GlobalSearch isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
    </div>
  )
}

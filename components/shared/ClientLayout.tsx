"use client"
import React, { useState } from 'react'
import Header from '@/components/shared/Header'
import Sidebar from '@/components/shared/Sidebar'
import GlobalSearchModal from '@/components/shared/GlobalSearchModal'

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <div className="flex flex-col min-h-screen">
      <Header onOpenSearch={() => setIsSearchOpen(true)} onOpenSidebar={() => setIsSidebarOpen(true)} />
      <div className="flex flex-1">
        <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
        <main className="flex-1 p-6 overflow-y-auto max-w-7xl mx-auto w-full min-w-0">
          {children}
        </main>
      </div>
      <GlobalSearchModal isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
    </div>
  )
}

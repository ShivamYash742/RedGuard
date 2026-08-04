"use client"
import React, { useState } from 'react'
import './globals.css'
import Sidebar from '@/components/Sidebar'
import Header from '@/components/Header'
import GlobalSearchModal from '@/components/GlobalSearchModal'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [isSearchOpen, setIsSearchOpen] = useState(false)

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-[var(--surface-base)] text-[var(--text-primary)] antialiased" suppressHydrationWarning>
        <div className="flex flex-col min-h-screen">
          <Header onOpenSearch={() => setIsSearchOpen(true)} />
          <div className="flex flex-1">
            <Sidebar />
            <main className="flex-1 p-6 overflow-y-auto max-w-7xl mx-auto w-full">
              {children}
            </main>
          </div>
        </div>
        <GlobalSearchModal isOpen={isSearchOpen} onClose={() => setIsSearchOpen(false)} />
      </body>
    </html>
  )
}

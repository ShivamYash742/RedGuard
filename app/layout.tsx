import './globals.css'
import type { Metadata } from 'next'
import LayoutWrapper from '@/components/LayoutWrapper'

export const metadata: Metadata = {
  title: 'RedGuard | AI Security & Red-Teaming Benchmark',
  description: 'Unified Automated Security Evaluation Dashboard for AI Agents',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-background text-foreground antialiased selection:bg-primary/20">
        <LayoutWrapper>
          {children}
        </LayoutWrapper>
      </body>
    </html>
  )
}

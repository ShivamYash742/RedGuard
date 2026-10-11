import type { Metadata } from 'next'
import { IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google'
import './globals.css'
import ClientLayout from '@/components/shared/ClientLayout'

const plexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'RedGuard v4.2.0 | AI Agent Security Benchmark',
  description: 'Academic AI Agent Security Evaluation Platform based on DeepMind Traps Taxonomy',
  icons: {
    icon: '/shield.svg',
    shortcut: '/shield.svg',
    apple: '/shield.svg',
  },
}

/*
THESIS: The benchmark is a wall of locked boxes; showing whether a model resists
an attack, not a leaderboard score, is the product.
OWN-WORLD: Brushed steel plates on gunmetal ground, brass accent for action and
selection, hazard-amber for compromised, verdigris for secure. One workhorse
sans (IBM Plex); engraved-caps numerals for scores and counts. Ledger-ruled
tables. No skeuomorphic 3D chrome — restrained material language only.
STORY: A security engineer scans the vault wall, opens a box to read its
evidence, and decides which model to ship.
FIRST VIEWPORT: Overview — steel scorecards row (verdicts read as sealed or
breached), then a numbered grid of attack-family panels below.
FORM: Vault & Safety-Deposit Security, direction 3 of 7 grounded candidates,
seed key 09c41416.
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, and DESIGN.md
*/
const DIRECTION_CONTRACT = `<!--
THESIS: The benchmark is a wall of locked boxes; showing whether a model resists an attack, not a leaderboard score, is the product.
OWN-WORLD: Brushed steel plates on gunmetal ground, brass accent for action and selection, hazard-amber for compromised, verdigris for secure. One workhorse sans (IBM Plex); engraved-caps numerals for scores and counts. Ledger-ruled tables. No skeuomorphic 3D chrome.
STORY: A security engineer scans the vault wall, opens a box to read its evidence, and decides which model to ship.
FIRST VIEWPORT: Overview — steel scorecards row (verdicts read as sealed or breached), then a numbered grid of attack-family panels below.
FORM: Vault & Safety-Deposit Security, direction 3 of 7 grounded candidates, seed key 09c41416.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${plexSans.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head>
        <link rel="icon" href="/shield.svg" type="image/svg+xml" />
        <script
          dangerouslySetInnerHTML={{
            __html: `try{document.documentElement.classList.toggle('dark',localStorage.getItem('theme')!=='light')}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen bg-[var(--surface-base)] text-[var(--text-primary)] antialiased" suppressHydrationWarning>
        <div style={{ display: 'contents' }} dangerouslySetInnerHTML={{ __html: DIRECTION_CONTRACT }} />
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  )
}

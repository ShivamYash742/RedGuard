"use client"
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function Sidebar() {
  const pathname = usePathname()

  const navItems = [
    { name: 'Overview', path: '/' },
    { name: 'Run Evaluation', path: '/scan' },
    { name: 'Evaluation Traces', path: '/audit' },
    { name: 'Benchmark Results', path: '/reports' },
    { name: 'Methodology', path: '/policy' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        📊 RedGuard Benchmark
      </div>
      <nav>
        {navItems.map((item) => {
          const isActive = pathname === item.path
          return (
            <Link 
              key={item.path} 
              href={item.path}
              className={`nav-link ${isActive ? 'active' : ''}`}
            >
              {item.name}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

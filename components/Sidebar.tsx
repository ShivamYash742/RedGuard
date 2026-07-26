"use client"
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function Sidebar() {
  const pathname = usePathname()

  const navItems = [
    { name: 'Dashboard', path: '/' },
    { name: 'Live Scan', path: '/scan' },
    { name: 'Audit Log', path: '/audit' },
    { name: 'Reports', path: '/reports' },
    { name: 'Policy', path: '/policy' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        🛡️ RedGuard
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

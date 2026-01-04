import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Video, List, Wand2 } from 'lucide-react'
import { useHealth } from '@/hooks/useJobs'

const navigation = [
  { name: 'Playground', href: '/', icon: Wand2 },
  { name: 'Jobs', href: '/jobs', icon: List },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { data: health, isError } = useHealth()

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <div className="mr-4 flex">
            <Link to="/" className="mr-6 flex items-center space-x-2">
              <Video className="h-6 w-6" />
              <span className="font-bold">i2v Studio</span>
            </Link>
          </div>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center space-x-2 transition-colors hover:text-foreground/80',
                    isActive ? 'text-foreground' : 'text-foreground/60'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
          <div className="ml-auto flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div
                className={cn(
                  'h-2 w-2 rounded-full',
                  health?.status === 'ok' ? 'bg-green-500' : isError ? 'bg-red-500' : 'bg-yellow-500'
                )}
              />
              <span className="text-xs text-muted-foreground">
                {health?.status === 'ok' ? 'API Connected' : isError ? 'API Offline' : 'Connecting...'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container py-6">{children}</main>
    </div>
  )
}

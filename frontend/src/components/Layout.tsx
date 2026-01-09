import { Link, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Video, List, Wand2, LayoutTemplate, LogOut, User, CreditCard } from 'lucide-react'
import { useHealth } from '@/hooks/useJobs'
import { useAuth } from '@/contexts/AuthContext'

const navigation = [
  { name: 'Playground', href: '/', icon: Wand2 },
  { name: 'Templates', href: '/templates', icon: LayoutTemplate },
  { name: 'Jobs', href: '/jobs', icon: List },
]

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: health, isError } = useHealth()
  const { user, isAuthenticated, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

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
            {/* API Status */}
            <div
              className="flex items-center space-x-2 cursor-help"
              title={health?.status === 'ok'
                ? 'Backend connected and healthy'
                : isError
                  ? 'Backend disconnected. Try restarting the server from Jobs page.'
                  : 'Checking backend connection...'}
            >
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

            {/* Auth Section */}
            {isAuthenticated && user ? (
              <>
                {/* Credits */}
                <div className="flex items-center space-x-1.5 rounded-md bg-muted px-2.5 py-1">
                  <CreditCard className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium">{user.credits_balance.toLocaleString()}</span>
                  <span className="text-xs text-muted-foreground">credits</span>
                </div>

                {/* Tier Badge */}
                <span className={cn(
                  'rounded-full px-2 py-0.5 text-xs font-medium',
                  user.tier === 'free' && 'bg-gray-100 text-gray-700',
                  user.tier === 'starter' && 'bg-blue-100 text-blue-700',
                  user.tier === 'pro' && 'bg-purple-100 text-purple-700',
                  user.tier === 'agency' && 'bg-amber-100 text-amber-700',
                )}>
                  {user.tier}
                </span>

                {/* User Menu */}
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                    {user.email}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="p-1.5 rounded-md hover:bg-muted transition-colors"
                    title="Sign out"
                  >
                    <LogOut className="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              </>
            ) : (
              <Link
                to="/login"
                className={cn(
                  'flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-sm font-medium',
                  'bg-primary text-primary-foreground hover:bg-primary/90',
                  'transition-colors'
                )}
              >
                <User className="h-4 w-4" />
                <span>Sign in</span>
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container py-6 px-4 lg:px-8">{children}</main>
    </div>
  )
}

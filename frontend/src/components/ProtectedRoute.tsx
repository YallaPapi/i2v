import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Loader2 } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRole?: string
  requiredTier?: string
}

// Tier hierarchy for comparison
const TIER_ORDER: Record<string, number> = {
  free: 0,
  starter: 1,
  pro: 2,
  agency: 3,
}

export function ProtectedRoute({
  children,
  requiredRole,
  requiredTier,
}: ProtectedRouteProps) {
  const { user, isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Not authenticated - redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  // Check role if required
  if (requiredRole && user?.role !== requiredRole) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">Access Denied</h1>
          <p className="text-muted-foreground">
            You need {requiredRole} privileges to access this page.
          </p>
        </div>
      </div>
    )
  }

  // Check tier if required
  if (requiredTier && user) {
    const userTierLevel = TIER_ORDER[user.tier] ?? 0
    const requiredTierLevel = TIER_ORDER[requiredTier] ?? 0

    if (userTierLevel < requiredTierLevel) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-bold">Upgrade Required</h1>
            <p className="text-muted-foreground">
              This feature requires {requiredTier} tier or higher.
            </p>
            <p className="text-sm text-muted-foreground">
              Your current tier: {user.tier}
            </p>
          </div>
        </div>
      )
    }
  }

  return <>{children}</>
}

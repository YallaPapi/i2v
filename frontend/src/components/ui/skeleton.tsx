import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-muted',
        className
      )}
    />
  )
}

// Pipeline card skeleton for Jobs page
export function PipelineCardSkeleton() {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {/* Favorite star */}
          <Skeleton className="h-5 w-5 rounded" />
          <div className="space-y-2">
            {/* Name and badges */}
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-20" />
            </div>
            {/* Date and stats */}
            <Skeleton className="h-3 w-64" />
            {/* Prompt preview */}
            <Skeleton className="h-3 w-80" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Hide button */}
          <Skeleton className="h-6 w-6 rounded" />
          {/* Status badge */}
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
      </div>

      {/* Tags row */}
      <div className="flex flex-wrap items-center gap-1">
        <Skeleton className="h-5 w-12 rounded" />
        <Skeleton className="h-5 w-14 rounded" />
      </div>

      {/* Outputs toggle */}
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-4" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-6 rounded" />
      </div>
    </div>
  )
}

// Grid of output thumbnail skeletons
export function OutputGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
      {Array.from({ length: count }).map((_, idx) => (
        <Skeleton key={idx} className="aspect-[9/16] rounded-lg" />
      ))}
    </div>
  )
}

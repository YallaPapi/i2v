import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import { DollarSign, ChevronDown, ChevronUp, Info } from 'lucide-react'
import { useState } from 'react'

interface StepCost {
  stepType: string
  stepOrder: number
  model?: string
  unitCount: number
  unitPrice: number
  total: number
}

interface CostEstimate {
  breakdown: StepCost[]
  total: number
  currency: string
}

interface CostPreviewProps {
  estimate: CostEstimate | null
  isLoading?: boolean
  compact?: boolean
  className?: string
}

const STEP_LABELS: Record<string, string> = {
  prompt_enhance: 'Prompt Enhancement',
  i2i: 'Image Generation',
  i2v: 'Video Generation',
}

export function CostPreview({
  estimate,
  isLoading = false,
  compact = false,
  className,
}: CostPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(!compact)

  const formattedTotal = useMemo(() => {
    if (!estimate) return '$0.00'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: estimate.currency || 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(estimate.total)
  }, [estimate])

  if (!estimate && !isLoading) {
    return null
  }

  if (compact) {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <DollarSign className="h-4 w-4 text-muted-foreground" />
        {isLoading ? (
          <span className="text-sm text-muted-foreground animate-pulse">Calculating...</span>
        ) : (
          <span className="text-sm font-medium">{formattedTotal}</span>
        )}
      </div>
    )
  }

  return (
    <div className={cn("border rounded-lg overflow-hidden", className)}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-muted/30 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-full">
            <DollarSign className="h-5 w-5 text-primary" />
          </div>
          <div className="text-left">
            <div className="font-medium">Cost Estimate</div>
            {isLoading ? (
              <div className="text-sm text-muted-foreground animate-pulse">Calculating...</div>
            ) : (
              <div className="text-2xl font-bold text-primary">{formattedTotal}</div>
            )}
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-5 w-5 text-muted-foreground" />
        )}
      </button>

      {/* Breakdown */}
      {isExpanded && estimate && (
        <div className="p-4 space-y-3">
          {estimate.breakdown.map((step, index) => (
            <div key={index} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="w-4 text-muted-foreground">{index === estimate.breakdown.length - 1 ? '└' : '├'}</span>
                <span>{STEP_LABELS[step.stepType] || step.stepType}</span>
                {step.model && (
                  <span className="text-xs text-muted-foreground">({step.model})</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">
                  {step.unitCount} × ${step.unitPrice.toFixed(3)}
                </span>
                <span className="font-medium w-16 text-right">
                  ${step.total.toFixed(2)}
                </span>
              </div>
            </div>
          ))}

          {/* Total line */}
          <div className="pt-3 border-t flex items-center justify-between">
            <span className="font-medium">Total</span>
            <span className="text-xl font-bold text-primary">{formattedTotal}</span>
          </div>

          {/* Info */}
          <div className="flex items-start gap-2 pt-2 text-xs text-muted-foreground">
            <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
            <span>
              Estimate based on selected models and quantities. Actual cost may vary.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

// Helper hook for fetching cost estimates
export function useCostEstimate(steps: Array<{ step_type: string; config: object }>) {
  const [estimate, setEstimate] = useState<CostEstimate | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchEstimate = async () => {
    if (steps.length === 0) {
      setEstimate(null)
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch('/api/pipelines/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          steps: steps.map((s, i) => ({
            step_type: s.step_type,
            step_order: i,
            config: s.config,
          })),
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setEstimate({
          breakdown: data.breakdown.map((b: { step_type: string; step_order: number; model?: string; unit_count: number; unit_price: number; total: number }) => ({
            stepType: b.step_type,
            stepOrder: b.step_order,
            model: b.model,
            unitCount: b.unit_count,
            unitPrice: b.unit_price,
            total: b.total,
          })),
          total: data.total,
          currency: data.currency,
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  return { estimate, isLoading, fetchEstimate }
}

export type { CostEstimate, StepCost }

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { AlertTriangle, DollarSign, Image, Video, X } from 'lucide-react'

interface ConfirmGenerationModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  costEstimate: {
    breakdown?: {
      grand_total?: number
      i2i_count?: number
      i2v_count?: number
      i2i_total?: number
      i2v_total?: number
    }
  } | null
  sourceImageCount: number
  bulkMode: 'photos' | 'videos' | 'both'
}

const THRESHOLD_KEY = 'confirmGenerationThreshold'
const DEFAULT_THRESHOLD = 1 // $1

export function ConfirmGenerationModal({
  isOpen,
  onClose,
  onConfirm,
  costEstimate,
  sourceImageCount,
  bulkMode,
}: ConfirmGenerationModalProps) {
  const [dontAskAgain, setDontAskAgain] = useState(false)
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD)

  useEffect(() => {
    const saved = localStorage.getItem(THRESHOLD_KEY)
    if (saved) {
      setThreshold(parseFloat(saved))
    }
  }, [])

  if (!isOpen) return null

  const totalCost = costEstimate?.breakdown?.grand_total || 0
  const photoCount = costEstimate?.breakdown?.i2i_count || 0
  const videoCount = costEstimate?.breakdown?.i2v_count || 0
  const photoCost = costEstimate?.breakdown?.i2i_total || 0
  const videoCost = costEstimate?.breakdown?.i2v_total || 0

  const handleConfirm = () => {
    if (dontAskAgain) {
      // Set threshold higher than current cost so this won't show again for similar jobs
      localStorage.setItem(THRESHOLD_KEY, Math.ceil(totalCost + 1).toString())
    }
    onConfirm()
  }

  const isExpensive = totalCost > 10

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-background border rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          {isExpensive ? (
            <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-full">
              <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400" />
            </div>
          ) : (
            <div className="p-2 bg-primary/10 rounded-full">
              <DollarSign className="h-6 w-6 text-primary" />
            </div>
          )}
          <div>
            <h2 className="text-lg font-semibold">Confirm Generation</h2>
            <p className="text-sm text-muted-foreground">
              Review before starting
            </p>
          </div>
        </div>

        {/* Cost breakdown */}
        <div className="space-y-3 mb-6">
          {/* Total */}
          <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
            <span className="font-medium">Estimated Total</span>
            <span className={`text-xl font-bold ${isExpensive ? 'text-amber-600' : 'text-primary'}`}>
              ${totalCost.toFixed(2)}
            </span>
          </div>

          {/* Breakdown */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between text-muted-foreground">
              <span>Source images</span>
              <span>{sourceImageCount}</span>
            </div>

            {(bulkMode === 'photos' || bulkMode === 'both') && photoCount > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Image className="h-4 w-4" />
                  Photos to generate
                </span>
                <span>{photoCount} (${photoCost.toFixed(2)})</span>
              </div>
            )}

            {(bulkMode === 'videos' || bulkMode === 'both') && videoCount > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Video className="h-4 w-4" />
                  Videos to generate
                </span>
                <span>{videoCount} (${videoCost.toFixed(2)})</span>
              </div>
            )}
          </div>
        </div>

        {/* Don't ask again checkbox */}
        <label className="flex items-center gap-2 text-sm text-muted-foreground mb-4 cursor-pointer">
          <input
            type="checkbox"
            checked={dontAskAgain}
            onChange={(e) => setDontAskAgain(e.target.checked)}
            className="rounded border-muted-foreground"
          />
          Don't ask again for jobs under ${Math.ceil(totalCost + 1)}
        </label>

        {/* Actions */}
        <div className="flex gap-3">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="flex-1"
            onClick={handleConfirm}
          >
            Start Generation
          </Button>
        </div>
      </div>
    </div>
  )
}

// Helper to check if confirmation should be shown
export function shouldShowConfirmation(costEstimate: { breakdown?: { grand_total?: number } } | null): boolean {
  const cost = costEstimate?.breakdown?.grand_total || 0
  const threshold = parseFloat(localStorage.getItem(THRESHOLD_KEY) || String(DEFAULT_THRESHOLD))
  return cost > threshold
}

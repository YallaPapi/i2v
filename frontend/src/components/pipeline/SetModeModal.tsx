import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { X, Layers, Sparkles } from 'lucide-react'

interface SetModeConfig {
  enabled: boolean
  variations: string[]
  countPerVariation: number
  customOutfits?: string
}

interface SetModeModalProps {
  isOpen: boolean
  onClose: () => void
  config: SetModeConfig
  onConfigChange: (config: SetModeConfig) => void
}

const VARIATION_OPTIONS = [
  {
    id: 'angles',
    label: 'Angles',
    description: 'Front, Side, 3/4, Back views',
    items: ['Front view', 'Side view', '3/4 angle', 'Back view'],
  },
  {
    id: 'expressions',
    label: 'Expressions',
    description: 'Different facial expressions',
    items: ['Smiling', 'Serious', 'Laughing', 'Contemplative'],
  },
  {
    id: 'poses',
    label: 'Poses',
    description: 'Body positions and stances',
    items: ['Standing', 'Sitting', 'Walking', 'Action pose'],
  },
  {
    id: 'lighting',
    label: 'Lighting',
    description: 'Different lighting conditions',
    items: ['Studio lighting', 'Natural light', 'Dramatic shadows', 'Soft glow'],
  },
]

export function SetModeModal({
  isOpen,
  onClose,
  config,
  onConfigChange,
}: SetModeModalProps) {
  const [localConfig, setLocalConfig] = useState<SetModeConfig>(config)

  useEffect(() => {
    setLocalConfig(config)
  }, [config])

  if (!isOpen) return null

  const toggleVariation = (variationId: string) => {
    const newVariations = localConfig.variations.includes(variationId)
      ? localConfig.variations.filter(v => v !== variationId)
      : [...localConfig.variations, variationId]

    setLocalConfig({
      ...localConfig,
      variations: newVariations,
      enabled: newVariations.length > 0,
    })
  }

  const calculateTotal = () => {
    if (!localConfig.enabled || localConfig.variations.length === 0) {
      return 1
    }

    let total = 0
    localConfig.variations.forEach(varId => {
      const option = VARIATION_OPTIONS.find(o => o.id === varId)
      if (option) {
        total += Math.min(option.items.length, localConfig.countPerVariation)
      }
    })

    // Add custom outfits count
    if (localConfig.customOutfits) {
      const outfitCount = localConfig.customOutfits.split(',').filter(s => s.trim()).length
      total += outfitCount
    }

    return total || 1
  }

  const handleApply = () => {
    onConfigChange(localConfig)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-background rounded-lg shadow-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">Create Photo Set</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-muted rounded-md transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6">
          <p className="text-sm text-muted-foreground">
            Generate multiple variations of your image with different angles, expressions, poses, and more.
          </p>

          {/* Variation Types */}
          <div className="space-y-3">
            <Label>Select Variations</Label>
            <div className="grid grid-cols-2 gap-3">
              {VARIATION_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => toggleVariation(option.id)}
                  className={cn(
                    "p-3 rounded-lg border text-left transition-all",
                    localConfig.variations.includes(option.id)
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  <div className="font-medium text-sm">{option.label}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {option.description}
                  </div>
                  {localConfig.variations.includes(option.id) && (
                    <div className="text-xs text-primary mt-2">
                      {Math.min(option.items.length, localConfig.countPerVariation)} variations
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Outfits */}
          <div className="space-y-2">
            <Label>Custom Outfits (optional)</Label>
            <Input
              placeholder="casual, formal, sporty, elegant..."
              value={localConfig.customOutfits || ''}
              onChange={(e) => setLocalConfig({
                ...localConfig,
                customOutfits: e.target.value,
                enabled: localConfig.variations.length > 0 || !!e.target.value,
              })}
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated outfit descriptions
            </p>
          </div>

          {/* Count Per Variation */}
          <div className="space-y-2">
            <Label>Images per variation type</Label>
            <div className="flex items-center gap-4">
              {[1, 2, 3, 4].map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => setLocalConfig({
                    ...localConfig,
                    countPerVariation: count,
                  })}
                  className={cn(
                    "w-10 h-10 rounded-md border font-medium transition-all",
                    localConfig.countPerVariation === count
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  {count}
                </button>
              ))}
            </div>
          </div>

          {/* Preview */}
          <div className="p-4 bg-muted/50 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                <span className="font-medium">Total Images</span>
              </div>
              <span className="text-2xl font-bold text-primary">
                {calculateTotal()}
              </span>
            </div>
            {localConfig.variations.length > 0 && (
              <p className="text-xs text-muted-foreground mt-2">
                {localConfig.variations.map(v =>
                  VARIATION_OPTIONS.find(o => o.id === v)?.label
                ).join(' + ')}
                {localConfig.customOutfits && ' + Custom Outfits'}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={handleApply}>
            Apply Set Mode
          </Button>
        </div>
      </div>
    </div>
  )
}

export type { SetModeConfig }

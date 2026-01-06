import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Sparkles } from 'lucide-react'

type ModelType = 'i2i' | 'i2v'

interface ModelOption {
  value: string
  label: string
  price: string
  priceValue: number
  provider: string
  description?: string
  recommended?: boolean
}

interface ModelSelectorProps {
  type: ModelType
  value: string
  onChange: (value: string) => void
  showPricing?: boolean
  disabled?: boolean
  className?: string
}

// Pricing from image_client.py - exact values from Fal API
const I2I_MODELS: ModelOption[] = [
  {
    value: 'gpt-image-1.5',
    label: 'GPT Image 1.5',
    price: 'Quality-based pricing',
    priceValue: 0.07,  // medium quality estimate
    provider: 'OpenAI',
    description: 'High-fidelity editing - select quality for specific pricing',
    recommended: true,
  },
  {
    value: 'kling-image',
    label: 'Kling Image O1',
    price: '$0.028/img',
    priceValue: 0.028,
    provider: 'Kling',
    description: 'Multi-reference control with Elements for character consistency',
  },
  {
    value: 'nano-banana',
    label: 'Nano Banana',
    price: '$0.039/img',
    priceValue: 0.039,
    provider: 'Google',
    description: 'Budget Google model for general editing',
  },
  {
    value: 'nano-banana-pro',
    label: 'Nano Banana Pro',
    price: '$0.15/img',  // 2x for 4K
    priceValue: 0.15,
    provider: 'Google',
    description: "Google's best model - realistic, good typography",
  },
]

// Pricing from fal.ai - January 2026 verified rates (per-second)
const I2V_MODELS: ModelOption[] = [
  // Kling models
  {
    value: 'kling',
    label: 'Kling v2.5 Turbo Pro',
    price: '$0.07/s',
    priceValue: 0.07,
    provider: 'Kling',
    description: 'Fast turbo generation',
    recommended: true,
  },
  {
    value: 'kling-standard',
    label: 'Kling v2.1 Standard',
    price: '$0.05/s',
    priceValue: 0.05,
    provider: 'Kling',
    description: 'Budget option',
  },
  {
    value: 'kling-master',
    label: 'Kling v2.1 Master',
    price: '$0.28/s',
    priceValue: 0.28,
    provider: 'Kling',
    description: 'Highest quality',
  },
  // Wan models
  {
    value: 'wan',
    label: 'Wan 2.5 Preview',
    price: '$0.05-0.15/s',
    priceValue: 0.10,
    provider: 'Wan',
    description: '480p=$0.05/s, 720p=$0.10/s, 1080p=$0.15/s',
  },
  {
    value: 'wan21',
    label: 'Wan 2.1 I2V',
    price: '$0.20-0.40/vid',
    priceValue: 0.30,
    provider: 'Wan',
    description: 'Flat rate: 480p=$0.20, 720p=$0.40',
  },
  {
    value: 'wan22',
    label: 'Wan 2.2',
    price: '$0.04-0.08/s',
    priceValue: 0.06,
    provider: 'Wan',
    description: '480p=$0.04/s, 720p=$0.08/s',
  },
  {
    value: 'wan-pro',
    label: 'Wan Pro',
    price: '$0.16/s',
    priceValue: 0.16,
    provider: 'Wan',
    description: 'Premium 1080p only',
  },
  // Google Veo models
  {
    value: 'veo2',
    label: 'Veo 2',
    price: '$0.50/s',
    priceValue: 0.50,
    provider: 'Google',
    description: '720p only',
  },
  {
    value: 'veo31-fast',
    label: 'Veo 3.1 Fast',
    price: '$0.10/s',
    priceValue: 0.10,
    provider: 'Google',
    description: 'Fast, 4/6/8s durations',
  },
  {
    value: 'veo31',
    label: 'Veo 3.1',
    price: '$0.20/s',
    priceValue: 0.20,
    provider: 'Google',
    description: 'High quality, 4/6/8s',
  },
  {
    value: 'veo31-flf',
    label: 'Veo 3.1 First-Last Frame',
    price: '$0.20/s',
    priceValue: 0.20,
    provider: 'Google',
    description: 'Control start and end frames',
  },
  {
    value: 'veo31-fast-flf',
    label: 'Veo 3.1 Fast First-Last',
    price: '$0.10/s',
    priceValue: 0.10,
    provider: 'Google',
    description: 'Fast first-last frame control',
  },
  // OpenAI Sora models
  {
    value: 'sora-2',
    label: 'Sora 2',
    price: '$0.10/s',
    priceValue: 0.10,
    provider: 'OpenAI',
    description: '720p, 4/8/12s durations',
  },
  {
    value: 'sora-2-pro',
    label: 'Sora 2 Pro',
    price: '$0.30-0.50/s',
    priceValue: 0.50,
    provider: 'OpenAI',
    description: '720p=$0.30/s, 1080p=$0.50/s',
  },
]

export function ModelSelector({
  type,
  value,
  onChange,
  showPricing = true,
  disabled = false,
  className,
}: ModelSelectorProps) {
  const models = type === 'i2i' ? I2I_MODELS : I2V_MODELS
  const selectedModel = models.find(m => m.value === value)

  // Group models by provider
  const groupedModels = models.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = []
    }
    acc[model.provider].push(model)
    return acc
  }, {} as Record<string, ModelOption[]>)

  return (
    <div className={cn("space-y-2", className)}>
      <Label>Model</Label>

      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className={cn(
            "w-full h-10 px-3 py-2 text-sm rounded-md border border-input bg-background",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
            disabled && "opacity-50 cursor-not-allowed"
          )}
        >
          {Object.entries(groupedModels).map(([provider, providerModels]) => (
            <optgroup key={provider} label={provider}>
              {providerModels.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label} {showPricing && `- ${model.price}`}
                  {model.recommended && ' (Recommended)'}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* Selected Model Info */}
      {selectedModel && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">{selectedModel.description}</span>
          {selectedModel.recommended && (
            <Badge variant="secondary" className="text-xs gap-1">
              <Sparkles className="h-3 w-3" />
              Best Value
            </Badge>
          )}
        </div>
      )}

      {/* Pricing display */}
      {showPricing && selectedModel && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Price:</span>
          <span className="text-sm font-medium text-primary">{selectedModel.price}</span>
          <span className="text-xs text-muted-foreground">per {type === 'i2i' ? 'image' : 'video'}</span>
        </div>
      )}
    </div>
  )
}

// Export model data for use in other components
export { I2I_MODELS, I2V_MODELS }
export type { ModelOption }

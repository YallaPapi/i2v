import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Sparkles, Loader2, ChevronDown, ChevronUp, Copy, Check, Settings2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

export type EnhanceMode = 'quick_improve' | 'category_based' | 'raw'

export const I2V_CATEGORIES = [
  { id: 'camera_movement', label: 'Camera Movement', desc: 'Add pan, zoom, tracking' },
  { id: 'motion_intensity', label: 'Motion Intensity', desc: 'Speed and energy' },
  { id: 'facial_expression', label: 'Facial Expression', desc: 'Expression details' },
  { id: 'body_language', label: 'Body Language', desc: 'Gestures and posture' },
]

export const I2I_CATEGORIES = [
  { id: 'lighting', label: 'Lighting', desc: 'Natural, studio, dramatic' },
  { id: 'outfit', label: 'Outfit', desc: 'Clothing variations' },
  { id: 'pose', label: 'Pose', desc: 'Body positioning' },
  { id: 'background', label: 'Background', desc: 'Background treatment' },
  { id: 'style', label: 'Style', desc: 'Visual style' },
]

interface PromptInputProps {
  value: string
  onChange: (value: string) => void
  onEnhance?: (mode: EnhanceMode, categories: string[]) => Promise<string[]>
  enhancedPrompts?: string[]
  onSelectEnhanced?: (prompt: string) => void
  placeholder?: string
  label?: string
  disabled?: boolean
  maxLength?: number
  className?: string
  target?: 'i2i' | 'i2v'
}

export function PromptInput({
  value,
  onChange,
  onEnhance,
  enhancedPrompts = [],
  onSelectEnhanced,
  placeholder = "Describe what you want to create...",
  label = "Prompt",
  disabled = false,
  maxLength = 2000,
  className,
  target = 'i2v',
}: PromptInputProps) {
  const [isEnhancing, setIsEnhancing] = useState(false)
  const [showEnhanced, setShowEnhanced] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [showOptions, setShowOptions] = useState(false)
  const [enhanceMode, setEnhanceMode] = useState<EnhanceMode>('quick_improve')
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])

  const categories = target === 'i2v' ? I2V_CATEGORIES : I2I_CATEGORIES

  const toggleCategory = (id: string) => {
    setSelectedCategories(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    )
  }

  const handleEnhance = async () => {
    if (!onEnhance || !value.trim() || isEnhancing) return

    setIsEnhancing(true)
    try {
      await onEnhance(enhanceMode, selectedCategories)
      setShowEnhanced(true)
    } finally {
      setIsEnhancing(false)
    }
  }

  const copyToClipboard = async (text: string, index: number) => {
    await navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  const selectPrompt = (prompt: string) => {
    if (onSelectEnhanced) {
      onSelectEnhanced(prompt)
    } else {
      onChange(prompt)
    }
    setShowEnhanced(false)
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <span className="text-xs text-muted-foreground">
          {value.length}/{maxLength}
        </span>
      </div>

      <div className="relative">
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, maxLength))}
          placeholder={placeholder}
          disabled={disabled || isEnhancing}
          rows={4}
          className="resize-none pr-24"
        />

        {onEnhance && (
          <div className="absolute bottom-2 right-2 flex gap-1">
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              onClick={() => setShowOptions(!showOptions)}
              title="Enhancement options"
            >
              <Settings2 className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant={value.trim() ? "default" : "secondary"}
              onClick={handleEnhance}
              disabled={!value.trim() || isEnhancing || disabled}
            >
              {isEnhancing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Enhancing...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-1" />
                  {enhanceMode === 'raw' ? 'Use As-Is' : 'Enhance'}
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Enhancement Options */}
      {showOptions && onEnhance && (
        <div className="border rounded-lg p-3 bg-muted/30 space-y-3">
          <div className="flex items-center gap-2">
            <Label className="text-xs font-medium">Mode:</Label>
            <div className="flex gap-1">
              {[
                { id: 'quick_improve', label: 'Quick Improve' },
                { id: 'category_based', label: 'Categories' },
                { id: 'raw', label: 'Raw (No Change)' },
              ].map(mode => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setEnhanceMode(mode.id as EnhanceMode)}
                  className={cn(
                    'px-2 py-1 text-xs rounded border transition-colors',
                    enhanceMode === mode.id
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background border-border hover:bg-muted'
                  )}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>

          {enhanceMode === 'category_based' && (
            <div className="space-y-2">
              <Label className="text-xs font-medium">
                Focus on ({target === 'i2v' ? 'Video' : 'Image'}):
              </Label>
              <div className="flex flex-wrap gap-1">
                {categories.map(cat => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={cn(
                      'px-2 py-1 text-xs rounded border transition-colors',
                      selectedCategories.includes(cat.id)
                        ? 'bg-primary/20 text-primary border-primary/50'
                        : 'bg-background border-border hover:bg-muted'
                    )}
                    title={cat.desc}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
              {selectedCategories.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Select categories to focus the enhancement
                </p>
              )}
            </div>
          )}

          {enhanceMode === 'quick_improve' && (
            <p className="text-xs text-muted-foreground">
              Makes your prompt more descriptive without adding unwanted context
            </p>
          )}

          {enhanceMode === 'raw' && (
            <p className="text-xs text-muted-foreground">
              Use your prompt exactly as written, no AI enhancement
            </p>
          )}
        </div>
      )}

      {/* Enhanced Prompts */}
      {enhancedPrompts.length > 0 && (
        <div className="border rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setShowEnhanced(!showEnhanced)}
            className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">
                {enhancedPrompts.length} Enhanced Variation{enhancedPrompts.length !== 1 ? 's' : ''}
              </span>
            </div>
            {showEnhanced ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {showEnhanced && (
            <div className="divide-y">
              {enhancedPrompts.map((prompt, index) => (
                <div
                  key={index}
                  className="p-3 hover:bg-muted/30 transition-colors group"
                >
                  <div className="flex items-start gap-2">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-xs flex items-center justify-center font-medium">
                      {index + 1}
                    </span>
                    <p className="flex-1 text-sm">{prompt}</p>
                    <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => copyToClipboard(prompt, index)}
                      >
                        {copiedIndex === index ? (
                          <Check className="h-3 w-3 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-7 text-xs"
                        onClick={() => selectPrompt(prompt)}
                      >
                        Use
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Multi-prompt hint */}
      <p className="text-xs text-muted-foreground">
        Tip: Separate multiple prompts with --- to process them in bulk
      </p>
    </div>
  )
}

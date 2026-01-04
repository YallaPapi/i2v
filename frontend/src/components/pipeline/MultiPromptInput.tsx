import { useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Wand2, Trash2 } from 'lucide-react'

interface MultiPromptInputProps {
  prompts: string[]
  onPromptsChange: (prompts: string[]) => void
  label?: string
  placeholder?: string
  maxPrompts?: number
  disabled?: boolean
  onEnhanceAll?: () => Promise<void>
  isEnhancing?: boolean
}

export function MultiPromptInput({
  prompts,
  onPromptsChange,
  label = 'Prompts',
  placeholder = 'Enter prompts, one per line...',
  maxPrompts,
  disabled = false,
  onEnhanceAll,
  isEnhancing = false,
}: MultiPromptInputProps) {
  const [text, setText] = useState(prompts.join('\n'))

  const handleTextChange = (value: string) => {
    setText(value)
    let lines = value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
    if (maxPrompts) {
      lines = lines.slice(0, maxPrompts)
    }
    onPromptsChange(lines)
  }

  const clearAll = () => {
    setText('')
    onPromptsChange([])
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        <div className="flex items-center gap-2">
          {prompts.length > 0 && (
            <Badge variant="secondary">
              {prompts.length} prompt{prompts.length !== 1 ? 's' : ''}
            </Badge>
          )}
          {onEnhanceAll && prompts.length > 0 && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onEnhanceAll}
              disabled={disabled || isEnhancing}
            >
              <Wand2 className="h-4 w-4 mr-1" />
              {isEnhancing ? 'Enhancing...' : 'Enhance All'}
            </Button>
          )}
          {prompts.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={clearAll}
              disabled={disabled}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <Textarea
        value={text}
        onChange={(e) => handleTextChange(e.target.value)}
        placeholder={placeholder}
        rows={5}
        disabled={disabled}
        className="font-mono text-sm"
      />

      <p className="text-xs text-muted-foreground">
        One prompt per line.{maxPrompts ? ` Maximum ${maxPrompts} prompts.` : ''}
      </p>
    </div>
  )
}

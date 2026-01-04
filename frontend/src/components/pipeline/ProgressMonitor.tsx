import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Loader2,
  CheckCircle,
  XCircle,
  Pause,
  Play,
  X,
  Clock,
  Sparkles,
  Image,
  Video,
} from 'lucide-react'

interface PipelineStep {
  id: number
  stepType: string
  stepOrder: number
  status: 'pending' | 'running' | 'review' | 'completed' | 'failed'
  progressPct?: number
  outputsCount?: number
  errorMessage?: string
}

interface ProgressMonitorProps {
  pipelineId: number
  steps: PipelineStep[]
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  onPause?: () => void
  onResume?: () => void
  onCancel?: () => void
  onApproveStep?: (stepId: number) => void
  className?: string
}

const STEP_ICONS: Record<string, React.ReactNode> = {
  prompt_enhance: <Sparkles className="h-4 w-4" />,
  i2i: <Image className="h-4 w-4" />,
  i2v: <Video className="h-4 w-4" />,
}

const STEP_LABELS: Record<string, string> = {
  prompt_enhance: 'Enhancing Prompts',
  i2i: 'Generating Images',
  i2v: 'Generating Videos',
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock className="h-4 w-4 text-muted-foreground" />,
  running: <Loader2 className="h-4 w-4 text-primary animate-spin" />,
  review: <Pause className="h-4 w-4 text-yellow-500" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-destructive" />,
}

export function ProgressMonitor({
  pipelineId: _pipelineId,
  steps,
  status,
  onPause,
  onResume,
  onCancel,
  onApproveStep,
  className,
}: ProgressMonitorProps) {
  // pipelineId available for future WebSocket subscription
  void _pipelineId
  const [elapsedTime, setElapsedTime] = useState(0)

  // Timer for elapsed time
  useEffect(() => {
    if (status !== 'running') return

    const interval = setInterval(() => {
      setElapsedTime(t => t + 1)
    }, 1000)

    return () => clearInterval(interval)
  }, [status])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const overallProgress = () => {
    if (steps.length === 0) return 0
    const completed = steps.filter(s => s.status === 'completed').length
    const running = steps.find(s => s.status === 'running')
    const runningProgress = running?.progressPct || 0

    return Math.round(((completed + runningProgress / 100) / steps.length) * 100)
  }

  const currentStep = steps.find(s => s.status === 'running' || s.status === 'review')

  return (
    <div className={cn("border rounded-lg overflow-hidden", className)}>
      {/* Header with overall progress */}
      <div className="p-4 bg-muted/30">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            {status === 'running' && (
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
            )}
            {status === 'paused' && (
              <Pause className="h-5 w-5 text-yellow-500" />
            )}
            {status === 'completed' && (
              <CheckCircle className="h-5 w-5 text-green-500" />
            )}
            {status === 'failed' && (
              <XCircle className="h-5 w-5 text-destructive" />
            )}
            <div>
              <div className="font-medium">
                {status === 'running' && 'Pipeline Running'}
                {status === 'paused' && 'Pipeline Paused'}
                {status === 'completed' && 'Pipeline Completed'}
                {status === 'failed' && 'Pipeline Failed'}
                {status === 'pending' && 'Pipeline Pending'}
              </div>
              {currentStep && (
                <div className="text-sm text-muted-foreground">
                  {STEP_LABELS[currentStep.stepType] || currentStep.stepType}
                </div>
              )}
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            {formatTime(elapsedTime)}
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full transition-all duration-500",
              status === 'completed' ? "bg-green-500" :
              status === 'failed' ? "bg-destructive" :
              "bg-primary"
            )}
            style={{ width: `${overallProgress()}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-muted-foreground text-right">
          {overallProgress()}% complete
        </div>
      </div>

      {/* Steps timeline */}
      <div className="p-4 space-y-3">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center gap-3">
            {/* Step indicator */}
            <div className={cn(
              "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
              step.status === 'completed' && "bg-green-500/10",
              step.status === 'running' && "bg-primary/10",
              step.status === 'review' && "bg-yellow-500/10",
              step.status === 'failed' && "bg-destructive/10",
              step.status === 'pending' && "bg-muted",
            )}>
              {STATUS_ICONS[step.status]}
            </div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {STEP_ICONS[step.stepType]}
                <span className={cn(
                  "font-medium text-sm",
                  step.status === 'pending' && "text-muted-foreground"
                )}>
                  {STEP_LABELS[step.stepType] || step.stepType}
                </span>
              </div>

              {/* Progress bar for running step */}
              {step.status === 'running' && step.progressPct !== undefined && (
                <div className="mt-1.5 h-1 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${step.progressPct}%` }}
                  />
                </div>
              )}

              {/* Outputs count */}
              {step.status === 'completed' && step.outputsCount !== undefined && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  {step.outputsCount} outputs generated
                </div>
              )}

              {/* Error message */}
              {step.status === 'failed' && step.errorMessage && (
                <div className="text-xs text-destructive mt-0.5">
                  {step.errorMessage}
                </div>
              )}

              {/* Review action */}
              {step.status === 'review' && onApproveStep && (
                <Button
                  size="sm"
                  className="mt-2"
                  onClick={() => onApproveStep(step.id)}
                >
                  Approve & Continue
                </Button>
              )}
            </div>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <div className="absolute left-[1.75rem] top-10 w-0.5 h-6 bg-border -ml-px" />
            )}
          </div>
        ))}
      </div>

      {/* Actions */}
      {(status === 'running' || status === 'paused') && (
        <div className="flex items-center justify-end gap-2 p-4 border-t">
          {status === 'running' && onPause && (
            <Button variant="outline" size="sm" onClick={onPause}>
              <Pause className="h-4 w-4 mr-1" />
              Pause
            </Button>
          )}
          {status === 'paused' && onResume && (
            <Button variant="outline" size="sm" onClick={onResume}>
              <Play className="h-4 w-4 mr-1" />
              Resume
            </Button>
          )}
          {onCancel && (
            <Button variant="destructive" size="sm" onClick={onCancel}>
              <X className="h-4 w-4 mr-1" />
              Cancel
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

export type { PipelineStep }

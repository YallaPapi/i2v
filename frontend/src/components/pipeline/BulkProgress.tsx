import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CheckCircle2, XCircle, Loader2, Clock, Image, Video, StopCircle } from 'lucide-react'

interface BulkStep {
  id: number
  step_type: 'i2i' | 'i2v'
  status: 'pending' | 'running' | 'completed' | 'failed'
  source_index?: number
  outputs?: string[]
}

interface BulkProgressProps {
  pipelineId: number
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  steps: BulkStep[]
  onCancel?: () => Promise<void>
}

export function BulkProgress({
  pipelineId,
  status,
  steps,
  onCancel,
}: BulkProgressProps) {
  const [isCancelling, setIsCancelling] = useState(false)

  const handleCancel = async () => {
    if (!onCancel || isCancelling) return
    setIsCancelling(true)
    try {
      await onCancel()
    } finally {
      setIsCancelling(false)
    }
  }
  const completedSteps = steps.filter(s => s.status === 'completed').length
  const failedSteps = steps.filter(s => s.status === 'failed').length
  const runningSteps = steps.filter(s => s.status === 'running').length
  const totalSteps = steps.length

  const progressPct = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  const i2iSteps = steps.filter(s => s.step_type === 'i2i')
  const i2vSteps = steps.filter(s => s.step_type === 'i2v')

  const i2iCompleted = i2iSteps.filter(s => s.status === 'completed').length
  const i2vCompleted = i2vSteps.filter(s => s.status === 'completed').length

  const getStatusIcon = (stepStatus: BulkStep['status']) => {
    switch (stepStatus) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'running':
        return <Loader2 className="h-4 w-4 text-primary animate-spin" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'running':
        return 'bg-primary'
      default:
        return 'bg-muted'
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            Pipeline #{pipelineId}
            {status === 'running' && <Loader2 className="h-4 w-4 animate-spin" />}
          </CardTitle>
          <div className="flex items-center gap-2">
            {(status === 'running' || status === 'pending') && onCancel && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleCancel}
                disabled={isCancelling}
                className="h-7 px-2"
              >
                {isCancelling ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : (
                  <StopCircle className="h-3 w-3 mr-1" />
                )}
                {isCancelling ? 'Cancelling...' : 'Cancel'}
              </Button>
            )}
            <Badge variant={status === 'completed' ? 'default' : status === 'failed' || status === 'cancelled' ? 'destructive' : 'secondary'}>
              {status}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {totalSteps > 0 ? `${completedSteps} / ${totalSteps} steps` : 'Processing...'}
            </span>
            {totalSteps > 0 && <span>{Math.round(progressPct)}%</span>}
          </div>
          <Progress value={totalSteps > 0 ? progressPct : 0} className={getStatusColor()} />
        </div>

        {/* Step Type Breakdown */}
        <div className="grid grid-cols-2 gap-4">
          {/* I2I Progress */}
          {i2iSteps.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <Image className="h-4 w-4" />
                <span>Images</span>
              </div>
              <Progress
                value={(i2iCompleted / i2iSteps.length) * 100}
                className="h-2"
              />
              <p className="text-xs text-muted-foreground">
                {i2iCompleted} / {i2iSteps.length}
              </p>
            </div>
          )}

          {/* I2V Progress */}
          {i2vSteps.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <Video className="h-4 w-4" />
                <span>Videos</span>
              </div>
              <Progress
                value={(i2vCompleted / i2vSteps.length) * 100}
                className="h-2"
              />
              <p className="text-xs text-muted-foreground">
                {i2vCompleted} / {i2vSteps.length}
              </p>
            </div>
          )}
        </div>

        {/* Running Steps */}
        {runningSteps > 0 && (
          <div className="text-sm text-muted-foreground">
            {runningSteps} step{runningSteps !== 1 ? 's' : ''} in progress...
          </div>
        )}

        {/* Failed Steps */}
        {failedSteps > 0 && (
          <div className="text-sm text-red-400">
            {failedSteps} step{failedSteps !== 1 ? 's' : ''} failed
          </div>
        )}

        {/* Individual Steps (collapsible in future) */}
        <div className="max-h-40 overflow-y-auto space-y-1 pt-2 border-t">
          {steps.length === 0 ? (
            <div className="flex items-center gap-2 text-xs py-1 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Preparing jobs...
            </div>
          ) : (
            steps.map((step) => (
              <div
                key={step.id}
                className="flex items-center gap-2 text-xs py-1"
              >
                {getStatusIcon(step.status)}
                <span className="text-muted-foreground">
                  {step.step_type.toUpperCase()} #{step.id}
                  {step.source_index !== undefined && ` (Source ${step.source_index + 1})`}
                </span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export type { BulkStep }

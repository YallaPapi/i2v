import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ArrowRight, Image, Video, Loader2 } from 'lucide-react'

interface BulkCostEstimate {
  breakdown: {
    i2i_count: number
    i2i_cost_per_image: number
    i2i_total: number
    i2v_count: number
    i2v_cost_per_video: number
    i2v_total: number
    grand_total: number
  }
  combinations: {
    sources: number
    i2i_prompts: number
    i2v_prompts: number
    total_images: number
    total_videos: number
  }
}

type BulkModeType = 'photos' | 'videos' | 'both'

interface BulkPreviewProps {
  sourceCount: number
  i2iPromptCount: number
  i2vPromptCount: number
  bulkMode: BulkModeType
  costEstimate?: BulkCostEstimate | null
  isLoading?: boolean
}

export function BulkPreview({
  sourceCount,
  i2iPromptCount,
  i2vPromptCount,
  bulkMode,
  costEstimate,
  isLoading = false,
}: BulkPreviewProps) {
  // Calculate outputs based on mode
  const showPhotos = bulkMode === 'photos' || bulkMode === 'both'
  const showVideos = bulkMode === 'videos' || bulkMode === 'both'

  const i2iOutputs = showPhotos && i2iPromptCount > 0 ? sourceCount * i2iPromptCount : 0
  const i2vInputs = bulkMode === 'both' && i2iOutputs > 0 ? i2iOutputs : sourceCount
  const i2vOutputs = showVideos ? i2vInputs * i2vPromptCount : 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          What You'll Get
          {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Visual flow */}
        <div className="space-y-3">
          {/* Photos uploaded */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
              <Image className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-medium">{sourceCount} photo{sourceCount !== 1 ? 's' : ''} uploaded</p>
            </div>
          </div>

          {/* Photo variations */}
          {showPhotos && i2iPromptCount > 0 && (
            <>
              <div className="flex items-center pl-4">
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <Image className="h-4 w-4 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-400">{i2iOutputs} new photo{i2iOutputs !== 1 ? 's' : ''}</p>
                  <p className="text-xs text-muted-foreground">
                    {sourceCount} × {i2iPromptCount} prompt{i2iPromptCount !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            </>
          )}

          {/* Videos */}
          {showVideos && i2vPromptCount > 0 && (
            <>
              <div className="flex items-center pl-4">
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                  <Video className="h-4 w-4 text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-green-400">{i2vOutputs} video{i2vOutputs !== 1 ? 's' : ''}</p>
                  <p className="text-xs text-muted-foreground">
                    {i2vInputs} photo{i2vInputs !== 1 ? 's' : ''} × {i2vPromptCount} motion{i2vPromptCount !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Cost */}
        {costEstimate && costEstimate.breakdown.grand_total > 0 && (
          <div className="pt-3 border-t">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Estimated cost</span>
              <span className="text-lg font-semibold">${costEstimate.breakdown.grand_total.toFixed(2)}</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
              {costEstimate.breakdown.i2i_count > 0 && (
                <p>{costEstimate.breakdown.i2i_count} photos = ${costEstimate.breakdown.i2i_total.toFixed(2)}</p>
              )}
              {costEstimate.breakdown.i2v_count > 0 && (
                <p>{costEstimate.breakdown.i2v_count} videos = ${costEstimate.breakdown.i2v_total.toFixed(2)}</p>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {sourceCount === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            Upload photos to see what we'll create
          </p>
        )}

        {sourceCount > 0 && bulkMode === 'photos' && i2iPromptCount === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            Add at least one photo description to create variations
          </p>
        )}

        {sourceCount > 0 && bulkMode === 'videos' && i2vPromptCount === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            Add at least one motion description to create videos
          </p>
        )}

        {sourceCount > 0 && bulkMode === 'both' && i2vPromptCount === 0 && (
          <p className="text-sm text-muted-foreground text-center py-2">
            Add at least one motion description to create videos
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export type { BulkCostEstimate, BulkModeType }

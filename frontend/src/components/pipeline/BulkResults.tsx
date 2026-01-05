import { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown, Download, Image, Video, ExternalLink, Play, Check, Square, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

// Helper to download a file from URL
async function downloadFile(url: string, filename?: string) {
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename || url.split('/').pop() || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)
  } catch (error) {
    console.error('Download failed:', error)
    // Fallback: open in new tab
    window.open(url, '_blank')
  }
}

interface SourceGroup {
  source_image: string
  source_index: number
  i2i_outputs: string[]  // Full resolution URLs for download/video
  i2i_thumbnails?: (string | null)[]  // Thumbnail URLs for fast grid loading
  i2v_outputs: string[]
}

interface BulkResultsProps {
  groups: SourceGroup[]
  totals: {
    source_images: number
    i2i_generated: number
    i2v_generated: number
    total_cost: number
  }
  onAnimateSelected?: (imageUrls: string[]) => void
}

export function BulkResults({ groups, totals, onAnimateSelected }: BulkResultsProps) {
  const [openGroups, setOpenGroups] = useState<Set<number>>(new Set([0]))
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set())
  const [isSelectionMode, setIsSelectionMode] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const toggleGroup = (index: number) => {
    const newOpen = new Set(openGroups)
    if (newOpen.has(index)) {
      newOpen.delete(index)
    } else {
      newOpen.add(index)
    }
    setOpenGroups(newOpen)
  }

  const toggleImageSelection = useCallback((url: string, e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setSelectedImages(prev => {
      const newSet = new Set(prev)
      if (newSet.has(url)) {
        newSet.delete(url)
      } else {
        newSet.add(url)
      }
      return newSet
    })
  }, [])

  const selectAllImages = useCallback(() => {
    const allImages = groups.flatMap(g => g.i2i_outputs)
    setSelectedImages(new Set(allImages))
  }, [groups])

  const clearSelection = useCallback(() => {
    setSelectedImages(new Set())
  }, [])

  const handleAnimateSelected = useCallback(() => {
    if (onAnimateSelected && selectedImages.size > 0) {
      onAnimateSelected(Array.from(selectedImages))
    }
  }, [onAnimateSelected, selectedImages])

  const downloadAll = async () => {
    const allUrls = groups.flatMap(g => [...g.i2i_outputs, ...g.i2v_outputs])
    if (allUrls.length === 0) return

    setIsDownloading(true)
    try {
      // Download files with a small delay between each to avoid overwhelming the browser
      for (let i = 0; i < allUrls.length; i++) {
        const url = allUrls[i]
        const ext = url.includes('.mp4') || url.includes('video') ? 'mp4' : 'png'
        await downloadFile(url, `output_${i + 1}.${ext}`)
        // Small delay to prevent browser from blocking multiple downloads
        if (i < allUrls.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 500))
        }
      }
    } finally {
      setIsDownloading(false)
    }
  }

  const downloadGroupVideos = async (group: SourceGroup) => {
    for (let i = 0; i < group.i2v_outputs.length; i++) {
      const url = group.i2v_outputs[i]
      await downloadFile(url, `video_${group.source_index + 1}_${i + 1}.mp4`)
      if (i < group.i2v_outputs.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 500))
      }
    }
  }

  if (groups.length === 0) {
    return null
  }

  const hasI2iOutputs = totals.i2i_generated > 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Results</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <Image className="h-3 w-3" />
              {totals.i2i_generated}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <Video className="h-3 w-3" />
              {totals.i2v_generated}
            </Badge>
            {totals.total_cost > 0 && (
              <Badge variant="secondary">
                ${totals.total_cost.toFixed(2)}
              </Badge>
            )}
            <Button size="sm" variant="outline" onClick={downloadAll} disabled={isDownloading}>
              {isDownloading ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-1" />
              )}
              {isDownloading ? 'Downloading...' : 'Download All'}
            </Button>
          </div>
        </div>

        {/* Prominent CTA for video creation */}
        {hasI2iOutputs && onAnimateSelected && !isSelectionMode && totals.i2v_generated === 0 && (
          <div className="pt-3 border-t mt-3">
            <Button
              size="lg"
              className="w-full gap-2"
              onClick={() => {
                selectAllImages()
                setIsSelectionMode(true)
              }}
            >
              <Video className="h-5 w-5" />
              Create Videos from These Photos
            </Button>
            <p className="text-xs text-muted-foreground text-center mt-2">
              Turn your {totals.i2i_generated} generated photos into videos
            </p>
          </div>
        )}

        {/* Selection controls for i2i outputs */}
        {hasI2iOutputs && onAnimateSelected && isSelectionMode && (
          <div className="flex items-center gap-2 pt-3 border-t mt-3 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setIsSelectionMode(false)
                clearSelection()
              }}
            >
              <Square className="h-4 w-4 mr-1" />
              Cancel
            </Button>
            <Button size="sm" variant="ghost" onClick={selectAllImages}>
              Select All
            </Button>
            <Button size="sm" variant="ghost" onClick={clearSelection}>
              Clear
            </Button>
            <span className="text-sm text-muted-foreground">
              {selectedImages.size} selected
            </span>
            <Button
              size="sm"
              variant="default"
              disabled={selectedImages.size === 0}
              onClick={handleAnimateSelected}
              className="ml-auto"
            >
              <Play className="h-4 w-4 mr-1" />
              Animate Selected ({selectedImages.size})
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {groups.map((group, idx) => (
          <Collapsible
            key={idx}
            open={openGroups.has(idx)}
            onOpenChange={() => toggleGroup(idx)}
          >
            <div className="border rounded-lg">
              <CollapsibleTrigger className="w-full">
                <div className="flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors">
                  {/* Source Thumbnail */}
                  <img
                    src={group.source_image}
                    alt={`Source ${idx + 1}`}
                    className="w-12 h-12 object-cover rounded"
                    width={48}
                    height={48}
                    decoding="async"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = group.source_image
                    }}
                  />

                  <div className="flex-1 text-left">
                    <p className="font-medium">Source {idx + 1}</p>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      {group.i2i_outputs.length > 0 && (
                        <span>{group.i2i_outputs.length} images</span>
                      )}
                      {group.i2v_outputs.length > 0 && (
                        <span>{group.i2v_outputs.length} videos</span>
                      )}
                    </div>
                  </div>

                  <ChevronDown
                    className={cn(
                      "h-5 w-5 transition-transform",
                      openGroups.has(idx) && "rotate-180"
                    )}
                  />
                </div>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="p-3 pt-0 space-y-4">
                  {/* I2I Outputs */}
                  {group.i2i_outputs.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Image className="h-4 w-4" />
                        Image Variations
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        {group.i2i_outputs.map((url, i) => {
                          const thumbnailUrl = group.i2i_thumbnails?.[i]
                          return (
                          <div
                            key={i}
                            className={cn(
                              "relative aspect-[9/16] rounded overflow-hidden border group cursor-pointer",
                              isSelectionMode && selectedImages.has(url) && "ring-2 ring-primary ring-offset-2"
                            )}
                            onClick={(e) => {
                              if (isSelectionMode) {
                                toggleImageSelection(url, e)
                              } else {
                                window.open(url, '_blank')  // Open full resolution
                              }
                            }}
                          >
                            <img
                              src={thumbnailUrl || url}
                              alt={`Variation ${i + 1}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                              decoding="async"
                            />

                            {/* Selection checkbox overlay */}
                            {isSelectionMode && (
                              <div
                                className={cn(
                                  "absolute top-2 left-2 w-6 h-6 rounded border-2 flex items-center justify-center transition-colors",
                                  selectedImages.has(url)
                                    ? "bg-primary border-primary"
                                    : "bg-white/80 border-gray-300"
                                )}
                              >
                                {selectedImages.has(url) && (
                                  <Check className="h-4 w-4 text-white" />
                                )}
                              </div>
                            )}

                            {/* Hover overlay for non-selection mode */}
                            {!isSelectionMode && (
                              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <ExternalLink className="h-5 w-5 text-white" />
                              </div>
                            )}
                          </div>
                        )})}

                      </div>
                    </div>
                  )}

                  {/* I2V Outputs */}
                  {group.i2v_outputs.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Video className="h-4 w-4" />
                          Videos
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => downloadGroupVideos(group)}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          Download
                        </Button>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        {group.i2v_outputs.map((url, i) => (
                          <div
                            key={i}
                            className="relative aspect-[9/16] rounded overflow-hidden border bg-black"
                          >
                            <video
                              src={url}
                              className="w-full h-full object-cover"
                              controls
                              muted
                              loop
                              playsInline
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        ))}
      </CardContent>
    </Card>
  )
}

export type { SourceGroup }

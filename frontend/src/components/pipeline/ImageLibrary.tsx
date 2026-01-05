import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Check, Image, Loader2, RefreshCw, CheckSquare, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LibraryImage {
  url: string
  thumbnail_url: string | null  // Small preview for fast loading
  step_id: number
  pipeline_id: number
  source_image: string | null
  prompt: string | null
  model: string
  created_at: string | null
}

interface ImageLibraryProps {
  selectedImages: string[]
  onSelectionChange: (urls: string[]) => void
  disabled?: boolean
}

// Hover preview component
function HoverPreview({ image, position }: { image: LibraryImage | null; position: { x: number; y: number } }) {
  if (!image) return null

  // Position the preview to the right of cursor, or left if too close to edge
  const previewWidth = 300
  const previewHeight = 500
  const padding = 20

  let left = position.x + padding
  let top = position.y - previewHeight / 2

  // Keep within viewport
  if (left + previewWidth > window.innerWidth - padding) {
    left = position.x - previewWidth - padding
  }
  if (top < padding) top = padding
  if (top + previewHeight > window.innerHeight - padding) {
    top = window.innerHeight - previewHeight - padding
  }

  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{ left, top }}
    >
      <div className="bg-black/90 rounded-lg shadow-2xl overflow-hidden border border-white/20">
        <img
          src={image.url}
          alt={image.prompt || 'Preview'}
          className="w-[300px] h-auto max-h-[500px] object-contain"
          loading="eager"
        />
        {image.prompt && (
          <div className="p-2 text-xs text-white/80 max-w-[300px] truncate">
            {image.prompt}
          </div>
        )}
      </div>
    </div>
  )
}

const BATCH_SIZE = 100  // Load 100 images at a time

export function ImageLibrary({ selectedImages, onSelectionChange, disabled }: ImageLibraryProps) {
  const [images, setImages] = useState<LibraryImage[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Hover preview state
  const [hoverImage, setHoverImage] = useState<LibraryImage | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  const hoverTimeoutRef = useRef<number | null>(null)

  const fetchImages = useCallback(async (offset = 0, append = false) => {
    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }

    try {
      const response = await fetch(`/api/pipelines/images/library?limit=${BATCH_SIZE}&offset=${offset}`)
      if (response.ok) {
        const data = await response.json()
        if (append) {
          setImages(prev => [...prev, ...data.images])
        } else {
          setImages(data.images)
        }
        setTotal(data.total)
        setHasMore(offset + data.images.length < data.total)
      }
    } catch (error) {
      console.error('Failed to fetch image library:', error)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [])

  useEffect(() => {
    fetchImages(0, false)
  }, [fetchImages])

  // Infinite scroll - load more when scrolled near bottom
  const handleScroll = useCallback(() => {
    if (!scrollRef.current || loadingMore || !hasMore) return

    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    if (scrollHeight - scrollTop - clientHeight < 200) {
      setLoadingMore(true)
      fetchImages(images.length, true)
    }
  }, [fetchImages, images.length, loadingMore, hasMore])

  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore) {
      fetchImages(images.length, true)
    }
  }, [fetchImages, images.length, loadingMore, hasMore])

  const toggleImage = (url: string) => {
    if (disabled) return
    const newSelection = selectedImages.includes(url)
      ? selectedImages.filter(u => u !== url)
      : [...selectedImages, url]
    onSelectionChange(newSelection)
  }

  const selectAll = () => {
    if (disabled) return
    onSelectionChange(images.map(img => img.url))
  }

  const clearSelection = () => {
    onSelectionChange([])
  }

  // Hover handlers with delay to prevent flicker
  const handleMouseEnter = (img: LibraryImage, e: React.MouseEvent) => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
    }
    hoverTimeoutRef.current = window.setTimeout(() => {
      setHoverImage(img)
      setHoverPosition({ x: e.clientX, y: e.clientY })
    }, 300) // 300ms delay before showing preview
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (hoverImage) {
      setHoverPosition({ x: e.clientX, y: e.clientY })
    }
  }

  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
    }
    setHoverImage(null)
  }

  if (loading && images.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (images.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Image className="h-12 w-12 mx-auto mb-3 opacity-50" />
        <p className="font-medium">No generated images yet</p>
        <p className="text-sm mt-1">Generate some photos first, then come back here to turn them into videos</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline">{total} images</Badge>
          <Badge variant="outline" className="text-xs">
            {images.length} loaded
          </Badge>
          {selectedImages.length > 0 && (
            <Badge variant="default">{selectedImages.length} selected</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => fetchImages(0, false)}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4 mr-1", loading && "animate-spin")} />
            Refresh
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={selectAll}
            disabled={disabled}
          >
            <CheckSquare className="h-4 w-4 mr-1" />
            Select All
          </Button>
          {selectedImages.length > 0 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={clearSelection}
              disabled={disabled}
            >
              <Square className="h-4 w-4 mr-1" />
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Image grid with scroll */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="grid grid-cols-5 gap-2 max-h-[400px] overflow-y-auto pr-2"
      >
        {images.map((img, idx) => {
          const isSelected = selectedImages.includes(img.url)
          return (
            <div
              key={`${img.step_id}-${idx}`}
              className={cn(
                "relative aspect-[9/16] rounded overflow-hidden border cursor-pointer group transition-all",
                isSelected && "ring-2 ring-primary ring-offset-2",
                disabled && "opacity-50 cursor-not-allowed"
              )}
              onClick={() => toggleImage(img.url)}
              onMouseEnter={(e) => handleMouseEnter(img, e)}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
            >
              {/* Use thumbnail if available, fallback to full image */}
              <img
                src={img.thumbnail_url || img.url}
                alt={img.prompt || `Image ${idx + 1}`}
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
              />

              {/* Selection checkbox */}
              <div
                className={cn(
                  "absolute top-1 left-1 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors",
                  isSelected
                    ? "bg-primary border-primary"
                    : "bg-white/80 border-gray-300 opacity-0 group-hover:opacity-100"
                )}
              >
                {isSelected && (
                  <Check className="h-3 w-3 text-white" />
                )}
              </div>

              {/* Model badge */}
              <div className="absolute bottom-1 left-1 right-1">
                <Badge variant="secondary" className="text-[10px] px-1 py-0 opacity-80">
                  {img.model}
                </Badge>
              </div>
            </div>
          )
        })}

        {/* Loading placeholder cells */}
        {loadingMore && Array.from({ length: 5 }).map((_, i) => (
          <div key={`loading-${i}`} className="aspect-[9/16] rounded bg-muted animate-pulse" />
        ))}
      </div>

      {/* Load more button */}
      {hasMore && (
        <div className="text-center">
          <Button
            size="sm"
            variant="outline"
            onClick={loadMore}
            disabled={loadingMore}
          >
            {loadingMore ? (
              <>
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                Loading...
              </>
            ) : (
              `Load more (${total - images.length} remaining)`
            )}
          </Button>
        </div>
      )}

      {selectedImages.length > 0 && (
        <p className="text-sm text-muted-foreground text-center">
          {selectedImages.length} image{selectedImages.length !== 1 ? 's' : ''} selected for video generation
        </p>
      )}

      {/* Hover preview popup */}
      <HoverPreview image={hoverImage} position={hoverPosition} />
    </div>
  )
}

interface ImageSourceSelectorProps {
  mode: 'upload' | 'library'
  onModeChange: (mode: 'upload' | 'library') => void
  uploadContent: React.ReactNode
  selectedLibraryImages: string[]
  onLibrarySelectionChange: (urls: string[]) => void
  disabled?: boolean
}

export function ImageSourceSelector({
  mode,
  onModeChange,
  uploadContent,
  selectedLibraryImages,
  onLibrarySelectionChange,
  disabled,
}: ImageSourceSelectorProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Image className="h-5 w-5" />
          Source Images
        </CardTitle>
        <CardDescription>
          Upload new images or select from your generated library
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={mode} onValueChange={(v) => onModeChange(v as 'upload' | 'library')}>
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="upload">Upload New</TabsTrigger>
            <TabsTrigger value="library">
              From Library
              {selectedLibraryImages.length > 0 && (
                <Badge variant="default" className="ml-2 h-5 px-1.5">
                  {selectedLibraryImages.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="mt-0">
            {uploadContent}
          </TabsContent>

          <TabsContent value="library" className="mt-0">
            <ImageLibrary
              selectedImages={selectedLibraryImages}
              onSelectionChange={onLibrarySelectionChange}
              disabled={disabled}
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

export type { LibraryImage }

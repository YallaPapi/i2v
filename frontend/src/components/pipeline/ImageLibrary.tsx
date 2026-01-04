import { useState, useEffect, useCallback } from 'react'
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

export function ImageLibrary({ selectedImages, onSelectionChange, disabled }: ImageLibraryProps) {
  const [images, setImages] = useState<LibraryImage[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)

  const fetchImages = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/pipelines/images/library?limit=50')
      if (response.ok) {
        const data = await response.json()
        setImages(data.images)
        setTotal(data.total)
      }
    } catch (error) {
      console.error('Failed to fetch image library:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchImages()
  }, [fetchImages])

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
          {selectedImages.length > 0 && (
            <Badge variant="default">{selectedImages.length} selected</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={fetchImages}
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

      {/* Image grid */}
      <div className="grid grid-cols-5 gap-2 max-h-[400px] overflow-y-auto pr-2">
        {images.map((img, idx) => (
          <div
            key={`${img.step_id}-${idx}`}
            className={cn(
              "relative aspect-[9/16] rounded overflow-hidden border cursor-pointer group transition-all",
              selectedImages.includes(img.url) && "ring-2 ring-primary ring-offset-2",
              disabled && "opacity-50 cursor-not-allowed"
            )}
            onClick={() => toggleImage(img.url)}
          >
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
                selectedImages.includes(img.url)
                  ? "bg-primary border-primary"
                  : "bg-white/80 border-gray-300 opacity-0 group-hover:opacity-100"
              )}
            >
              {selectedImages.includes(img.url) && (
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
        ))}
      </div>

      {selectedImages.length > 0 && (
        <p className="text-sm text-muted-foreground text-center">
          {selectedImages.length} image{selectedImages.length !== 1 ? 's' : ''} selected for video generation
        </p>
      )}
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

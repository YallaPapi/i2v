import { useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Download,
  Check,
  Play,
  Image,
  Video,
  Grid,
  LayoutGrid,
  RefreshCw,
  ExternalLink,
  X,
} from 'lucide-react'

interface OutputItem {
  id: string
  url: string
  type: 'image' | 'video'
  stepType?: string
  model?: string
  createdAt?: string
  prompt?: string
}

interface OutputGalleryProps {
  outputs: OutputItem[]
  onRerun?: (item: OutputItem) => void
  onDownload?: (items: OutputItem[]) => void
  className?: string
}

type FilterType = 'all' | 'image' | 'video'
type LayoutType = 'grid' | 'masonry'

export function OutputGallery({
  outputs,
  onRerun,
  onDownload,
  className,
}: OutputGalleryProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState<FilterType>('all')
  const [layout, setLayout] = useState<LayoutType>('grid')
  const [playingVideo, setPlayingVideo] = useState<string | null>(null)
  const [lightboxItem, setLightboxItem] = useState<OutputItem | null>(null)

  const filteredOutputs = useMemo(() => {
    if (filter === 'all') return outputs
    return outputs.filter(o => o.type === filter)
  }, [outputs, filter])

  const toggleSelect = (id: string) => {
    const newSelected = new Set(selectedIds)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedIds(newSelected)
  }

  const selectAll = () => {
    if (selectedIds.size === filteredOutputs.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredOutputs.map(o => o.id)))
    }
  }

  const handleDownload = () => {
    if (onDownload) {
      const selectedItems = outputs.filter(o => selectedIds.has(o.id))
      onDownload(selectedItems.length > 0 ? selectedItems : outputs)
    }
  }

  const imageCount = outputs.filter(o => o.type === 'image').length
  const videoCount = outputs.filter(o => o.type === 'video').length

  return (
    <div className={cn("space-y-4", className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          {/* Filter buttons */}
          <div className="flex items-center border rounded-lg overflow-hidden">
            <button
              onClick={() => setFilter('all')}
              className={cn(
                "px-3 py-1.5 text-sm transition-colors",
                filter === 'all' ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              )}
            >
              All ({outputs.length})
            </button>
            <button
              onClick={() => setFilter('image')}
              className={cn(
                "px-3 py-1.5 text-sm flex items-center gap-1 transition-colors border-l",
                filter === 'image' ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              )}
            >
              <Image className="h-3 w-3" />
              {imageCount}
            </button>
            <button
              onClick={() => setFilter('video')}
              className={cn(
                "px-3 py-1.5 text-sm flex items-center gap-1 transition-colors border-l",
                filter === 'video' ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              )}
            >
              <Video className="h-3 w-3" />
              {videoCount}
            </button>
          </div>

          {/* Layout toggle */}
          <div className="flex items-center border rounded-lg overflow-hidden">
            <button
              onClick={() => setLayout('grid')}
              className={cn(
                "p-1.5 transition-colors",
                layout === 'grid' ? "bg-muted" : "hover:bg-muted"
              )}
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setLayout('masonry')}
              className={cn(
                "p-1.5 transition-colors border-l",
                layout === 'masonry' ? "bg-muted" : "hover:bg-muted"
              )}
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Select all */}
          <Button
            variant="outline"
            size="sm"
            onClick={selectAll}
          >
            <Check className="h-4 w-4 mr-1" />
            {selectedIds.size === filteredOutputs.length ? 'Deselect All' : 'Select All'}
          </Button>

          {/* Download */}
          {onDownload && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
            >
              <Download className="h-4 w-4 mr-1" />
              Download {selectedIds.size > 0 ? `(${selectedIds.size})` : 'All'}
            </Button>
          )}
        </div>
      </div>

      {/* Gallery Grid */}
      {filteredOutputs.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Image className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>No outputs yet</p>
        </div>
      ) : (
        <div className={cn(
          "grid gap-3",
          layout === 'grid'
            ? "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
            : "columns-2 sm:columns-3 md:columns-4 lg:columns-5"
        )}>
          {filteredOutputs.map((item) => (
            <div
              key={item.id}
              className={cn(
                "relative group rounded-lg overflow-hidden border bg-muted cursor-pointer",
                layout === 'masonry' && "break-inside-avoid mb-3",
                selectedIds.has(item.id) && "ring-2 ring-primary"
              )}
              onClick={() => setLightboxItem(item)}
            >
              {/* Thumbnail */}
              {item.type === 'image' ? (
                <img
                  src={item.url}
                  alt=""
                  className="w-full aspect-square object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="relative aspect-video bg-black">
                  <video
                    src={item.url}
                    className="w-full h-full object-cover"
                    muted
                    loop
                    playsInline
                    onMouseEnter={(e) => {
                      setPlayingVideo(item.id)
                      e.currentTarget.play()
                    }}
                    onMouseLeave={(e) => {
                      setPlayingVideo(null)
                      e.currentTarget.pause()
                      e.currentTarget.currentTime = 0
                    }}
                  />
                  {playingVideo !== item.id && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="p-2 bg-black/50 rounded-full">
                        <Play className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Selection checkbox */}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  toggleSelect(item.id)
                }}
                className={cn(
                  "absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center transition-all",
                  selectedIds.has(item.id)
                    ? "bg-primary border-primary"
                    : "bg-white/80 border-white/80 opacity-0 group-hover:opacity-100"
                )}
              >
                {selectedIds.has(item.id) && (
                  <Check className="h-3 w-3 text-white" />
                )}
              </button>

              {/* Actions overlay */}
              <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="flex items-center justify-end gap-1">
                  {onRerun && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onRerun(item)
                      }}
                      className="p-1.5 bg-white/20 hover:bg-white/30 rounded transition-colors"
                      title="Re-run with this output"
                    >
                      <RefreshCw className="h-3 w-3 text-white" />
                    </button>
                  )}
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="p-1.5 bg-white/20 hover:bg-white/30 rounded transition-colors"
                    title="Open in new tab"
                  >
                    <ExternalLink className="h-3 w-3 text-white" />
                  </a>
                </div>
              </div>

              {/* Type badge */}
              <div className="absolute top-2 right-2">
                <div className="p-1 bg-black/50 rounded">
                  {item.type === 'image' ? (
                    <Image className="h-3 w-3 text-white" />
                  ) : (
                    <Video className="h-3 w-3 text-white" />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightboxItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90"
          onClick={() => setLightboxItem(null)}
        >
          <button
            className="absolute top-4 right-4 p-2 text-white hover:bg-white/10 rounded-full"
            onClick={() => setLightboxItem(null)}
          >
            <X className="h-6 w-6" />
          </button>

          <div
            className="max-w-[90vw] max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {lightboxItem.type === 'image' ? (
              <img
                src={lightboxItem.url}
                alt=""
                className="max-w-full max-h-[90vh] object-contain"
              />
            ) : (
              <video
                src={lightboxItem.url}
                controls
                autoPlay
                className="max-w-full max-h-[90vh]"
              />
            )}

            {/* Info panel */}
            <div className="mt-4 flex items-center justify-between text-white">
              <div className="text-sm text-white/70">
                {lightboxItem.model && <span>{lightboxItem.model}</span>}
                {lightboxItem.prompt && (
                  <p className="mt-1 max-w-lg truncate">{lightboxItem.prompt}</p>
                )}
              </div>
              <div className="flex gap-2">
                {onRerun && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      onRerun(lightboxItem)
                      setLightboxItem(null)
                    }}
                  >
                    <RefreshCw className="h-4 w-4 mr-1" />
                    Re-run
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => window.open(lightboxItem.url, '_blank')}
                >
                  <Download className="h-4 w-4 mr-1" />
                  Download
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export type { OutputItem }

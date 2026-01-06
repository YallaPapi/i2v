import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Image as ImageIcon, CheckCircle, XCircle, Clock, RefreshCw, Layers, Play, Download, Star, EyeOff, Eye, X, Plus, ChevronDown, ChevronUp } from 'lucide-react'
import { PipelineCardSkeleton, OutputGridSkeleton } from '@/components/ui/skeleton'
import {
  usePipelines,
  usePipelineDetails,
  useTogglePipelineFavorite,
  useTogglePipelineHidden,
  useUpdatePipelineTags,
} from '@/hooks/useJobs'
import type { PipelineSummary, PipelineDetails } from '@/api/client'
const QUICK_TAGS = ['demo', 'test', 'best', 'wip', 'production']
const TAG_COLORS: Record<string, string> = {
  demo: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  test: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  best: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  wip: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  production: 'bg-green-500/20 text-green-400 border-green-500/30',
}
function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success"><CheckCircle className="h-3 w-3 mr-1" />Completed</Badge>
    case 'failed':
      return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>
    case 'running':
    case 'submitted':
      return <Badge variant="pending"><Clock className="h-3 w-3 mr-1" />Processing</Badge>
    default:
      return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" />Pending</Badge>
  }
}
function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}
const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]
// Hover preview component for full-res image on hover
function HoverPreview({ output, position }: {
  output: { url: string; thumbnailUrl?: string; prompt?: string } | null
  position: { x: number; y: number }
}) {
  if (!output) return null
  const previewWidth = 300
  const previewHeight = 500
  const padding = 20
  let left = position.x + padding
  let top = position.y - previewHeight / 2
  if (typeof window !== 'undefined') {
    if (left + previewWidth > window.innerWidth - padding) {
      left = position.x - previewWidth - padding
    }
    if (top < padding) top = padding
    if (top + previewHeight > window.innerHeight - padding) {
      top = window.innerHeight - previewHeight - padding
    }
  }
  return (
    <div className="fixed z-50 pointer-events-none" style={{ left, top }}>
      <div className="bg-black/90 rounded-lg shadow-2xl overflow-hidden border border-white/20">
        <img src={output.url} alt={output.prompt || 'Preview'} className="w-[300px] h-auto max-h-[500px] object-contain" />
        {output.prompt && (
          <div className="p-2 text-xs text-white/80 max-w-[300px] truncate">{output.prompt}</div>
        )}
      </div>
    </div>
  )
}

// Extract outputs from pipeline details
function getOutputs(details: PipelineDetails | undefined) {
  if (!details) return []
  const outputs: { url: string; thumbnailUrl?: string; type: 'image' | 'video'; prompt?: string }[] = []
  for (const step of details.steps) {
    if (step.outputs?.items) {
      const thumbnailUrls = step.outputs.thumbnail_urls || []
      for (let i = 0; i < step.outputs.items.length; i++) {
        const item = step.outputs.items[i]
        outputs.push({
          url: item.url,
          thumbnailUrl: thumbnailUrls[i],
          type: item.type as 'image' | 'video',
          prompt: item.prompt
        })
      }
    }
  }
  return outputs
}
const PAGE_SIZE = 10
// Individual pipeline item component
function PipelineItem({
  pipeline,
  isExpanded,
  onToggleExpand,
  selectedOutputs,
  onToggleSelect,
  onSelectAll,
}: {
  pipeline: PipelineSummary
  isExpanded: boolean
  onToggleExpand: () => void
  selectedOutputs: Set<string>
  onToggleSelect: (url: string) => void
  onSelectAll: (urls: string[], selectAll: boolean) => void
}) {
  const { data: details, isLoading: isLoadingDetails } = usePipelineDetails(pipeline.id, isExpanded)
  const toggleFavorite = useTogglePipelineFavorite()
  const toggleHidden = useTogglePipelineHidden()
  const updateTags = useUpdatePipelineTags()
  const [editingTags, setEditingTags] = useState(false)
  const [newTagInput, setNewTagInput] = useState('')
  const [hoverOutput, setHoverOutput] = useState<{ url: string; thumbnailUrl?: string; prompt?: string } | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  const hoverTimeoutRef = useRef<number | null>(null)
  const pipelineTags = pipeline.tags || []
  const outputs = getOutputs(details)
  const pipelineSelected = outputs.filter(o => selectedOutputs.has(o.url))
  const handleMouseEnter = (output: typeof outputs[0], e: React.MouseEvent) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    hoverTimeoutRef.current = window.setTimeout(() => {
      setHoverOutput(output)
      setHoverPosition({ x: e.clientX, y: e.clientY })
    }, 300)
  }
  const handleMouseMove = (e: React.MouseEvent) => {
    if (hoverOutput) setHoverPosition({ x: e.clientX, y: e.clientY })
  }
  const handleMouseLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    setHoverOutput(null)
  }
  const handleAddTag = (tag: string) => {
    if (!pipelineTags.includes(tag)) {
      updateTags.mutate({ id: pipeline.id, tags: [...pipelineTags, tag] })
    }
    setNewTagInput('')
    setEditingTags(false)
  }
  const handleRemoveTag = (tag: string) => {
    updateTags.mutate({ id: pipeline.id, tags: pipelineTags.filter(t => t !== tag) })
  }
  return (
    <div className={`border rounded-lg p-4 ${pipeline.is_hidden ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-3">
          <button
            onClick={() => toggleFavorite.mutate(pipeline.id)}
            className="p-1 hover:bg-muted rounded"
            disabled={toggleFavorite.isPending}
          >
            <Star className={`h-5 w-5 ${pipeline.is_favorite ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground'}`} />
          </button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-medium">{pipeline.name}</p>
              {pipeline.model_info && (
                <span className="px-1.5 py-0.5 text-[10px] font-medium bg-primary/10 text-primary rounded">
                  {pipeline.model_info}
                </span>
              )}
              {pipeline.total_cost && (
                <span className="px-1.5 py-0.5 text-[10px] font-medium bg-green-500/10 text-green-500 rounded">
                  ${pipeline.total_cost.toFixed(2)}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatDate(pipeline.created_at)} • {pipeline.step_count} steps • {pipeline.output_count} outputs
            </p>
            {pipeline.first_prompt && (
              <p className="text-xs text-muted-foreground/80 italic truncate max-w-md">
                "{pipeline.first_prompt}"
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => toggleHidden.mutate(pipeline.id)}
            className="p-1 hover:bg-muted rounded text-muted-foreground"
            disabled={toggleHidden.isPending}
          >
            {pipeline.is_hidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
          </button>
          {getStatusBadge(pipeline.status)}
        </div>
      </div>
      {/* Tags */}
      <div className="flex flex-wrap items-center gap-1 mb-2">
        {pipelineTags.map(tag => (
          <span key={tag} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${TAG_COLORS[tag] || 'bg-muted'}`}>
            {tag}
            <button onClick={() => handleRemoveTag(tag)} className="hover:text-destructive">
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {editingTags ? (
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newTagInput) handleAddTag(newTagInput)
                else if (e.key === 'Escape') { setEditingTags(false); setNewTagInput('') }
              }}
              className="w-20 px-1 py-0.5 text-xs border rounded bg-background"
              autoFocus
            />
            {QUICK_TAGS.filter(t => !pipelineTags.includes(t)).slice(0, 3).map(t => (
              <button key={t} onClick={() => handleAddTag(t)} className={`px-1.5 py-0.5 text-xs rounded border ${TAG_COLORS[t]}`}>
                {t}
              </button>
            ))}
          </div>
        ) : (
          <button onClick={() => setEditingTags(true)} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-muted-foreground hover:bg-muted">
            <Plus className="h-3 w-3" /> tag
          </button>
        )}
      </div>
      {/* Outputs */}
      {pipeline.output_count > 0 && (
        <div className="space-y-2">
          <button onClick={onToggleExpand} className="flex items-center gap-2 text-sm font-medium hover:text-primary">
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Outputs ({pipeline.output_count})
            {pipelineSelected.length > 0 && <span className="text-primary">• {pipelineSelected.length} selected</span>}
            {!isExpanded && pipeline.first_thumbnail_url && (
              <img src={pipeline.first_thumbnail_url} alt="" className="h-8 w-6 object-cover rounded ml-2" loading="lazy" />
            )}
          </button>
          {isExpanded && (
            <>
              {isLoadingDetails ? (
                <OutputGridSkeleton count={Math.min(pipeline.output_count, 8)} />
              ) : outputs.length > 0 ? (
                <>
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => onSelectAll(outputs.map(o => o.url), !outputs.every(o => selectedOutputs.has(o.url)))}>
                      {outputs.every(o => selectedOutputs.has(o.url)) ? 'Deselect All' : 'Select All'}
                    </Button>
                    <Button variant="default" size="sm" disabled={pipelineSelected.length === 0} onClick={async () => {
                      for (let i = 0; i < pipelineSelected.length; i++) {
                        const o = pipelineSelected[i]
                        try {
                          // Use backend proxy to avoid CORS issues
                          const proxyUrl = `/api/pipelines/download?url=${encodeURIComponent(o.url)}`
                          const response = await fetch(proxyUrl)
                          const blob = await response.blob()
                          const blobUrl = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = blobUrl
                          a.download = `output-${i + 1}.${o.type === 'video' ? 'mp4' : 'png'}`
                          a.click()
                          URL.revokeObjectURL(blobUrl)
                          await new Promise(r => setTimeout(r, 300))
                        } catch (e) {
                          console.error('Download failed:', o.url, e)
                        }
                      }
                    }}>
                      <Download className="h-4 w-4 mr-1" /> Download ({pipelineSelected.length})
                    </Button>
                  </div>
                  <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                    {outputs.map((output, idx) => {
                      const isSelected = selectedOutputs.has(output.url)
                      return (
                        <div key={idx} className={`relative aspect-[9/16] bg-muted rounded-lg overflow-hidden cursor-pointer ${isSelected ? 'ring-2 ring-primary' : ''}`}
                          onClick={() => onToggleSelect(output.url)}
                          onMouseEnter={(e) => output.type === 'image' && handleMouseEnter(output, e)}
                          onMouseMove={handleMouseMove}
                          onMouseLeave={handleMouseLeave}>
                          {output.type === 'video' ? (
                            <video src={output.url} className="w-full h-full object-cover" muted playsInline preload="none"
                              onMouseEnter={(e) => e.currentTarget.play()} onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0 }} />
                          ) : (
                            <img src={output.thumbnailUrl || output.url} alt="" className="w-full h-full object-cover" loading="lazy" />
                          )}
                          <div className={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center ${isSelected ? 'bg-primary border-primary' : 'bg-white/80 border-white/80'}`}>
                            {isSelected && <CheckCircle className="h-3 w-3 text-white" />}
                          </div>
                          <div className="absolute top-2 right-2">
                            {output.type === 'video' ? <Play className="h-4 w-4 text-white drop-shadow" /> : <ImageIcon className="h-4 w-4 text-white drop-shadow" />}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <HoverPreview output={hoverOutput} position={hoverPosition} />
                </>
              ) : <p className="text-sm text-muted-foreground">No outputs</p>}
            </>
          )}
        </div>
      )}
    </div>
  )
}
export function Jobs() {
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedOutputs, setSelectedOutputs] = useState<Set<string>>(new Set())
  const [expandedOutputs, setExpandedOutputs] = useState<Set<number>>(new Set())
  const [demoMode, setDemoMode] = useState(() => localStorage.getItem('demoMode') === 'true')
  const [showHidden, setShowHidden] = useState(false)
  const [tagFilter, setTagFilter] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)
  // Query params - fetch more than displayed to enable smooth "load more"
  const queryParams = useMemo(() => ({
    favorites: demoMode || undefined,
    hidden: showHidden || undefined,
    tag: tagFilter || undefined,
    limit: displayCount,
    offset: 0,
  }), [demoMode, showHidden, tagFilter, displayCount])
  const { data, isLoading, isFetching, refetch } = usePipelines(queryParams)
  const pipelines = data?.pipelines || []
  const total = data?.total || 0
  // Reset display count when filters change
  useEffect(() => {
    setDisplayCount(PAGE_SIZE)
  }, [demoMode, showHidden, tagFilter])
  // Save demo mode
  if (typeof window !== 'undefined') localStorage.setItem('demoMode', demoMode.toString())
  const toggleExpand = useCallback((id: number) => {
    setExpandedOutputs(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])
  const toggleSelect = useCallback((url: string) => {
    setSelectedOutputs(prev => {
      const next = new Set(prev)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }, [])
  const selectAll = useCallback((urls: string[], select: boolean) => {
    setSelectedOutputs(prev => {
      const next = new Set(prev)
      urls.forEach(url => select ? next.add(url) : next.delete(url))
      return next
    })
  }, [])
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">All Jobs</h1>
          <p className="text-muted-foreground">View and manage all your generation jobs</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant={demoMode ? 'default' : 'outline'} size="sm" onClick={() => setDemoMode(!demoMode)} className="gap-1">
            <Star className={`h-4 w-4 ${demoMode ? 'fill-current' : ''}`} /> Demo Mode
          </Button>
          <Button variant={showHidden ? 'secondary' : 'outline'} size="sm" onClick={() => setShowHidden(!showHidden)} className="gap-1">
            {showHidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {showHidden ? 'Showing Hidden' : 'Hidden'}
          </Button>
          <Select options={[{ value: '', label: 'All Tags' }, ...QUICK_TAGS.map(t => ({ value: t, label: t }))]} value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} />
          <div className="w-36">
            <Select options={STATUS_OPTIONS} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
          </div>
          <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" /> All Jobs ({pipelines.length}{total > pipelines.length ? ` / ${total}` : ''})
          </CardTitle>
          <CardDescription>Your generated photos and videos from the Playground</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => <PipelineCardSkeleton key={i} />)}
            </div>
          ) : pipelines.length > 0 ? (
            <div className="h-[calc(100vh-280px)] overflow-auto space-y-4">
              {pipelines.map(pipeline => (
                <PipelineItem
                  key={pipeline.id}
                  pipeline={pipeline}
                  isExpanded={expandedOutputs.has(pipeline.id)}
                  onToggleExpand={() => toggleExpand(pipeline.id)}
                  selectedOutputs={selectedOutputs}
                  onToggleSelect={toggleSelect}
                  onSelectAll={selectAll}
                />
              ))}
              {pipelines.length < total && (
                <div className="flex justify-center py-4">
                  <Button variant="outline" onClick={() => setDisplayCount(prev => prev + PAGE_SIZE)} disabled={isFetching}>
                    {isFetching ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : null}
                    Load More ({pipelines.length} / {total})
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              No pipeline jobs found. Go to Playground to create one.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

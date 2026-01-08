import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
// Card imports removed - using flat layout now
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Image as ImageIcon, CheckCircle, XCircle, Clock, RefreshCw, Play, Download, Star, EyeOff, Eye, X, Plus, ChevronDown, ChevronUp, Loader2, RotateCcw, Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
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

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'name', label: 'Name A-Z' },
  { value: 'cost_high', label: 'Cost: High-Low' },
  { value: 'cost_low', label: 'Cost: Low-High' },
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
  const [showPrompts, setShowPrompts] = useState(false)
  const [hoverOutput, setHoverOutput] = useState<{ url: string; thumbnailUrl?: string; prompt?: string } | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  const [downloadState, setDownloadState] = useState<'idle' | 'downloading' | 'done'>('idle')
  const [downloadProgress, setDownloadProgress] = useState({ current: 0, total: 0 })
  const hoverTimeoutRef = useRef<number | null>(null)
  const pipelineTags = pipeline.tags || []
  const outputs = getOutputs(details)
  const pipelineSelected = outputs.filter(o => selectedOutputs.has(o.url))
  // Get all unique prompts from outputs
  const allPrompts = [...new Set(outputs.map(o => o.prompt).filter(Boolean))]
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
    <div className={`border rounded-lg p-4 hover:border-primary/30 transition-colors ${pipeline.is_hidden ? 'opacity-60' : ''}`}>
      {/* Main row: Status + Name + Actions */}
      <div className="flex items-start gap-3 mb-2">
        {/* Left: Status + Favorite */}
        <div className="flex items-center gap-2 pt-0.5">
          {getStatusBadge(pipeline.status)}
          <button
            onClick={() => toggleFavorite.mutate(pipeline.id)}
            className="p-1 hover:bg-muted rounded"
            disabled={toggleFavorite.isPending}
          >
            <Star className={`h-4 w-4 ${pipeline.is_favorite ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground'}`} />
          </button>
        </div>

        {/* Center: Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold">{pipeline.name}</p>
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
          {pipeline.first_prompt && !showPrompts && (
            <button
              onClick={() => setShowPrompts(true)}
              className="text-xs text-muted-foreground/80 italic hover:text-foreground text-left mt-0.5 flex items-center gap-1"
            >
              <span className="truncate max-w-lg">"{pipeline.first_prompt}"</span>
              <ChevronDown className="h-3 w-3 flex-shrink-0" />
            </button>
          )}
        </div>

        {/* Right: Hide button */}
        <button
          onClick={() => toggleHidden.mutate(pipeline.id)}
          className="p-1.5 hover:bg-muted rounded text-muted-foreground"
          disabled={toggleHidden.isPending}
          title={pipeline.is_hidden ? 'Show' : 'Hide'}
        >
          {pipeline.is_hidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
        </button>
      </div>

      {/* Expanded prompts - outside main row */}
      {showPrompts && (
        <div className="mb-2 ml-[88px] space-y-2 bg-muted/50 rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">All Prompts ({allPrompts.length || 1})</span>
            <button onClick={() => setShowPrompts(false)} className="text-xs text-muted-foreground hover:text-foreground">
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          {allPrompts.length > 0 ? (
            allPrompts.map((prompt, i) => (
              <p key={i} className="text-xs text-muted-foreground italic border-l-2 border-primary/30 pl-2">
                "{prompt}"
              </p>
            ))
          ) : (
            <p className="text-xs text-muted-foreground italic border-l-2 border-primary/30 pl-2">
              "{pipeline.first_prompt}"
            </p>
          )}
        </div>
      )}

      {/* Inline preview / expand button - show when collapsed */}
      {pipeline.output_count > 0 && !isExpanded && (
        <div className="flex items-center gap-2 mb-2 ml-[88px]">
          <button onClick={onToggleExpand} className="flex items-center gap-1.5 group">
            {/* Show thumbnail if available */}
            {pipeline.first_thumbnail_url && (
              <div className="flex -space-x-2">
                <img src={pipeline.first_thumbnail_url} alt="" className="h-10 w-7 object-cover rounded border-2 border-background" loading="lazy" />
              </div>
            )}
            <span className="text-xs text-muted-foreground group-hover:text-primary">
              {pipeline.output_count} outputs
              <ChevronDown className="h-3 w-3 inline ml-1" />
            </span>
          </button>
        </div>
      )}

      {/* Tags - only show if has tags or editing */}
      {(pipelineTags.length > 0 || editingTags) && (
        <div className="flex flex-wrap items-center gap-1 mb-2 ml-[88px]">
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
      )}

      {/* Add tag button - shown when no tags and not editing */}
      {pipelineTags.length === 0 && !editingTags && (
        <div className="ml-[88px] mb-2">
          <button onClick={() => setEditingTags(true)} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-muted-foreground hover:bg-muted">
            <Plus className="h-3 w-3" /> Add tag
          </button>
        </div>
      )}

      {/* Expanded Outputs */}
      {pipeline.output_count > 0 && isExpanded && (
        <div className="space-y-2 ml-[88px]">
          <div className="flex items-center justify-between">
            <button onClick={onToggleExpand} className="flex items-center gap-2 text-sm font-medium hover:text-primary">
              <ChevronUp className="h-4 w-4" />
              {pipeline.output_count} outputs
              {pipelineSelected.length > 0 && <span className="text-primary">• {pipelineSelected.length} selected</span>}
            </button>
          </div>
          {isLoadingDetails ? (
                <OutputGridSkeleton count={Math.min(pipeline.output_count, 8)} />
              ) : outputs.length > 0 ? (
                <>
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => onSelectAll(outputs.map(o => o.url), !outputs.every(o => selectedOutputs.has(o.url)))}>
                      {outputs.every(o => selectedOutputs.has(o.url)) ? 'Deselect All' : 'Select All'}
                    </Button>
                    <Button variant="default" size="sm" disabled={pipelineSelected.length === 0 || downloadState === 'downloading'} onClick={async () => {
                      const safeName = pipeline.name.replace(/[^a-zA-Z0-9-_]/g, '_').substring(0, 50) || `pipeline-${pipeline.id}`
                      setDownloadState('downloading')
                      setDownloadProgress({ current: 0, total: pipelineSelected.length })
                      for (let i = 0; i < pipelineSelected.length; i++) {
                        const o = pipelineSelected[i]
                        setDownloadProgress({ current: i + 1, total: pipelineSelected.length })
                        try {
                          // Use backend proxy to avoid CORS issues
                          const proxyUrl = `/api/pipelines/download?url=${encodeURIComponent(o.url)}`
                          const response = await fetch(proxyUrl)
                          const blob = await response.blob()
                          const blobUrl = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = blobUrl
                          a.download = `${safeName}-${i + 1}.${o.type === 'video' ? 'mp4' : 'png'}`
                          a.click()
                          URL.revokeObjectURL(blobUrl)
                          await new Promise(r => setTimeout(r, 300))
                        } catch (e) {
                          console.error('Download failed:', o.url, e)
                        }
                      }
                      setDownloadState('done')
                      setTimeout(() => setDownloadState('idle'), 3000)
                    }}>
                      {downloadState === 'downloading' ? (
                        <><Loader2 className="h-4 w-4 mr-1 animate-spin" /> Downloading {downloadProgress.current}/{downloadProgress.total}</>
                      ) : downloadState === 'done' ? (
                        <><CheckCircle className="h-4 w-4 mr-1" /> Downloaded!</>
                      ) : (
                        <><Download className="h-4 w-4 mr-1" /> Download ({pipelineSelected.length})</>
                      )}
                    </Button>
                  </div>
                  <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                    {outputs.map((output, idx) => {
                      const isSelected = selectedOutputs.has(output.url)
                      return (
                        <div key={idx} className={`relative aspect-[9/16] bg-muted rounded-lg overflow-hidden cursor-pointer group ${isSelected ? 'ring-2 ring-primary' : ''}`}
                          onClick={() => onToggleSelect(output.url)}
                          onDoubleClick={(e) => { e.stopPropagation(); window.open(output.url, '_blank') }}
                          onMouseEnter={(e) => output.type === 'image' && handleMouseEnter(output, e)}
                          onMouseMove={handleMouseMove}
                          onMouseLeave={handleMouseLeave}>
                          {output.type === 'video' ? (
                            <video
                              src={output.url}
                              className="w-full h-full object-cover"
                              muted
                              playsInline
                              preload="auto"
                              poster={output.thumbnailUrl}
                              onMouseEnter={(e) => e.currentTarget.play()}
                              onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0 }}
                            />
                          ) : (
                            <img src={output.thumbnailUrl || output.url} alt="" className="w-full h-full object-cover" loading="lazy" />
                          )}
                          <div className={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center ${isSelected ? 'bg-primary border-primary' : 'bg-white/80 border-white/80'}`}>
                            {isSelected && <CheckCircle className="h-3 w-3 text-white" />}
                          </div>
                          <div className="absolute top-2 right-2">
                            {output.type === 'video' ? <Play className="h-4 w-4 text-white drop-shadow" /> : <ImageIcon className="h-4 w-4 text-white drop-shadow" />}
                          </div>
                          {/* Open in new tab button - appears on hover */}
                          <button
                            className="absolute bottom-2 right-2 p-1.5 bg-black/60 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
                            onClick={(e) => { e.stopPropagation(); window.open(output.url, '_blank') }}
                            title="Open in new tab (or double-click)"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 text-white">
                              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                              <polyline points="15 3 21 3 21 9"></polyline>
                              <line x1="10" y1="14" x2="21" y2="3"></line>
                            </svg>
                          </button>
                        </div>
                      )
                    })}
                  </div>
                  <HoverPreview output={hoverOutput} position={hoverPosition} />
                </>
              ) : <p className="text-sm text-muted-foreground">No outputs</p>}
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
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [displayCount, setDisplayCount] = useState(PAGE_SIZE)
  const [restartState, setRestartState] = useState<'idle' | 'restarting' | 'done'>('idle')
  const [sortBy, setSortBy] = useState('newest')

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Query params - fetch more than displayed to enable smooth "load more"
  const queryParams = useMemo(() => ({
    favorites: demoMode || undefined,
    hidden: showHidden || undefined,
    tag: tagFilter || undefined,
    status: statusFilter || undefined,
    search: debouncedSearch || undefined,
    limit: displayCount,
    offset: 0,
  }), [demoMode, showHidden, tagFilter, statusFilter, debouncedSearch, displayCount])
  const { data, isLoading, isFetching, refetch } = usePipelines(queryParams)
  const rawPipelines = data?.pipelines || []
  const total = data?.total || 0

  // Sort pipelines client-side
  const pipelines = useMemo(() => {
    const sorted = [...rawPipelines]
    switch (sortBy) {
      case 'oldest':
        sorted.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        break
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'cost_high':
        sorted.sort((a, b) => (b.total_cost || 0) - (a.total_cost || 0))
        break
      case 'cost_low':
        sorted.sort((a, b) => (a.total_cost || 0) - (b.total_cost || 0))
        break
      case 'newest':
      default:
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        break
    }
    return sorted
  }, [rawPipelines, sortBy])
  // Reset display count when filters change (intentional - resets pagination on filter change)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisplayCount(PAGE_SIZE)
  }, [demoMode, showHidden, tagFilter, statusFilter, debouncedSearch])
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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isFetching} title="Refresh">
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            disabled={restartState === 'restarting'}
            onClick={async () => {
              setRestartState('restarting')
              try {
                await fetch('/api/pipelines/restart', { method: 'POST' })
                // Wait for server to restart
                await new Promise(r => setTimeout(r, 2000))
                // Check if server is back
                let retries = 0
                while (retries < 10) {
                  try {
                    const res = await fetch('/api/health')
                    if (res.ok) break
                  } catch { /* server still down */ }
                  await new Promise(r => setTimeout(r, 500))
                  retries++
                }
                setRestartState('done')
                setTimeout(() => setRestartState('idle'), 2000)
                refetch()
              } catch {
                setRestartState('idle')
              }
            }}
          >
            {restartState === 'restarting' ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Restarting...</>
            ) : restartState === 'done' ? (
              <><CheckCircle className="h-4 w-4" /> Restarted!</>
            ) : (
              <><RotateCcw className="h-4 w-4" /> Restart</>
            )}
          </Button>
        </div>
      </div>

      {/* Filters Row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-[300px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-8 h-9"
          />
          {searchInput && (
            <button
              onClick={() => setSearchInput('')}
              className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* View toggles */}
        <div className="flex items-center gap-1 border rounded-md p-1">
          <Button variant={demoMode ? 'default' : 'ghost'} size="sm" onClick={() => setDemoMode(!demoMode)} className="h-7 gap-1 px-2" title="Show only favorited jobs">
            <Star className={`h-3.5 w-3.5 ${demoMode ? 'fill-current' : ''}`} />
            <span className="hidden sm:inline">Favorites</span>
          </Button>
          <Button variant={showHidden ? 'secondary' : 'ghost'} size="sm" onClick={() => setShowHidden(!showHidden)} className="h-7 gap-1 px-2">
            {showHidden ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">Hidden</span>
          </Button>
        </div>

        {/* Filters */}
        <Select options={[{ value: '', label: 'All Tags' }, ...QUICK_TAGS.map(t => ({ value: t, label: t }))]} value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} />
        <Select options={STATUS_OPTIONS} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
        <Select options={SORT_OPTIONS} value={sortBy} onChange={(e) => setSortBy(e.target.value)} />

        {/* Count */}
        <span className="text-sm text-muted-foreground ml-auto">
          {pipelines.length}{total > pipelines.length ? ` of ${total}` : ''} jobs
        </span>
      </div>

      {/* Jobs List */}
      <div className="space-y-3">
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
            <p className="text-sm text-muted-foreground text-center py-12 border rounded-lg">
              No jobs found. Go to Playground to create one.
            </p>
          )}
      </div>
    </div>
  )
}

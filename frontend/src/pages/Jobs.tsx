import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { Select } from '@/components/ui/select'
import { Video, Image as ImageIcon, CheckCircle, XCircle, Clock, ExternalLink, RefreshCw, Layers, Play, Download, Star, EyeOff, Eye, X, Plus, ChevronDown, ChevronUp, Info } from 'lucide-react'

interface PipelineStep {
  id: number
  step_type: string
  status: string
  config: { model?: string; resolution?: string; duration_sec?: number; quality?: string }
  inputs: { prompts?: string[]; image_urls?: string[] } | null
  outputs: { items?: { url: string; type: string; prompt?: string }[] } | null
  cost_actual: number | null
  error_message: string | null
}

interface Pipeline {
  id: number
  name: string
  status: string
  created_at: string
  steps: PipelineStep[]
  tags?: string[]
  is_favorite?: boolean
  is_hidden?: boolean
  description?: string
}

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

// Hover preview component for outputs
function OutputPreview({ output, position }: { output: { url: string; type: 'image' | 'video'; prompt?: string } | null; position: { x: number; y: number } }) {
  if (!output) return null

  const previewWidth = 300
  const previewHeight = 500
  const padding = 20

  let left = position.x + padding
  let top = position.y - previewHeight / 2

  if (left + previewWidth > window.innerWidth - padding) {
    left = position.x - previewWidth - padding
  }
  if (top < padding) top = padding
  if (top + previewHeight > window.innerHeight - padding) {
    top = window.innerHeight - previewHeight - padding
  }

  return (
    <div className="fixed z-50 pointer-events-none" style={{ left, top }}>
      <div className="bg-black/90 rounded-lg shadow-2xl overflow-hidden border border-white/20">
        {output.type === 'video' ? (
          <video src={output.url} className="w-[300px] h-auto max-h-[500px] object-contain" autoPlay muted loop playsInline />
        ) : (
          <img src={output.url} alt="" className="w-[300px] h-auto max-h-[500px] object-contain" />
        )}
        {output.prompt && (
          <div className="p-2 text-xs text-white/80 max-w-[300px] truncate">{output.prompt}</div>
        )}
      </div>
    </div>
  )
}

const PAGE_SIZE = 20

export function Jobs() {
  const [statusFilter, setStatusFilter] = useState('')
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [pipelinesLoading, setPipelinesLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [total, setTotal] = useState(0)
  const [selectedOutputs, setSelectedOutputs] = useState<Set<string>>(new Set())
  const [expandedPipelines, setExpandedPipelines] = useState<Set<number>>(new Set())
  const [expandedOutputs, setExpandedOutputs] = useState<Set<number>>(new Set())

  // Hover preview state
  const [hoverOutput, setHoverOutput] = useState<{ url: string; type: 'image' | 'video'; prompt?: string } | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  const hoverTimeoutRef = useRef<number | null>(null)

  // Categorization state
  const [demoMode, setDemoMode] = useState(() => localStorage.getItem('demoMode') === 'true')
  const [showHidden, setShowHidden] = useState(false)
  const [tagFilter, setTagFilter] = useState('')
  const [editingTagsId, setEditingTagsId] = useState<number | null>(null)
  const [newTagInput, setNewTagInput] = useState('')

  const toggleExpanded = (id: number) => {
    const newSet = new Set(expandedPipelines)
    if (newSet.has(id)) newSet.delete(id)
    else newSet.add(id)
    setExpandedPipelines(newSet)
  }

  const toggleOutputs = (id: number) => {
    const newSet = new Set(expandedOutputs)
    if (newSet.has(id)) newSet.delete(id)
    else newSet.add(id)
    setExpandedOutputs(newSet)
  }

  const fetchPipelines = async (offset = 0, append = false) => {
    if (append) {
      setLoadingMore(true)
    } else {
      setPipelinesLoading(true)
    }
    try {
      const params = new URLSearchParams()
      if (demoMode) params.set('favorites', 'true')
      if (showHidden) params.set('hidden', 'true')
      if (tagFilter) params.set('tag', tagFilter)
      params.set('limit', PAGE_SIZE.toString())
      params.set('offset', offset.toString())

      const res = await fetch(`/api/pipelines?${params}`)
      if (res.ok) {
        const data = await res.json()
        const newPipelines = data.pipelines || []
        if (append) {
          setPipelines(prev => [...prev, ...newPipelines])
        } else {
          setPipelines(newPipelines)
        }
        setTotal(data.total || newPipelines.length)
        setHasMore(offset + newPipelines.length < (data.total || newPipelines.length))
      }
    } catch (error) {
      console.error('Failed to fetch pipelines:', error)
    } finally {
      setPipelinesLoading(false)
      setLoadingMore(false)
    }
  }

  const loadMore = () => {
    if (!loadingMore && hasMore) {
      fetchPipelines(pipelines.length, true)
    }
  }

  useEffect(() => {
    setPipelines([])
    setHasMore(true)
    fetchPipelines(0, false)
  }, [demoMode, showHidden, tagFilter])

  // Hover handlers
  const handleOutputHover = (output: { url: string; type: 'image' | 'video'; prompt?: string }, e: React.MouseEvent) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    hoverTimeoutRef.current = window.setTimeout(() => {
      setHoverOutput(output)
      setHoverPosition({ x: e.clientX, y: e.clientY })
    }, 300)
  }

  const handleOutputMove = (e: React.MouseEvent) => {
    if (hoverOutput) setHoverPosition({ x: e.clientX, y: e.clientY })
  }

  const handleOutputLeave = () => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
    setHoverOutput(null)
  }

  useEffect(() => {
    localStorage.setItem('demoMode', demoMode.toString())
  }, [demoMode])

  const toggleFavorite = async (id: number) => {
    try {
      await fetch(`/api/pipelines/${id}/favorite`, { method: 'PUT' })
      fetchPipelines()
    } catch (error) {
      console.error('Failed to toggle favorite:', error)
    }
  }

  const toggleHidden = async (id: number) => {
    try {
      await fetch(`/api/pipelines/${id}/hide`, { method: 'PUT' })
      fetchPipelines()
    } catch (error) {
      console.error('Failed to toggle hidden:', error)
    }
  }

  const updateTags = async (id: number, tags: string[]) => {
    try {
      await fetch(`/api/pipelines/${id}/tags`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(tags),
      })
      fetchPipelines()
    } catch (error) {
      console.error('Failed to update tags:', error)
    }
  }

  const addTag = async (id: number, tag: string) => {
    const pipeline = pipelines.find(p => p.id === id)
    if (!pipeline) return
    const currentTags = pipeline.tags || []
    if (!currentTags.includes(tag)) {
      await updateTags(id, [...currentTags, tag])
    }
    setNewTagInput('')
  }

  const removeTag = async (id: number, tag: string) => {
    const pipeline = pipelines.find(p => p.id === id)
    if (!pipeline) return
    const currentTags = pipeline.tags || []
    await updateTags(id, currentTags.filter(t => t !== tag))
  }

  // Simplified - Pipeline view only (Video/Image Jobs were for legacy API)

  const getOutputs = (steps: PipelineStep[]) => {
    const outputs: { url: string; type: 'image' | 'video'; prompt?: string }[] = []
    for (const step of steps) {
      if (step.outputs?.items) {
        for (const item of step.outputs.items) {
          outputs.push({ url: item.url, type: item.type as 'image' | 'video', prompt: item.prompt })
        }
      }
    }
    return outputs
  }

  // Get unique model configs used in pipeline (model + resolution + duration + quality)
  const getModelConfigs = (steps: PipelineStep[]) => {
    const configs: { model: string; resolution?: string; duration?: number; quality?: string; type: string; prompts: string[] }[] = []
    const seen = new Set<string>()
    for (const step of steps) {
      if (step.config?.model) {
        const key = `${step.step_type}-${step.config.model}-${step.config.resolution || ''}-${step.config.duration_sec || ''}-${step.config.quality || ''}`
        if (!seen.has(key)) {
          seen.add(key)
          configs.push({
            model: step.config.model,
            resolution: step.config.resolution,
            duration: step.config.duration_sec,
            quality: step.config.quality,
            type: step.step_type,
            prompts: step.inputs?.prompts || [],
          })
        }
      }
    }
    return configs
  }

  // Get all prompts from pipeline steps
  const getPrompts = (steps: PipelineStep[]) => {
    const prompts: string[] = []
    for (const step of steps) {
      if (step.inputs?.prompts) {
        prompts.push(...step.inputs.prompts)
      }
    }
    return [...new Set(prompts)] // unique prompts
  }

  // Get step details for display
  const getStepDetails = (steps: PipelineStep[]) => {
    return steps.map(step => ({
      type: step.step_type,
      model: step.config?.model || 'unknown',
      resolution: step.config?.resolution,
      duration: step.config?.duration_sec,
      prompts: step.inputs?.prompts || [],
      outputCount: step.outputs?.items?.length || 0,
      status: step.status,
      cost: step.cost_actual,
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">All Jobs</h1>
          <p className="text-muted-foreground">
            View and manage all your generation jobs
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Demo Mode Toggle */}
          <Button
            variant={demoMode ? 'default' : 'outline'}
            size="sm"
            onClick={() => setDemoMode(!demoMode)}
            className="gap-1"
          >
            <Star className={`h-4 w-4 ${demoMode ? 'fill-current' : ''}`} />
            Demo Mode
          </Button>

          {/* Show Hidden Toggle */}
          <Button
            variant={showHidden ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => setShowHidden(!showHidden)}
            className="gap-1"
          >
            {showHidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {showHidden ? 'Showing Hidden' : 'Hidden'}
          </Button>

          {/* Tag Filter */}
          <Select
            options={[
              { value: '', label: 'All Tags' },
              ...QUICK_TAGS.map(t => ({ value: t, label: t }))
            ]}
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
          />

          <div className="w-36">
            <Select
              options={STATUS_OPTIONS}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            />
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => {
              fetchPipelines()
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5" />
            All Jobs ({pipelines.length}{total > pipelines.length ? ` / ${total}` : ''})
          </CardTitle>
          <CardDescription>Your generated photos and videos from the Playground</CardDescription>
        </CardHeader>
            <CardContent>
              {pipelinesLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : pipelines.length > 0 ? (
                <div className="space-y-4">
                  {pipelines.map((pipeline) => {
                    const outputs = getOutputs(pipeline.steps)
                    const pipelineTags = pipeline.tags || []
                    const modelConfigs = getModelConfigs(pipeline.steps)
                    const prompts = getPrompts(pipeline.steps)
                    const isExpanded = expandedPipelines.has(pipeline.id)
                    const stepDetails = getStepDetails(pipeline.steps)
                    return (
                      <div key={pipeline.id} className={`border rounded-lg p-4 ${pipeline.is_hidden ? 'opacity-60' : ''}`}>
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-3">
                            {/* Favorite button */}
                            <button
                              onClick={() => toggleFavorite(pipeline.id)}
                              className="p-1 hover:bg-muted rounded"
                              title={pipeline.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                            >
                              <Star className={`h-5 w-5 ${pipeline.is_favorite ? 'fill-yellow-400 text-yellow-400' : 'text-muted-foreground'}`} />
                            </button>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <p className="font-medium">{pipeline.name}</p>
                                {/* Model badges with config details + prompt tooltip */}
                                {modelConfigs.map((cfg, idx) => (
                                  <span
                                    key={`${cfg.model}-${idx}`}
                                    className="px-1.5 py-0.5 text-[10px] font-medium bg-primary/10 text-primary rounded cursor-help relative group/badge"
                                    title={cfg.prompts.length > 0 ? cfg.prompts.join('\n\n') : undefined}
                                  >
                                    {cfg.model}
                                    {cfg.quality && ` • ${cfg.quality}`}
                                    {cfg.resolution && ` • ${cfg.resolution}`}
                                    {cfg.duration && ` • ${cfg.duration}s`}
                                    {/* Prompt tooltip on hover */}
                                    {cfg.prompts.length > 0 && (
                                      <div className="absolute left-0 top-full mt-1 z-50 hidden group-hover/badge:block">
                                        <div className="bg-black/95 text-white text-xs p-2 rounded shadow-lg max-w-xs whitespace-pre-wrap">
                                          {cfg.prompts.map((p, i) => (
                                            <p key={i} className="mb-1 last:mb-0">{p.length > 100 ? p.slice(0, 100) + '...' : p}</p>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </span>
                                ))}
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {formatDate(pipeline.created_at)}
                              </p>
                              {/* Prompt preview */}
                              {prompts.length > 0 && (
                                <p className="text-xs text-muted-foreground/80 italic truncate max-w-md" title={prompts[0]}>
                                  "{prompts[0].length > 60 ? prompts[0].slice(0, 60) + '...' : prompts[0]}"
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {/* Details toggle */}
                            {prompts.length > 0 && (
                              <button
                                onClick={() => toggleExpanded(pipeline.id)}
                                className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                                title="Show details"
                              >
                                {isExpanded ? <ChevronUp className="h-4 w-4" /> : <Info className="h-4 w-4" />}
                              </button>
                            )}
                            {/* Hide button */}
                            <button
                              onClick={() => toggleHidden(pipeline.id)}
                              className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                              title={pipeline.is_hidden ? 'Show' : 'Hide'}
                            >
                              {pipeline.is_hidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                            </button>
                            {getStatusBadge(pipeline.status)}
                          </div>
                        </div>

                        {/* Expandable details section */}
                        {isExpanded && (
                          <div className="mb-3 p-3 bg-muted/50 rounded-lg text-sm space-y-2">
                            {stepDetails.map((step, idx) => (
                              <div key={idx} className="space-y-1">
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <span className="font-medium uppercase">{step.type}</span>
                                  <span>•</span>
                                  <span>{step.model}</span>
                                  {step.resolution && <><span>•</span><span>{step.resolution}</span></>}
                                  {step.duration && <><span>•</span><span>{step.duration}s</span></>}
                                  {step.cost && <><span>•</span><span className="text-green-500">${step.cost.toFixed(2)}</span></>}
                                </div>
                                {step.prompts.length > 0 && (
                                  <div className="pl-2 border-l-2 border-muted-foreground/20">
                                    {step.prompts.map((prompt, pIdx) => (
                                      <p key={pIdx} className="text-xs text-muted-foreground italic truncate" title={prompt}>
                                        "{prompt.length > 80 ? prompt.slice(0, 80) + '...' : prompt}"
                                      </p>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Tags section */}
                        <div className="flex flex-wrap items-center gap-1 mb-2">
                          {pipelineTags.map(tag => (
                            <span
                              key={tag}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${TAG_COLORS[tag] || 'bg-muted text-muted-foreground border-border'}`}
                            >
                              {tag}
                              <button
                                onClick={() => removeTag(pipeline.id, tag)}
                                className="hover:text-destructive"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </span>
                          ))}
                          {editingTagsId === pipeline.id ? (
                            <div className="flex items-center gap-1">
                              <input
                                type="text"
                                value={newTagInput}
                                onChange={(e) => setNewTagInput(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && newTagInput) {
                                    addTag(pipeline.id, newTagInput)
                                    setEditingTagsId(null)
                                  } else if (e.key === 'Escape') {
                                    setEditingTagsId(null)
                                    setNewTagInput('')
                                  }
                                }}
                                className="w-20 px-1 py-0.5 text-xs border rounded bg-background"
                                placeholder="tag..."
                                autoFocus
                              />
                              <div className="flex gap-0.5">
                                {QUICK_TAGS.filter(t => !pipelineTags.includes(t)).slice(0, 3).map(t => (
                                  <button
                                    key={t}
                                    onClick={() => { addTag(pipeline.id, t); setEditingTagsId(null) }}
                                    className={`px-1.5 py-0.5 text-xs rounded border ${TAG_COLORS[t] || 'bg-muted'} hover:opacity-80`}
                                  >
                                    {t}
                                  </button>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setEditingTagsId(pipeline.id)}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs text-muted-foreground hover:bg-muted"
                            >
                              <Plus className="h-3 w-3" />
                              tag
                            </button>
                          )}
                        </div>

                        <div className="flex flex-wrap gap-2 mb-3">
                          {pipeline.steps.map((step) => (
                            <Badge key={step.id} variant="outline" className="gap-1">
                              {step.step_type === 'i2v' && <Video className="h-3 w-3" />}
                              {step.step_type === 'i2i' && <ImageIcon className="h-3 w-3" />}
                              {step.step_type} - {step.status}
                              {step.cost_actual && ` ($${step.cost_actual.toFixed(2)})`}
                            </Badge>
                          ))}
                        </div>
                        {pipeline.steps.some(s => s.error_message) && (
                          <p className="text-xs text-destructive mb-2">
                            {pipeline.steps.find(s => s.error_message)?.error_message}
                          </p>
                        )}
                        {outputs.length > 0 && (() => {
                          const pipelineSelected = outputs.filter(o => selectedOutputs.has(o.url))
                          const isOutputsExpanded = expandedOutputs.has(pipeline.id)
                          return (
                          <div className="space-y-2">
                            {/* Collapsed: just show count and expand button */}
                            <button
                              onClick={() => toggleOutputs(pipeline.id)}
                              className="flex items-center gap-2 text-sm font-medium hover:text-primary transition-colors"
                            >
                              {isOutputsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                              Outputs ({outputs.length})
                              {pipelineSelected.length > 0 && (
                                <span className="text-primary">• {pipelineSelected.length} selected</span>
                              )}
                            </button>

                            {/* Expanded: show full grid */}
                            {isOutputsExpanded && (
                              <>
                                <div className="flex items-center justify-end gap-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                      const allSelected = outputs.every(o => selectedOutputs.has(o.url))
                                      const newSet = new Set(selectedOutputs)
                                      outputs.forEach(o => {
                                        if (allSelected) newSet.delete(o.url)
                                        else newSet.add(o.url)
                                      })
                                      setSelectedOutputs(newSet)
                                    }}
                                  >
                                    {outputs.every(o => selectedOutputs.has(o.url)) ? 'Deselect All' : 'Select All'}
                                  </Button>
                                  <Button
                                    variant="default"
                                    size="sm"
                                    disabled={pipelineSelected.length === 0}
                                    onClick={() => {
                                      pipelineSelected.forEach((output, i) => {
                                        setTimeout(() => {
                                          const a = document.createElement('a')
                                          a.href = output.url
                                          a.download = `output-${pipeline.id}-${i + 1}.${output.type === 'video' ? 'mp4' : 'png'}`
                                          a.target = '_blank'
                                          a.click()
                                        }, i * 200)
                                      })
                                    }}
                                  >
                                    <Download className="h-4 w-4 mr-1" />
                                    Download {pipelineSelected.length > 0 ? `(${pipelineSelected.length})` : 'Selected'}
                                  </Button>
                                </div>
                                <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
                                  {outputs.map((output, idx) => {
                                    const isSelected = selectedOutputs.has(output.url)
                                    return (
                                    <div
                                      key={idx}
                                      className={`relative aspect-[9/16] bg-muted rounded-lg overflow-hidden group cursor-pointer ${isSelected ? 'ring-2 ring-primary' : ''}`}
                                      onClick={() => {
                                        const newSet = new Set(selectedOutputs)
                                        if (isSelected) newSet.delete(output.url)
                                        else newSet.add(output.url)
                                        setSelectedOutputs(newSet)
                                      }}
                                      onMouseEnter={(e) => handleOutputHover(output, e)}
                                      onMouseMove={handleOutputMove}
                                      onMouseLeave={handleOutputLeave}
                                    >
                                      {output.type === 'video' ? (
                                        <video
                                          src={output.url}
                                          className="w-full h-full object-cover"
                                          muted
                                          playsInline
                                          preload="none"
                                          onMouseEnter={(e) => e.currentTarget.play()}
                                          onMouseLeave={(e) => {
                                            e.currentTarget.pause()
                                            e.currentTarget.currentTime = 0
                                          }}
                                        />
                                      ) : (
                                        <img src={output.url} alt="" className="w-full h-full object-cover" loading="lazy" />
                                      )}
                                      {/* Selection checkbox */}
                                      <div className={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${isSelected ? 'bg-primary border-primary' : 'bg-white/80 border-white/80'}`}>
                                        {isSelected && <CheckCircle className="h-3 w-3 text-white" />}
                                      </div>
                                      {/* Type indicator */}
                                      <div className="absolute top-2 right-2">
                                        {output.type === 'video' ? (
                                          <Play className="h-4 w-4 text-white drop-shadow" />
                                        ) : (
                                          <ImageIcon className="h-4 w-4 text-white drop-shadow" />
                                        )}
                                      </div>
                                      {/* Quick actions on hover */}
                                      <div className="absolute bottom-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <a
                                          href={output.url}
                                          download={`output-${idx + 1}.${output.type === 'video' ? 'mp4' : 'png'}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          onClick={(e) => e.stopPropagation()}
                                          className="p-1.5 bg-black/70 hover:bg-black/90 rounded"
                                          title="Download"
                                        >
                                          <Download className="h-3 w-3 text-white" />
                                        </a>
                                        <a
                                          href={output.url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          onClick={(e) => e.stopPropagation()}
                                          className="p-1.5 bg-black/70 hover:bg-black/90 rounded"
                                          title="Open"
                                        >
                                          <ExternalLink className="h-3 w-3 text-white" />
                                        </a>
                                      </div>
                                    </div>
                                  )})}
                                </div>
                              </>
                            )}
                          </div>
                        )})()}
                      </div>
                    )
                  })}

                  {/* Load More button */}
                  {hasMore && (
                    <div className="text-center pt-4">
                      <Button
                        variant="outline"
                        onClick={loadMore}
                        disabled={loadingMore}
                      >
                        {loadingMore ? (
                          <>
                            <Spinner size="sm" className="mr-2" />
                            Loading...
                          </>
                        ) : (
                          `Load More (${total - pipelines.length} remaining)`
                        )}
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

      {/* Hover preview popup */}
      <OutputPreview output={hoverOutput} position={hoverPosition} />
    </div>
  )
}

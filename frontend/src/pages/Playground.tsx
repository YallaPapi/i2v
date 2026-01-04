import { useState, useCallback, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ImageUploadZone,
  PromptInput,
  ModelSelector,
  SetModeModal,
  CostPreview,
  ProgressMonitor,
  OutputGallery,
  MultiPromptInput,
  BulkPreview,
  BulkProgress,
  BulkResults,
} from '@/components/pipeline'
import type { SetModeConfig, CostEstimate, OutputItem, BulkCostEstimate, BulkStep, SourceGroup } from '@/components/pipeline'
import { Textarea } from '@/components/ui/textarea'
import { Layers, Image, Video, Wand2, Play, Sparkles, Grid3X3, Loader2, GalleryHorizontal } from 'lucide-react'

type GenerationMode = 'i2i' | 'i2v' | 'pipeline' | 'bulk' | 'carousel'

interface UploadedImage {
  id: string
  url: string
  preview: string
  name: string
  source: 'upload' | 'url'
}

export function Playground() {
  // Mode selection - persisted to localStorage
  const [mode, setMode] = useState<GenerationMode>(() => {
    const saved = localStorage.getItem('playground-default-mode')
    return (saved as GenerationMode) || 'bulk'
  })
  const [defaultMode, setDefaultMode] = useState<GenerationMode>(() => {
    const saved = localStorage.getItem('playground-default-mode')
    return (saved as GenerationMode) || 'bulk'
  })

  // Save default mode to localStorage
  const handleSetDefaultMode = (newMode: GenerationMode) => {
    setDefaultMode(newMode)
    localStorage.setItem('playground-default-mode', newMode)
  }

  // Images
  const [images, setImages] = useState<UploadedImage[]>([])

  // Prompts
  const [prompt, setPrompt] = useState('')
  const [enhancedPrompts, setEnhancedPrompts] = useState<string[]>([])

  // I2I Settings
  const [i2iModel, setI2iModel] = useState('gpt-image-1.5')
  const [i2iAspectRatio, setI2iAspectRatio] = useState('9:16')
  const [i2iQuality, setI2iQuality] = useState<'low' | 'medium' | 'high'>('high')
  const [setModeOpen, setSetModeOpen] = useState(false)
  const [setModeConfig, setSetModeConfig] = useState<SetModeConfig>({
    enabled: false,
    variations: [],
    countPerVariation: 1,
  })

  // I2V Settings
  const [i2vModel, setI2vModel] = useState('kling')
  const [resolution, setResolution] = useState('1080p')
  const [duration, setDuration] = useState('5')

  // Pipeline State
  const [isGenerating, setIsGenerating] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<'pending' | 'running' | 'paused' | 'completed' | 'failed'>('pending')
  const [pipelineSteps, setPipelineSteps] = useState<Array<{
    id: number
    stepType: string
    stepOrder: number
    status: 'pending' | 'running' | 'review' | 'completed' | 'failed'
    progressPct?: number
    outputsCount?: number
  }>>([])

  // Outputs
  const [outputs, setOutputs] = useState<OutputItem[]>([])

  // Cost
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null)

  // Bulk Mode State
  const [bulkMode, setBulkMode] = useState<'photos' | 'videos' | 'both'>('videos')
  const [bulkI2iPrompts, setBulkI2iPrompts] = useState<string[]>([])
  const [bulkI2vPrompts, setBulkI2vPrompts] = useState<string[]>([])
  const [bulkI2iNegativePrompt, setBulkI2iNegativePrompt] = useState('')
  const [bulkI2vNegativePrompt, setBulkI2vNegativePrompt] = useState('')
  const [isExpandingI2i, setIsExpandingI2i] = useState(false)
  const [isExpandingI2v, setIsExpandingI2v] = useState(false)
  // Prompt enhancement settings
  const [enhanceMode, setEnhanceMode] = useState<'location' | 'outfit' | 'expression' | 'rewrite' | 'random'>('random')
  const [enhanceCount, setEnhanceCount] = useState(3)
  const [bulkCostEstimate, setBulkCostEstimate] = useState<BulkCostEstimate | null>(null)
  const [bulkPipelineId, setBulkPipelineId] = useState<number | null>(null)
  const [bulkSteps, setBulkSteps] = useState<BulkStep[]>([])
  const [bulkGroups, setBulkGroups] = useState<SourceGroup[]>([])
  const [bulkTotals, setBulkTotals] = useState({ source_images: 0, i2i_generated: 0, i2v_generated: 0, total_cost: 0 })

  // Carousel Mode State - each prompt = one slide in the story
  const [carouselPrompts, setCarouselPrompts] = useState<string[]>([])
  const [carouselNegativePrompt, setCarouselNegativePrompt] = useState('')

  // Handlers
  const handleEnhancePrompt = async (
    enhanceMode: 'quick_improve' | 'category_based' | 'raw' = 'quick_improve',
    categories: string[] = []
  ): Promise<string[]> => {
    try {
      const response = await fetch('/api/pipelines/prompts/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompts: [prompt],
          count: 3,
          target: mode === 'i2v' ? 'i2v' : 'i2i',
          style: 'photorealistic',
          mode: enhanceMode,
          categories: categories.length > 0 ? categories : undefined,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        const allEnhanced = data.enhanced_prompts.flat()
        setEnhancedPrompts(allEnhanced)
        return allEnhanced
      }
    } catch (error) {
      console.error('Failed to enhance prompt:', error)
    }
    return []
  }

  // Bulk prompt expansion - generates variations based on selected mode
  const handleExpandBulkPrompts = async (type: 'i2i' | 'i2v') => {
    const prompts = type === 'i2i' ? bulkI2iPrompts : bulkI2vPrompts
    if (prompts.length === 0) return

    if (type === 'i2i') setIsExpandingI2i(true)
    else setIsExpandingI2v(true)

    // Map enhance mode to API categories
    const modeToCategories: Record<string, string[]> = {
      location: ['background'],
      outfit: ['outfit'],
      expression: ['facial_expression'],
      rewrite: [], // quick_improve mode, no specific categories
      random: ['lighting', 'outfit', 'pose', 'background', 'style'],
    }

    try {
      const response = await fetch('/api/pipelines/prompts/enhance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompts,
          count: enhanceCount,
          target: type,
          style: 'photorealistic',
          mode: enhanceMode === 'rewrite' ? 'quick_improve' : 'category_based',
          categories: modeToCategories[enhanceMode] || [],
        }),
      })

      if (response.ok) {
        const data = await response.json()
        const expanded = data.enhanced_prompts.flat()
        // Add expanded prompts to existing ones (deduplicated)
        const combined = [...new Set([...prompts, ...expanded])]
        if (type === 'i2i') setBulkI2iPrompts(combined)
        else setBulkI2vPrompts(combined)
      }
    } catch (error) {
      console.error('Failed to expand prompts:', error)
    } finally {
      if (type === 'i2i') setIsExpandingI2i(false)
      else setIsExpandingI2v(false)
    }
  }

  const calculateCost = useCallback(async () => {
    const steps = []

    if (mode === 'pipeline' && enhancedPrompts.length === 0) {
      steps.push({
        step_type: 'prompt_enhance',
        step_order: 0,
        config: {
          input_prompts: [prompt],
          variations_per_prompt: 5,
        },
      })
    }

    if (mode === 'i2i' || mode === 'pipeline') {
      steps.push({
        step_type: 'i2i',
        step_order: steps.length,
        config: {
          model: i2iModel,
          images_per_prompt: 1,
          set_mode: setModeConfig,
          quality: 'high',
        },
      })
    }

    if (mode === 'i2v' || mode === 'pipeline') {
      steps.push({
        step_type: 'i2v',
        step_order: steps.length,
        config: {
          model: i2vModel,
          videos_per_image: 1,
          resolution,
          duration_sec: parseInt(duration),
        },
      })
    }

    if (steps.length === 0) return

    try {
      const response = await fetch('/api/pipelines/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps }),
      })

      if (response.ok) {
        const data = await response.json()
        setCostEstimate({
          breakdown: data.breakdown.map((b: { step_type: string; step_order: number; model?: string; unit_count: number; unit_price: number; total: number }) => ({
            stepType: b.step_type,
            stepOrder: b.step_order,
            model: b.model,
            unitCount: b.unit_count,
            unitPrice: b.unit_price,
            total: b.total,
          })),
          total: data.total,
          currency: data.currency,
        })
      }
    } catch (error) {
      console.error('Failed to estimate cost:', error)
    }
  }, [mode, prompt, enhancedPrompts, i2iModel, i2vModel, resolution, duration, setModeConfig])

  // Recalculate cost when settings change
  useEffect(() => {
    if (images.length > 0 && prompt.trim()) {
      calculateCost()
    }
  }, [calculateCost, images.length, prompt])

  // Bulk cost estimation
  const calculateBulkCost = useCallback(async () => {
    // For photos-only mode, we need photo prompts
    // For videos-only mode, we need video prompts
    // For both mode, we need video prompts (photo prompts optional)
    const needsPhotoPrompts = bulkMode === 'photos' || bulkMode === 'both'
    const needsVideoPrompts = bulkMode === 'videos' || bulkMode === 'both'

    if (images.length === 0) {
      setBulkCostEstimate(null)
      return
    }
    if (needsPhotoPrompts && bulkMode === 'photos' && bulkI2iPrompts.length === 0) {
      setBulkCostEstimate(null)
      return
    }
    if (needsVideoPrompts && bulkI2vPrompts.length === 0) {
      setBulkCostEstimate(null)
      return
    }

    try {
      const response = await fetch('/api/pipelines/bulk/estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_images: images.map(img => img.url),
          i2i_config: (bulkMode === 'photos' || bulkMode === 'both') && bulkI2iPrompts.length > 0 ? {
            enabled: true,
            prompts: bulkI2iPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: 'high',
            negative_prompt: bulkI2iNegativePrompt || undefined,
          } : null,
          i2v_config: {
            prompts: bulkMode === 'photos' ? ['placeholder'] : bulkI2vPrompts,
            model: i2vModel,
            resolution,
            duration_sec: parseInt(duration),
            negative_prompt: bulkI2vNegativePrompt || undefined,
          },
        }),
      })

      if (response.ok) {
        const data = await response.json()
        // For photos-only mode, zero out the video costs
        if (bulkMode === 'photos') {
          data.breakdown.i2v_count = 0
          data.breakdown.i2v_total = 0
          data.breakdown.grand_total = data.breakdown.i2i_total
        }
        setBulkCostEstimate(data)
      }
    } catch (error) {
      console.error('Failed to estimate bulk cost:', error)
    }
  }, [images, bulkMode, bulkI2iPrompts, bulkI2iNegativePrompt, bulkI2vPrompts, bulkI2vNegativePrompt, i2iModel, i2iAspectRatio, i2vModel, resolution, duration])

  // Recalculate bulk cost when settings change
  useEffect(() => {
    if (mode === 'bulk') {
      calculateBulkCost()
    }
  }, [mode, calculateBulkCost])

  // Bulk generate handler
  const handleBulkGenerate = async () => {
    if (images.length === 0) return
    if (bulkMode === 'photos' && bulkI2iPrompts.length === 0) return
    if ((bulkMode === 'videos' || bulkMode === 'both') && bulkI2vPrompts.length === 0) return

    setIsGenerating(true)
    setPipelineStatus('running')
    setBulkGroups([])
    setBulkSteps([])

    // For photos-only mode, we'll handle it differently (no video generation)
    const includePhotos = bulkMode === 'photos' || bulkMode === 'both'
    const includeVideos = bulkMode === 'videos' || bulkMode === 'both'

    try {
      const response = await fetch('/api/pipelines/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Bulk ${bulkMode === 'photos' ? 'Photos' : bulkMode === 'videos' ? 'Videos' : 'Photos + Videos'} - ${new Date().toLocaleString()}`,
          source_images: images.map(img => img.url),
          i2i_config: includePhotos && bulkI2iPrompts.length > 0 ? {
            enabled: true,
            prompts: bulkI2iPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: 'high',
            negative_prompt: bulkI2iNegativePrompt || undefined,
          } : null,
          i2v_config: includeVideos ? {
            prompts: bulkI2vPrompts,
            model: i2vModel,
            resolution,
            duration_sec: parseInt(duration),
            negative_prompt: bulkI2vNegativePrompt || undefined,
          } : { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration) },
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        console.error('Bulk pipeline creation failed:', errorData)
        setPipelineStatus('failed')
        setIsGenerating(false)
        alert(`Failed to create pipeline: ${errorData.detail || 'Unknown error'}`)
        return
      }

      const data = await response.json()
      setBulkPipelineId(data.pipeline_id)

      // Poll for status
      const pollBulkStatus = async () => {
        const statusRes = await fetch(`/api/pipelines/bulk/${data.pipeline_id}`)
        if (statusRes.ok) {
          const statusData = await statusRes.json()
          setPipelineStatus(statusData.status)
          setBulkGroups(statusData.groups)
          setBulkTotals(statusData.totals)

          if (statusData.status === 'running') {
            setTimeout(pollBulkStatus, 2000)
          } else {
            setIsGenerating(false)
          }
        }
      }

      // Also poll the regular pipeline endpoint to get step statuses
      const pollSteps = async () => {
        const stepsRes = await fetch(`/api/pipelines/${data.pipeline_id}`)
        if (stepsRes.ok) {
          const stepsData = await stepsRes.json()
          setBulkSteps(stepsData.steps?.map((s: { id: number; step_type: string; status: string; inputs?: { source_image_index?: number } }) => ({
            id: s.id,
            step_type: s.step_type,
            status: s.status,
            source_index: s.inputs?.source_image_index,
          })) || [])

          if (stepsData.status === 'running') {
            setTimeout(pollSteps, 2000)
          }
        }
      }

      pollBulkStatus()
      pollSteps()
    } catch (error) {
      console.error('Bulk pipeline failed:', error)
      setPipelineStatus('failed')
      setIsGenerating(false)
    }
  }

  // Carousel generate handler - uses bulk i2i pipeline
  const handleCarouselGenerate = async () => {
    if (images.length === 0 || carouselPrompts.length === 0) return

    setIsGenerating(true)
    setPipelineStatus('running')
    setBulkGroups([])

    try {
      const response = await fetch('/api/pipelines/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Carousel - ${new Date().toLocaleString()}`,
          source_images: images.map(img => img.url),
          i2i_config: {
            enabled: true,
            prompts: carouselPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: 'high',
            negative_prompt: carouselNegativePrompt || undefined,
          },
          i2v_config: { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration) },
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setBulkPipelineId(data.pipeline_id)

        // Poll for status
        const pollStatus = async () => {
          const statusRes = await fetch(`/api/pipelines/bulk/${data.pipeline_id}`)
          if (statusRes.ok) {
            const statusData = await statusRes.json()
            setPipelineStatus(statusData.status)
            setBulkGroups(statusData.groups)

            if (statusData.status === 'running') {
              setTimeout(pollStatus, 2000)
            } else {
              setIsGenerating(false)
            }
          }
        }

        pollStatus()
      }
    } catch (error) {
      console.error('Carousel generation failed:', error)
      setPipelineStatus('failed')
      setIsGenerating(false)
    }
  }

  const handleGenerate = async () => {
    if (images.length === 0 || !prompt.trim()) return

    setIsGenerating(true)
    setPipelineStatus('running')

    // Build pipeline steps
    const steps = []
    let stepOrder = 0

    if (mode === 'pipeline') {
      steps.push({
        step_type: 'prompt_enhance',
        step_order: stepOrder++,
        config: {
          input_prompts: [prompt],
          variations_per_prompt: 5,
          target_type: 'i2i',
        },
        inputs: {},
      })
    }

    if (mode === 'i2i' || mode === 'pipeline') {
      steps.push({
        step_type: 'i2i',
        step_order: stepOrder++,
        config: {
          model: i2iModel,
          images_per_prompt: 1,
          set_mode: setModeConfig,
          aspect_ratio: '9:16',
          quality: 'high',
        },
        inputs: {
          image_urls: images.map(img => img.url),
          prompts: enhancedPrompts.length > 0 ? enhancedPrompts : [prompt],
        },
      })
    }

    if (mode === 'i2v' || mode === 'pipeline') {
      steps.push({
        step_type: 'i2v',
        step_order: stepOrder++,
        config: {
          model: i2vModel,
          videos_per_image: 1,
          resolution,
          duration_sec: parseInt(duration),
        },
        inputs: {
          image_urls: images.map(img => img.url),
          prompts: [prompt],
        },
      })
    }

    // Initialize pipeline steps for progress display
    setPipelineSteps(steps.map((s, i) => ({
      id: i,
      stepType: s.step_type,
      stepOrder: s.step_order,
      status: i === 0 ? 'running' : 'pending',
    })))

    try {
      // Create pipeline
      const response = await fetch('/api/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `${mode.toUpperCase()} - ${new Date().toLocaleString()}`,
          mode: 'auto',
          steps,
        }),
      })

      if (response.ok) {
        const pipeline = await response.json()

        // Start pipeline
        await fetch(`/api/pipelines/${pipeline.id}/run`, {
          method: 'POST',
        })

        // Poll for status (simplified - in production use WebSocket)
        const pollStatus = async () => {
          const statusRes = await fetch(`/api/pipelines/${pipeline.id}`)
          if (statusRes.ok) {
            const data = await statusRes.json()
            setPipelineStatus(data.status)

            if (data.steps) {
              setPipelineSteps(data.steps.map((s: { id: number; step_type: string; step_order: number; status: string; outputs?: { count?: number } }) => ({
                id: s.id,
                stepType: s.step_type,
                stepOrder: s.step_order,
                status: s.status,
                outputsCount: s.outputs?.count,
              })))

              // Collect outputs
              const allOutputs: OutputItem[] = []
              for (const step of data.steps) {
                if (step.outputs?.items) {
                  for (const item of step.outputs.items) {
                    allOutputs.push({
                      id: crypto.randomUUID(),
                      url: item.url,
                      type: item.type,
                      stepType: step.step_type,
                      model: step.config?.model,
                    })
                  }
                }
              }
              setOutputs(allOutputs)
            }

            if (data.status === 'running') {
              setTimeout(pollStatus, 2000)
            } else {
              setIsGenerating(false)
            }
          }
        }

        pollStatus()
      }
    } catch (error) {
      console.error('Pipeline failed:', error)
      setPipelineStatus('failed')
      setIsGenerating(false)
    }
  }

  const canGenerate = mode === 'bulk'
    ? images.length > 0 && !isGenerating && (
        (bulkMode === 'photos' && bulkI2iPrompts.length > 0) ||
        (bulkMode === 'videos' && bulkI2vPrompts.length > 0) ||
        (bulkMode === 'both' && bulkI2vPrompts.length > 0)
      )
    : mode === 'carousel'
      ? images.length > 0 && carouselPrompts.length > 0 && !isGenerating
      : images.length > 0 && prompt.trim() && !isGenerating

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <Wand2 className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Playground</h1>
                <p className="text-sm text-muted-foreground">Create images and videos with AI</p>
              </div>
            </div>

            {/* Mode Selector */}
            <Tabs value={mode} onValueChange={(v) => setMode(v as GenerationMode)}>
              <TabsList>
                <TabsTrigger value="i2i" className="gap-2">
                  <Image className="h-4 w-4" />
                  Edit Image
                </TabsTrigger>
                <TabsTrigger value="i2v" className="gap-2">
                  <Video className="h-4 w-4" />
                  Animate
                </TabsTrigger>
                <TabsTrigger value="pipeline" className="gap-2">
                  <Layers className="h-4 w-4" />
                  Full Pipeline
                </TabsTrigger>
                <TabsTrigger value="bulk" className="gap-2">
                  <Grid3X3 className="h-4 w-4" />
                  Bulk
                </TabsTrigger>
                <TabsTrigger value="carousel" className="gap-2">
                  <GalleryHorizontal className="h-4 w-4" />
                  Carousel
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <button
              type="button"
              onClick={() => handleSetDefaultMode(mode)}
              className={`text-xs px-2 py-1 rounded ${
                defaultMode === mode
                  ? 'text-primary bg-primary/10'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {defaultMode === mode ? '✓ Default' : 'Set as default'}
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Image Upload - shown in all modes */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {mode === 'bulk' ? (
                    <span className="text-lg">Step 1: Upload Your Photos</span>
                  ) : (
                    <>
                      <Image className="h-5 w-5" />
                      Source Images
                    </>
                  )}
                </CardTitle>
                <CardDescription>
                  {mode === 'bulk'
                    ? 'Add the photos you want to turn into videos. You can upload up to 10 photos.'
                    : 'Upload or paste URLs of images to transform'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ImageUploadZone
                  images={images}
                  onImagesChange={setImages}
                  multiple={true}
                  maxFiles={mode === 'bulk' ? 10 : 20}
                  disabled={isGenerating}
                />
              </CardContent>
            </Card>

            {/* Standard Mode: Single Prompt */}
            {mode !== 'bulk' && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5" />
                    Prompt
                  </CardTitle>
                  <CardDescription>
                    Describe what you want to create
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <PromptInput
                    value={prompt}
                    onChange={setPrompt}
                    onEnhance={handleEnhancePrompt}
                    enhancedPrompts={enhancedPrompts}
                    onSelectEnhanced={setPrompt}
                    placeholder={
                      mode === 'i2v'
                        ? "Describe the motion and camera movement..."
                        : "Describe the changes you want to make..."
                    }
                    disabled={isGenerating}
                    target={mode === 'i2v' ? 'i2v' : 'i2i'}
                  />
                </CardContent>
              </Card>
            )}

            {/* Bulk Mode: Multi-Prompt Inputs */}
            {mode === 'bulk' && (
              <>
                {/* What do you want to create? */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">What do you want to create?</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-3">
                      <button
                        type="button"
                        onClick={() => setBulkMode('photos')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          bulkMode === 'photos'
                            ? 'border-primary bg-primary/10'
                            : 'border-muted hover:border-muted-foreground/50'
                        }`}
                      >
                        <Image className="h-6 w-6 mb-2" />
                        <p className="font-medium">Just Photos</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Create multiple versions of your photos
                        </p>
                      </button>

                      <button
                        type="button"
                        onClick={() => setBulkMode('videos')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          bulkMode === 'videos'
                            ? 'border-primary bg-primary/10'
                            : 'border-muted hover:border-muted-foreground/50'
                        }`}
                      >
                        <Video className="h-6 w-6 mb-2" />
                        <p className="font-medium">Just Videos</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Turn your photos into videos
                        </p>
                      </button>

                      <button
                        type="button"
                        onClick={() => setBulkMode('both')}
                        className={`p-4 rounded-lg border-2 text-left transition-all ${
                          bulkMode === 'both'
                            ? 'border-primary bg-primary/10'
                            : 'border-muted hover:border-muted-foreground/50'
                        }`}
                      >
                        <Layers className="h-6 w-6 mb-2" />
                        <p className="font-medium">Photos + Videos</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          Create photo variations, then videos from each
                        </p>
                      </button>
                    </div>
                  </CardContent>
                </Card>

                {/* Photo descriptions - shown for 'photos' and 'both' modes */}
                {(bulkMode === 'photos' || bulkMode === 'both') && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center justify-between">
                        <span>Describe the photo variations you want</span>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handleExpandBulkPrompts('i2i')}
                          disabled={isGenerating || isExpandingI2i || bulkI2iPrompts.length === 0}
                        >
                          {isExpandingI2i ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Wand2 className="h-4 w-4 mr-1" />
                          )}
                          Expand prompts
                        </Button>
                      </CardTitle>
                      <CardDescription>
                        Write one description per line. Each one creates a new version of every photo you uploaded.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <MultiPromptInput
                        prompts={bulkI2iPrompts}
                        onPromptsChange={setBulkI2iPrompts}
                        label=""
                        placeholder="wearing a red dress&#10;in casual summer clothes&#10;with dramatic studio lighting&#10;smiling warmly"
                        disabled={isGenerating}
                      />

                      {/* Prompt Enhancer Settings */}
                      <div className="p-3 bg-muted/50 rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">Prompt Enhancer</span>
                          <span className="text-xs text-muted-foreground">
                            Expand your prompts into more variations
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <Label className="text-xs">Enhance by</Label>
                            <select
                              value={enhanceMode}
                              onChange={(e) => setEnhanceMode(e.target.value as typeof enhanceMode)}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={isGenerating}
                            >
                              <option value="random">Random (mixed)</option>
                              <option value="location">Location changes</option>
                              <option value="outfit">Outfit changes</option>
                              <option value="expression">Facial expressions</option>
                              <option value="rewrite">Slight rewrites</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Variations per prompt</Label>
                            <select
                              value={enhanceCount}
                              onChange={(e) => setEnhanceCount(parseInt(e.target.value))}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={isGenerating}
                            >
                              <option value={2}>2 variations</option>
                              <option value={3}>3 variations</option>
                              <option value={5}>5 variations</option>
                              <option value={10}>10 variations</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* Output count */}
                      {images.length > 0 && bulkI2iPrompts.length > 0 && (
                        <p className="text-sm text-muted-foreground pt-2">
                          → Will create <strong>{images.length * bulkI2iPrompts.length} photos</strong> ({images.length} uploaded × {bulkI2iPrompts.length} descriptions)
                        </p>
                      )}

                      {/* Negative prompt */}
                      <div className="space-y-2 pt-3 border-t">
                        <Label className="text-sm text-muted-foreground">What to avoid (optional)</Label>
                        <Textarea
                          value={bulkI2iNegativePrompt}
                          onChange={(e) => setBulkI2iNegativePrompt(e.target.value)}
                          placeholder="blurry, low quality, distorted face, extra limbs..."
                          rows={2}
                          disabled={isGenerating}
                          className="text-sm"
                        />
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Video motion descriptions - shown for 'videos' and 'both' modes */}
                {(bulkMode === 'videos' || bulkMode === 'both') && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center justify-between">
                        <span>Describe how each video should move</span>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handleExpandBulkPrompts('i2v')}
                          disabled={isGenerating || isExpandingI2v || bulkI2vPrompts.length === 0}
                        >
                          {isExpandingI2v ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Wand2 className="h-4 w-4 mr-1" />
                          )}
                          Expand prompts
                        </Button>
                      </CardTitle>
                      <CardDescription>
                        Write one motion per line. Each one will be applied to {bulkMode === 'both' ? 'every photo variation' : 'every photo you uploaded'}.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <MultiPromptInput
                        prompts={bulkI2vPrompts}
                        onPromptsChange={setBulkI2vPrompts}
                        label=""
                        placeholder="slowly turns head and smiles&#10;looks up and laughs naturally&#10;waves hand gently at camera&#10;walks forward with confidence"
                        disabled={isGenerating}
                      />

                      {/* Prompt Enhancer Settings for Video */}
                      <div className="p-3 bg-muted/50 rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">Motion Enhancer</span>
                          <span className="text-xs text-muted-foreground">
                            Generate more motion variations
                          </span>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Variations per motion</Label>
                          <select
                            value={enhanceCount}
                            onChange={(e) => setEnhanceCount(parseInt(e.target.value))}
                            className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                            disabled={isGenerating}
                          >
                            <option value={2}>2 variations</option>
                            <option value={3}>3 variations</option>
                            <option value={5}>5 variations</option>
                            <option value={10}>10 variations</option>
                          </select>
                        </div>
                      </div>

                      {bulkI2vPrompts.length > 0 && (
                        <p className="text-sm text-muted-foreground">
                          {bulkMode === 'both' && images.length > 0 && bulkI2iPrompts.length > 0 ? (
                            <>→ Will create <strong>{images.length * bulkI2iPrompts.length * bulkI2vPrompts.length} videos</strong> ({images.length * bulkI2iPrompts.length} photos × {bulkI2vPrompts.length} motions)</>
                          ) : images.length > 0 ? (
                            <>→ Will create <strong>{images.length * bulkI2vPrompts.length} videos</strong> ({images.length} photos × {bulkI2vPrompts.length} motions)</>
                          ) : null}
                        </p>
                      )}

                      {/* Negative prompt */}
                      <div className="space-y-2 pt-2 border-t">
                        <Label className="text-sm text-muted-foreground">What to avoid (optional)</Label>
                        <Textarea
                          value={bulkI2vNegativePrompt}
                          onChange={(e) => setBulkI2vNegativePrompt(e.target.value)}
                          placeholder="blurry, jittery motion, distorted face..."
                          rows={2}
                          disabled={isGenerating}
                          className="text-sm"
                        />
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {/* Carousel Mode - Story-based content */}
            {mode === 'carousel' && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Create Your Story</CardTitle>
                  <CardDescription>
                    Each prompt creates one slide. Include on-screen captions in your prompts.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Instructions */}
                  <div className="p-3 bg-muted/50 rounded-lg text-sm space-y-2">
                    <p className="font-medium">How to write carousel prompts:</p>
                    <p className="text-muted-foreground">
                      Include the caption text directly in each prompt. The AI will render it on the image.
                    </p>
                    <div className="text-xs text-muted-foreground space-y-1 pt-2 border-t">
                      <p><strong>Example for "Friday vs Monday":</strong></p>
                      <p className="font-mono bg-background p-1 rounded">happy and excited, with on-screen caption "Friday afternoon"</p>
                      <p className="font-mono bg-background p-1 rounded">tired and exhausted, with on-screen caption "Monday morning"</p>
                    </div>
                  </div>

                  {/* Prompt input */}
                  <div className="space-y-2">
                    <Label>Story slides (one prompt per line)</Label>
                    <Textarea
                      value={carouselPrompts.join('\n')}
                      onChange={(e) => setCarouselPrompts(
                        e.target.value.split('\n').filter(l => l.trim().length > 0)
                      )}
                      placeholder={'happy and excited, bright smile, with on-screen caption "Friday afternoon"\ntired and exhausted, messy hair, with on-screen caption "Monday morning"'}
                      rows={6}
                      disabled={isGenerating}
                      className="font-mono text-sm"
                    />
                  </div>

                  {/* Count */}
                  {images.length > 0 && carouselPrompts.length > 0 && (
                    <p className="text-sm text-muted-foreground">
                      → Will create <strong>{images.length * carouselPrompts.length} images</strong> ({images.length} source × {carouselPrompts.length} slides)
                    </p>
                  )}

                  {/* Negative prompt */}
                  <div className="space-y-2 pt-3 border-t">
                    <Label className="text-sm text-muted-foreground">What to avoid (optional)</Label>
                    <Textarea
                      value={carouselNegativePrompt}
                      onChange={(e) => setCarouselNegativePrompt(e.target.value)}
                      placeholder="blurry, low quality, distorted text, unreadable caption..."
                      rows={2}
                      disabled={isGenerating}
                      className="text-sm"
                    />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Progress / Outputs - Standard Mode */}
            {mode !== 'bulk' && mode !== 'carousel' && isGenerating && (
              <ProgressMonitor
                pipelineId={0}
                steps={pipelineSteps}
                status={pipelineStatus}
              />
            )}

            {mode !== 'bulk' && outputs.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Results</CardTitle>
                </CardHeader>
                <CardContent>
                  <OutputGallery outputs={outputs} />
                </CardContent>
              </Card>
            )}

            {/* Bulk/Carousel Mode Progress */}
            {(mode === 'bulk' || mode === 'carousel') && isGenerating && (
              bulkPipelineId ? (
                <BulkProgress
                  pipelineId={bulkPipelineId}
                  status={pipelineStatus}
                  steps={bulkSteps}
                />
              ) : (
                <Card>
                  <CardContent className="py-8">
                    <div className="flex flex-col items-center justify-center gap-3">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <p className="text-sm text-muted-foreground">Starting pipeline...</p>
                    </div>
                  </CardContent>
                </Card>
              )
            )}

            {/* Bulk/Carousel Mode Results */}
            {(mode === 'bulk' || mode === 'carousel') && bulkGroups.length > 0 && (
              <BulkResults
                groups={bulkGroups}
                totals={bulkTotals}
              />
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Model Settings */}
            <Card>
              <CardHeader>
                <CardTitle>{mode === 'bulk' ? 'Quality Settings' : 'Settings'}</CardTitle>
                {mode === 'bulk' && (
                  <CardDescription>Choose which AI models to use</CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                {(mode === 'i2i' || mode === 'pipeline') && (
                  <>
                    <ModelSelector
                      type="i2i"
                      value={i2iModel}
                      onChange={setI2iModel}
                    />

                    <div className="space-y-2">
                      <Label>Aspect Ratio</Label>
                      <select
                        value={i2iAspectRatio}
                        onChange={(e) => setI2iAspectRatio(e.target.value)}
                        className="w-full h-10 px-3 rounded-md border bg-background"
                      >
                        <option value="9:16">9:16 (Portrait)</option>
                        <option value="16:9">16:9 (Landscape)</option>
                        <option value="1:1">1:1 (Square)</option>
                        <option value="4:3">4:3</option>
                        <option value="3:4">3:4</option>
                      </select>
                    </div>

                    {/* Quality selector - shown for GPT Image */}
                    {i2iModel === 'gpt-image-1.5' && (
                      <div className="space-y-2">
                        <Label>Quality</Label>
                        <select
                          value={i2iQuality}
                          onChange={(e) => setI2iQuality(e.target.value as 'low' | 'medium' | 'high')}
                          className="w-full h-10 px-3 rounded-md border bg-background"
                        >
                          <option value="low">Low - $0.01/image</option>
                          <option value="medium">Medium - $0.07/image</option>
                          <option value="high">High - $0.19/image</option>
                        </select>
                      </div>
                    )}

                    <div>
                      <Button
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => setSetModeOpen(true)}
                      >
                        <Layers className="h-4 w-4 mr-2" />
                        {setModeConfig.enabled
                          ? `Set Mode: ${setModeConfig.variations.length} variations`
                          : 'Create Photo Set'}
                      </Button>
                    </div>
                  </>
                )}

                {(mode === 'i2v' || mode === 'pipeline') && (
                  <>
                    <ModelSelector
                      type="i2v"
                      value={i2vModel}
                      onChange={setI2vModel}
                    />

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label>Resolution</Label>
                        <select
                          value={resolution}
                          onChange={(e) => setResolution(e.target.value)}
                          className="w-full h-10 px-3 rounded-md border bg-background"
                        >
                          <option value="480p">480p</option>
                          <option value="720p">720p</option>
                          <option value="1080p">1080p</option>
                        </select>
                      </div>
                      <div className="space-y-2">
                        <Label>Duration</Label>
                        <select
                          value={duration}
                          onChange={(e) => setDuration(e.target.value)}
                          className="w-full h-10 px-3 rounded-md border bg-background"
                        >
                          <option value="5">5 seconds</option>
                          <option value="10">10 seconds</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}

                {/* Bulk Mode Settings */}
                {mode === 'bulk' && (
                  <>
                    {/* Photo settings - shown for photos and both modes */}
                    {(bulkMode === 'photos' || bulkMode === 'both') && (
                      <>
                        <div className="space-y-2">
                          <Label className="text-sm text-muted-foreground">Photo AI model</Label>
                          <ModelSelector
                            type="i2i"
                            value={i2iModel}
                            onChange={setI2iModel}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Photo aspect ratio</Label>
                          <select
                            value={i2iAspectRatio}
                            onChange={(e) => setI2iAspectRatio(e.target.value)}
                            className="w-full h-10 px-3 rounded-md border bg-background"
                          >
                            <option value="9:16">9:16 (Portrait)</option>
                            <option value="16:9">16:9 (Landscape)</option>
                            <option value="1:1">1:1 (Square)</option>
                            <option value="4:3">4:3</option>
                            <option value="3:4">3:4</option>
                          </select>
                        </div>
                        {/* Quality selector - shown for GPT Image */}
                        {i2iModel === 'gpt-image-1.5' && (
                          <div className="space-y-2">
                            <Label>Photo quality</Label>
                            <select
                              value={i2iQuality}
                              onChange={(e) => setI2iQuality(e.target.value as 'low' | 'medium' | 'high')}
                              className="w-full h-10 px-3 rounded-md border bg-background"
                            >
                              <option value="low">Low - $0.01/image</option>
                              <option value="medium">Medium - $0.07/image</option>
                              <option value="high">High - $0.19/image</option>
                            </select>
                          </div>
                        )}
                      </>
                    )}

                    {/* Video model - shown for videos and both modes */}
                    {(bulkMode === 'videos' || bulkMode === 'both') && (
                      <>
                        <div className="space-y-2">
                          <Label className="text-sm text-muted-foreground">Video AI model</Label>
                          <ModelSelector
                            type="i2v"
                            value={i2vModel}
                            onChange={setI2vModel}
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-2">
                            <Label>Video quality</Label>
                            <select
                              value={resolution}
                              onChange={(e) => setResolution(e.target.value)}
                              className="w-full h-10 px-3 rounded-md border bg-background"
                            >
                              <option value="480p">480p (fastest)</option>
                              <option value="720p">720p</option>
                              <option value="1080p">1080p (best)</option>
                            </select>
                          </div>
                          <div className="space-y-2">
                            <Label>Video length</Label>
                            <select
                              value={duration}
                              onChange={(e) => setDuration(e.target.value)}
                              className="w-full h-10 px-3 rounded-md border bg-background"
                            >
                              <option value="5">5 seconds</option>
                              <option value="10">10 seconds</option>
                            </select>
                          </div>
                        </div>
                      </>
                    )}
                  </>
                )}

                {/* Carousel Mode Settings */}
                {mode === 'carousel' && (
                  <>
                    <div className="space-y-2">
                      <Label className="text-sm text-muted-foreground">Photo AI model</Label>
                      <ModelSelector
                        type="i2i"
                        value={i2iModel}
                        onChange={setI2iModel}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Aspect ratio</Label>
                      <select
                        value={i2iAspectRatio}
                        onChange={(e) => setI2iAspectRatio(e.target.value)}
                        className="w-full h-10 px-3 rounded-md border bg-background"
                      >
                        <option value="9:16">9:16 (Portrait)</option>
                        <option value="16:9">16:9 (Landscape)</option>
                        <option value="1:1">1:1 (Square)</option>
                        <option value="4:3">4:3</option>
                        <option value="3:4">3:4</option>
                      </select>
                    </div>
                    {/* Quality selector - shown for GPT Image */}
                    {i2iModel === 'gpt-image-1.5' && (
                      <div className="space-y-2">
                        <Label>Quality</Label>
                        <select
                          value={i2iQuality}
                          onChange={(e) => setI2iQuality(e.target.value as 'low' | 'medium' | 'high')}
                          className="w-full h-10 px-3 rounded-md border bg-background"
                        >
                          <option value="low">Low - $0.01/image</option>
                          <option value="medium">Medium - $0.07/image</option>
                          <option value="high">High - $0.19/image</option>
                        </select>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            {/* Bulk Preview */}
            {mode === 'bulk' && (
              <BulkPreview
                sourceCount={images.length}
                i2iPromptCount={bulkI2iPrompts.length}
                i2vPromptCount={bulkI2vPrompts.length}
                bulkMode={bulkMode}
                costEstimate={bulkCostEstimate}
              />
            )}

            {/* Cost Preview - Standard Mode */}
            {mode !== 'bulk' && (
              <CostPreview
                estimate={costEstimate}
                isLoading={false}
              />
            )}

            {/* Generate Button */}
            <Button
              size="lg"
              className="w-full"
              disabled={!canGenerate}
              onClick={
                mode === 'bulk' ? handleBulkGenerate
                : mode === 'carousel' ? handleCarouselGenerate
                : handleGenerate
              }
            >
              {isGenerating ? (
                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              ) : (
                <Play className="h-5 w-5 mr-2" />
              )}
              {isGenerating
                ? 'Creating...'
                : mode === 'bulk'
                  ? bulkMode === 'photos'
                    ? 'Create Photos'
                    : bulkMode === 'videos'
                      ? 'Create Videos'
                      : 'Create Photos + Videos'
                  : mode === 'carousel'
                    ? 'Create Carousel'
                    : 'Generate'}
            </Button>

            {/* Help text */}
            <p className="text-xs text-muted-foreground text-center">
              {mode === 'i2i' && 'Transform your images with AI-powered editing'}
              {mode === 'i2v' && 'Bring your images to life with video animation'}
              {mode === 'pipeline' && 'Chain multiple steps: enhance prompts → generate images → create videos'}
              {mode === 'bulk' && 'We\'ll create every combination for you automatically'}
              {mode === 'carousel' && 'Create a story with multiple slides'}
            </p>
          </div>
        </div>
      </div>

      {/* Set Mode Modal */}
      <SetModeModal
        isOpen={setModeOpen}
        onClose={() => setSetModeOpen(false)}
        config={setModeConfig}
        onConfigChange={setSetModeConfig}
      />
    </div>
  )
}

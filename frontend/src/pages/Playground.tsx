import { useState, useCallback, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  ImageUploadZone,
  ModelSelector,
  MultiPromptInput,
  BulkPreview,
  BulkProgress,
  BulkResults,
  ImageSourceSelector,
} from '@/components/pipeline'
import type { BulkCostEstimate, BulkStep, SourceGroup } from '@/components/pipeline'
import { Textarea } from '@/components/ui/textarea'
import { Layers, Image, Video, Wand2, Play, Loader2, GalleryHorizontal } from 'lucide-react'

type GenerationMode = 'bulk' | 'carousel'

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

  // Images
  const [images, setImages] = useState<UploadedImage[]>([])
  const [imageSourceMode, setImageSourceMode] = useState<'upload' | 'library'>('upload')
  const [selectedLibraryImages, setSelectedLibraryImages] = useState<string[]>([])

  // I2I Settings
  const [i2iModel, setI2iModel] = useState('gpt-image-1.5')
  const [i2iAspectRatio, setI2iAspectRatio] = useState('9:16')
  const [i2iQuality, setI2iQuality] = useState<'low' | 'medium' | 'high'>('high')

  // I2V Settings
  const [i2vModel, setI2vModel] = useState('kling')
  const [resolution, setResolution] = useState('1080p')
  const [duration, setDuration] = useState('5')
  const [enableAudio, setEnableAudio] = useState(false)

  // Model-specific duration options
  const getDurationOptions = (model: string) => {
    if (model.startsWith('veo')) {
      return [
        { value: '4', label: '4 seconds' },
        { value: '6', label: '6 seconds' },
        { value: '8', label: '8 seconds' },
      ]
    }
    if (model.startsWith('sora')) {
      return [
        { value: '4', label: '4 seconds' },
        { value: '8', label: '8 seconds' },
        { value: '12', label: '12 seconds' },
      ]
    }
    // Kling, Wan models: 5 or 10 seconds
    return [
      { value: '5', label: '5 seconds' },
      { value: '10', label: '10 seconds' },
    ]
  }

  // Check if model supports audio (Veo 3.1 models only)
  const supportsAudio = (model: string) => {
    return ['veo31', 'veo31-fast', 'veo31-flf', 'veo31-fast-flf'].includes(model)
  }

  // Reset duration when model changes (to a valid value for the new model)
  const handleI2vModelChange = (newModel: string) => {
    setI2vModel(newModel)
    const options = getDurationOptions(newModel)
    const currentDurationValid = options.some(opt => opt.value === duration)
    if (!currentDurationValid) {
      setDuration(options[0].value)
    }
    // Disable audio if new model doesn't support it
    if (!supportsAudio(newModel)) {
      setEnableAudio(false)
    }
  }

  // Pipeline State
  const [isGenerating, setIsGenerating] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<'pending' | 'running' | 'paused' | 'completed' | 'failed'>('pending')

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

  // Compute effective source images based on mode
  const effectiveSourceImages = imageSourceMode === 'upload'
    ? images.map(img => img.url)
    : selectedLibraryImages

  // Handlers

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


  // Bulk cost estimation
  const calculateBulkCost = useCallback(async () => {
    // For photos-only mode, we need photo prompts
    // For videos-only mode, we need video prompts
    // For both mode, we need video prompts (photo prompts optional)
    const needsPhotoPrompts = bulkMode === 'photos' || bulkMode === 'both'
    const needsVideoPrompts = bulkMode === 'videos' || bulkMode === 'both'

    if (effectiveSourceImages.length === 0) {
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
          source_images: effectiveSourceImages,
          i2i_config: (bulkMode === 'photos' || bulkMode === 'both') && bulkI2iPrompts.length > 0 ? {
            enabled: true,
            prompts: bulkI2iPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: i2iQuality,
            negative_prompt: bulkI2iNegativePrompt || undefined,
          } : null,
          i2v_config: {
            prompts: bulkMode === 'photos' ? ['placeholder'] : bulkI2vPrompts,
            model: i2vModel,
            resolution,
            duration_sec: parseInt(duration),
            negative_prompt: bulkI2vNegativePrompt || undefined,
            enable_audio: supportsAudio(i2vModel) ? enableAudio : false,
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
  }, [effectiveSourceImages, bulkMode, bulkI2iPrompts, bulkI2iNegativePrompt, bulkI2vPrompts, bulkI2vNegativePrompt, i2iModel, i2iAspectRatio, i2iQuality, i2vModel, resolution, duration, enableAudio])

  // Recalculate bulk cost when settings change
  useEffect(() => {
    if (mode === 'bulk') {
      calculateBulkCost()
    }
  }, [mode, calculateBulkCost])

  // Bulk generate handler
  const handleBulkGenerate = async () => {
    if (effectiveSourceImages.length === 0) return
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
          source_images: effectiveSourceImages,
          i2i_config: includePhotos && bulkI2iPrompts.length > 0 ? {
            enabled: true,
            prompts: bulkI2iPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: i2iQuality,
            negative_prompt: bulkI2iNegativePrompt || undefined,
          } : null,
          i2v_config: includeVideos ? {
            prompts: bulkI2vPrompts,
            model: i2vModel,
            resolution,
            duration_sec: parseInt(duration),
            negative_prompt: bulkI2vNegativePrompt || undefined,
            enable_audio: supportsAudio(i2vModel) ? enableAudio : false,
          } : { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration), enable_audio: false },
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
    if (effectiveSourceImages.length === 0 || carouselPrompts.length === 0) return

    setIsGenerating(true)
    setPipelineStatus('running')
    setBulkGroups([])

    try {
      const response = await fetch('/api/pipelines/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Carousel - ${new Date().toLocaleString()}`,
          source_images: effectiveSourceImages,
          i2i_config: {
            enabled: true,
            prompts: carouselPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: i2iQuality,
            negative_prompt: carouselNegativePrompt || undefined,
          },
          i2v_config: { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration), enable_audio: false },
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

  // Animate selected images handler
  const handleAnimateSelectedImages = async (selectedImageUrls: string[]) => {
    if (selectedImageUrls.length === 0 || bulkI2vPrompts.length === 0) {
      alert('Please enter at least one motion prompt in the video motion section')
      return
    }

    setIsGenerating(true)
    setPipelineStatus('running')
    setBulkGroups([])
    setBulkSteps([])

    try {
      const response = await fetch('/api/pipelines/animate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `Animate Selected - ${new Date().toLocaleString()}`,
          image_urls: selectedImageUrls,
          prompts: bulkI2vPrompts,
          model: i2vModel,
          resolution,
          duration_sec: parseInt(duration),
          negative_prompt: bulkI2vNegativePrompt || undefined,
          enable_audio: supportsAudio(i2vModel) ? enableAudio : false,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        console.error('Animate pipeline creation failed:', errorData)
        setPipelineStatus('failed')
        setIsGenerating(false)
        alert(`Failed to create pipeline: ${errorData.detail || 'Unknown error'}`)
        return
      }

      const data = await response.json()
      setBulkPipelineId(data.pipeline_id)

      // Poll for status
      const pollStatus = async () => {
        const statusRes = await fetch(`/api/pipelines/bulk/${data.pipeline_id}`)
        if (statusRes.ok) {
          const statusData = await statusRes.json()
          setPipelineStatus(statusData.status)
          setBulkGroups(statusData.groups)
          setBulkTotals(statusData.totals)

          if (statusData.status === 'running') {
            setTimeout(pollStatus, 2000)
          } else {
            setIsGenerating(false)
          }
        }
      }

      pollStatus()
    } catch (error) {
      console.error('Animate pipeline failed:', error)
      setPipelineStatus('failed')
      setIsGenerating(false)
    }
  }

  // Check if generation is possible
  const canGenerate = mode === 'bulk'
    ? effectiveSourceImages.length > 0 && !isGenerating && (
        (bulkMode === 'photos' && bulkI2iPrompts.length > 0) ||
        (bulkMode === 'videos' && bulkI2vPrompts.length > 0) ||
        (bulkMode === 'both' && bulkI2vPrompts.length > 0)
      )
    : mode === 'carousel'
      ? effectiveSourceImages.length > 0 && carouselPrompts.length > 0 && !isGenerating
      : false

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
                <TabsTrigger value="bulk" className="gap-2">
                  <Wand2 className="h-4 w-4" />
                  Create
                </TabsTrigger>
                <TabsTrigger value="carousel" className="gap-2">
                  <GalleryHorizontal className="h-4 w-4" />
                  Carousel
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-6">
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Image Source Selection */}
            <ImageSourceSelector
              mode={imageSourceMode}
              onModeChange={setImageSourceMode}
              uploadContent={
                <ImageUploadZone
                  images={images}
                  onImagesChange={setImages}
                  multiple={true}
                  maxFiles={10}
                  disabled={isGenerating}
                />
              }
              selectedLibraryImages={selectedLibraryImages}
              onLibrarySelectionChange={setSelectedLibraryImages}
              disabled={isGenerating}
            />

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
                      {effectiveSourceImages.length > 0 && bulkI2iPrompts.length > 0 && (
                        <p className="text-sm text-muted-foreground pt-2">
                          → Will create <strong>{effectiveSourceImages.length * bulkI2iPrompts.length} photos</strong> ({effectiveSourceImages.length} {imageSourceMode === 'library' ? 'selected' : 'uploaded'} × {bulkI2iPrompts.length} descriptions)
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
                          {bulkMode === 'both' && effectiveSourceImages.length > 0 && bulkI2iPrompts.length > 0 ? (
                            <>→ Will create <strong>{effectiveSourceImages.length * bulkI2iPrompts.length * bulkI2vPrompts.length} videos</strong> ({effectiveSourceImages.length * bulkI2iPrompts.length} photos × {bulkI2vPrompts.length} motions)</>
                          ) : effectiveSourceImages.length > 0 ? (
                            <>→ Will create <strong>{effectiveSourceImages.length * bulkI2vPrompts.length} videos</strong> ({effectiveSourceImages.length} {imageSourceMode === 'library' ? 'selected' : 'photos'} × {bulkI2vPrompts.length} motions)</>
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
                  {effectiveSourceImages.length > 0 && carouselPrompts.length > 0 && (
                    <p className="text-sm text-muted-foreground">
                      → Will create <strong>{effectiveSourceImages.length * carouselPrompts.length} images</strong> ({effectiveSourceImages.length} {imageSourceMode === 'library' ? 'selected' : 'source'} × {carouselPrompts.length} slides)
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

            {/* Progress */}
            {isGenerating && (
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

            {/* Results */}
            {bulkGroups.length > 0 && (
              <BulkResults
                groups={bulkGroups}
                totals={bulkTotals}
                onAnimateSelected={handleAnimateSelectedImages}
              />
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Model Settings */}
            <Card>
              <CardHeader>
                <CardTitle>Quality Settings</CardTitle>
                <CardDescription>Choose which AI models to use</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
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
                            onChange={handleI2vModelChange}
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
                              {getDurationOptions(i2vModel).map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                              ))}
                            </select>
                          </div>
                        </div>

                        {/* Audio toggle for Veo 3.1 models */}
                        {supportsAudio(i2vModel) && (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <Label>Generate with audio</Label>
                              <button
                                type="button"
                                onClick={() => setEnableAudio(!enableAudio)}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                  enableAudio ? 'bg-primary' : 'bg-muted'
                                }`}
                              >
                                <span
                                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                    enableAudio ? 'translate-x-6' : 'translate-x-1'
                                  }`}
                                />
                              </button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {enableAudio
                                ? 'Audio enabled - costs ~1.5-2x more'
                                : 'Audio disabled - lower cost'}
                            </p>
                          </div>
                        )}
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

            {/* Cost Preview */}
            {mode === 'bulk' && (
              <BulkPreview
                sourceCount={effectiveSourceImages.length}
                i2iPromptCount={bulkI2iPrompts.length}
                i2vPromptCount={bulkI2vPrompts.length}
                bulkMode={bulkMode}
                costEstimate={bulkCostEstimate}
              />
            )}

            {/* Generate Button */}
            <Button
              size="lg"
              className="w-full"
              disabled={!canGenerate}
              onClick={mode === 'bulk' ? handleBulkGenerate : handleCarouselGenerate}
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
                  : 'Create Carousel'}
            </Button>

            {/* Help text */}
            <p className="text-xs text-muted-foreground text-center">
              {mode === 'bulk' && 'We\'ll create every combination for you automatically'}
              {mode === 'carousel' && 'Create a story with multiple slides'}
            </p>
          </div>
        </div>
      </div>

    </div>
  )
}

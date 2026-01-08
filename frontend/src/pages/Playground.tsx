import { useState, useCallback, useEffect, useRef } from 'react'
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
  ConfirmGenerationModal,
  shouldShowConfirmation,
} from '@/components/pipeline'
import type { BulkCostEstimate, BulkStep, SourceGroup } from '@/components/pipeline'
import { Textarea } from '@/components/ui/textarea'
import { Layers, Image, Video, Wand2, Play, Loader2, GalleryHorizontal, History, ChevronDown, ChevronUp, Plus, Copy, Check, Sparkles } from 'lucide-react'
import { cancelPipeline } from '@/api/client'

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
  const [i2iQuality, setI2iQuality] = useState<'low' | 'medium' | 'high'>('low')

  // FLUX-specific settings (persisted to localStorage)
  const [fluxStrength, setFluxStrength] = useState(() =>
    parseFloat(localStorage.getItem('i2v_fluxStrength') || '0.75')
  )
  const [fluxGuidanceScale, setFluxGuidanceScale] = useState(() =>
    parseFloat(localStorage.getItem('i2v_fluxGuidanceScale') || '1.0')
  )
  const [fluxNumInferenceSteps, setFluxNumInferenceSteps] = useState(() =>
    parseInt(localStorage.getItem('i2v_fluxNumInferenceSteps') || '28')
  )
  const [fluxSeed, setFluxSeed] = useState<number | null>(() => {
    const saved = localStorage.getItem('i2v_fluxSeed')
    return saved ? parseInt(saved) : null
  })
  const [fluxScheduler, setFluxScheduler] = useState<'euler' | 'dpmpp_2m'>(() =>
    (localStorage.getItem('i2v_fluxScheduler') as 'euler' | 'dpmpp_2m') || 'euler'
  )

  // FLUX.2 specific settings
  const [fluxEnablePromptExpansion, setFluxEnablePromptExpansion] = useState(() =>
    localStorage.getItem('i2v_fluxEnablePromptExpansion') === 'true'
  )
  const [fluxAcceleration, setFluxAcceleration] = useState<'none' | 'regular' | 'high'>(() =>
    (localStorage.getItem('i2v_fluxAcceleration') as 'none' | 'regular' | 'high') || 'regular'
  )
  const [showFluxAdvanced, setShowFluxAdvanced] = useState(false)

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

  // Check if model supports audio (Veo models)
  const supportsAudio = (model: string) => {
    return ['veo2', 'veo31', 'veo31-fast', 'veo31-flf', 'veo31-fast-flf'].includes(model)
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
  const [pipelineStatus, setPipelineStatus] = useState<'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'>('pending')
  const [jobSent, setJobSent] = useState(false)  // Shows "Job sent!" indicator

  // Bulk Mode State - persisted to localStorage
  const [bulkMode, setBulkMode] = useState<'photos' | 'videos' | 'both'>(() => {
    const saved = localStorage.getItem('playground-default-bulkMode')
    return (saved as 'photos' | 'videos' | 'both') || 'videos'
  })
  const [bulkI2iPrompts, setBulkI2iPrompts] = useState<string[]>([])
  const [bulkI2vPrompts, setBulkI2vPrompts] = useState<string[]>([])
  const [bulkI2iNegativePrompt, setBulkI2iNegativePrompt] = useState(() => {
    const saved = localStorage.getItem('i2v_bulkI2iNegativePrompt')
    // Clear old default negative prompt that was causing issues
    if (saved?.includes('skinny, slim, thin, petite')) {
      localStorage.removeItem('i2v_bulkI2iNegativePrompt')
      return ''
    }
    return saved || ''
  })
  const [bulkI2vNegativePrompt, setBulkI2vNegativePrompt] = useState(() =>
    localStorage.getItem('i2v_bulkI2vNegativePrompt') || ''
  )
  const [isExpandingI2i, setIsExpandingI2i] = useState(false)
  const [isExpandingI2v, setIsExpandingI2v] = useState(false)
  // Prompt enhancement settings
  const [enhanceMode, setEnhanceMode] = useState<'location' | 'outfit' | 'expression' | 'rewrite' | 'random'>('random')
  const [enhanceCount, setEnhanceCount] = useState(3)
  const [enhanceIntensity, setEnhanceIntensity] = useState<'subtle' | 'moderate' | 'wild'>('moderate')
  const [bulkCostEstimate, setBulkCostEstimate] = useState<BulkCostEstimate | null>(null)
  const [bulkPipelineId, setBulkPipelineId] = useState<number | null>(null)
  const [runName, setRunName] = useState('')
  const [bulkSteps, setBulkSteps] = useState<BulkStep[]>([])
  const [bulkGroups, setBulkGroups] = useState<SourceGroup[]>([])
  const [bulkTotals, setBulkTotals] = useState({ source_images: 0, i2i_generated: 0, i2v_generated: 0, total_cost: 0 })

  // Carousel Mode State - each prompt = one slide in the story
  const [carouselPrompts, setCarouselPrompts] = useState<string[]>([])
  const [carouselNegativePrompt, setCarouselNegativePrompt] = useState(() =>
    localStorage.getItem('i2v_carouselNegativePrompt') || ''
  )

  // Recent prompts state
  interface RecentPrompt {
    prompt: string
    step_type: string
    model: string
    used_at: string | null
  }
  const [recentI2iPrompts, setRecentI2iPrompts] = useState<RecentPrompt[]>([])
  const [recentI2vPrompts, setRecentI2vPrompts] = useState<RecentPrompt[]>([])
  const [showRecentI2i, setShowRecentI2i] = useState(true)  // Show by default when prompts exist
  const [showRecentI2v, setShowRecentI2v] = useState(true)  // Show by default when prompts exist
  const [copiedPrompt, setCopiedPrompt] = useState<string | null>(null)

  // Prompt Builder state
  const [showPromptBuilder, setShowPromptBuilder] = useState(false)
  const [promptBuilderStyle, setPromptBuilderStyle] = useState<'cosplay' | 'cottagecore' | 'gym' | 'bookish' | 'nurse'>('cosplay')
  const [promptBuilderLocation, setPromptBuilderLocation] = useState<'outdoor' | 'indoor' | 'mixed'>('mixed')
  const [promptBuilderCount, setPromptBuilderCount] = useState(10)
  const [promptBuilderExaggeratedBust, setPromptBuilderExaggeratedBust] = useState(false)
  const [promptBuilderPreserveIdentity, setPromptBuilderPreserveIdentity] = useState(true)
  const [promptBuilderFraming, setPromptBuilderFraming] = useState<'close' | 'medium' | 'full'>('medium')
  const [promptBuilderRealism, setPromptBuilderRealism] = useState(true)
  const [promptBuilderLoading, setPromptBuilderLoading] = useState(false)
  const [generatedPrompts, setGeneratedPrompts] = useState<string[]>([])
  const [promptBuilderCopied, setPromptBuilderCopied] = useState(false)

  // Confirmation modal state
  const [showConfirmModal, setShowConfirmModal] = useState(false)

  // Ref for results section (auto-scroll)
  const resultsRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to results when generation completes
  useEffect(() => {
    if (pipelineStatus === 'completed' && bulkGroups.length > 0) {
      resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [pipelineStatus, bulkGroups.length])

  // Persist negative prompts to localStorage
  useEffect(() => {
    localStorage.setItem('i2v_bulkI2iNegativePrompt', bulkI2iNegativePrompt)
  }, [bulkI2iNegativePrompt])

  useEffect(() => {
    localStorage.setItem('i2v_bulkI2vNegativePrompt', bulkI2vNegativePrompt)
  }, [bulkI2vNegativePrompt])

  useEffect(() => {
    localStorage.setItem('i2v_carouselNegativePrompt', carouselNegativePrompt)
  }, [carouselNegativePrompt])

  // Persist FLUX settings to localStorage
  useEffect(() => {
    localStorage.setItem('i2v_fluxStrength', fluxStrength.toString())
  }, [fluxStrength])

  useEffect(() => {
    localStorage.setItem('i2v_fluxGuidanceScale', fluxGuidanceScale.toString())
  }, [fluxGuidanceScale])

  useEffect(() => {
    localStorage.setItem('i2v_fluxNumInferenceSteps', fluxNumInferenceSteps.toString())
  }, [fluxNumInferenceSteps])

  useEffect(() => {
    if (fluxSeed !== null) {
      localStorage.setItem('i2v_fluxSeed', fluxSeed.toString())
    } else {
      localStorage.removeItem('i2v_fluxSeed')
    }
  }, [fluxSeed])

  useEffect(() => {
    localStorage.setItem('i2v_fluxScheduler', fluxScheduler)
  }, [fluxScheduler])

  // FLUX.2 specific settings persistence
  useEffect(() => {
    localStorage.setItem('i2v_fluxEnablePromptExpansion', String(fluxEnablePromptExpansion))
  }, [fluxEnablePromptExpansion])

  useEffect(() => {
    localStorage.setItem('i2v_fluxAcceleration', fluxAcceleration)
  }, [fluxAcceleration])

  // Fetch recent prompts on mount
  useEffect(() => {
    const fetchRecentPrompts = async () => {
      try {
        // Fetch I2I prompts
        const i2iRes = await fetch('/api/pipelines/prompts/recent?step_type=i2i&limit=15')
        if (i2iRes.ok) {
          const data = await i2iRes.json()
          setRecentI2iPrompts(data.prompts)
        }

        // Fetch I2V prompts
        const i2vRes = await fetch('/api/pipelines/prompts/recent?step_type=i2v&limit=15')
        if (i2vRes.ok) {
          const data = await i2vRes.json()
          setRecentI2vPrompts(data.prompts)
        }
      } catch (error) {
        console.error('Failed to fetch recent prompts:', error)
      }
    }

    fetchRecentPrompts()
  }, [])

  // Add a recent prompt to the prompt list
  const handleAddRecentPrompt = (type: 'i2i' | 'i2v' | 'carousel', prompt: string) => {
    if (type === 'i2i') {
      if (!bulkI2iPrompts.includes(prompt)) {
        setBulkI2iPrompts([...bulkI2iPrompts, prompt])
      }
    } else if (type === 'i2v') {
      if (!bulkI2vPrompts.includes(prompt)) {
        setBulkI2vPrompts([...bulkI2vPrompts, prompt])
      }
    } else if (type === 'carousel') {
      if (!carouselPrompts.includes(prompt)) {
        setCarouselPrompts([...carouselPrompts, prompt])
      }
    }
  }

  // Copy prompt to clipboard
  const handleCopyPrompt = async (prompt: string) => {
    try {
      await navigator.clipboard.writeText(prompt)
      setCopiedPrompt(prompt)
      setTimeout(() => setCopiedPrompt(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  // Prompt Builder handlers
  const handleGeneratePrompts = async () => {
    console.log('[PromptBuilder] Starting generation...', {
      count: promptBuilderCount,
      style: promptBuilderStyle,
      location: promptBuilderLocation,
    })
    setPromptBuilderLoading(true)
    try {
      const requestBody = {
        count: promptBuilderCount,
        style: promptBuilderStyle,
        location: promptBuilderLocation,
        exaggerated_bust: promptBuilderExaggeratedBust,
        preserve_identity: promptBuilderPreserveIdentity,
        framing: promptBuilderFraming,
        realism: promptBuilderRealism,
      }
      console.log('[PromptBuilder] Request body:', requestBody)

      const response = await fetch('/api/generate-prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })

      console.log('[PromptBuilder] Response status:', response.status)

      if (response.ok) {
        const data = await response.json()
        console.log('[PromptBuilder] Success! Received prompts:', data.prompts?.length)
        setGeneratedPrompts(data.prompts)
      } else {
        const errorText = await response.text()
        console.error('[PromptBuilder] Error response:', response.status, errorText)
        let errorMessage = 'Unknown error'
        try {
          const errorData = JSON.parse(errorText)
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          } else if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((e: {msg?: string}) => e.msg || JSON.stringify(e)).join('; ')
          } else if (errorData.detail) {
            errorMessage = JSON.stringify(errorData.detail)
          } else if (errorData.message) {
            errorMessage = errorData.message
          }
        } catch {
          errorMessage = errorText || 'Unknown error'
        }
        alert(`Failed to generate prompts (${response.status}): ${errorMessage}`)
      }
    } catch (error) {
      console.error('[PromptBuilder] Fetch error:', error)
      alert('Failed to generate prompts. Check console for details.')
    } finally {
      setPromptBuilderLoading(false)
    }
  }

  const handleCopyAllPrompts = async () => {
    try {
      await navigator.clipboard.writeText(generatedPrompts.join('\n'))
      setPromptBuilderCopied(true)
      setTimeout(() => setPromptBuilderCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleAddGeneratedToI2i = () => {
    // Add generated prompts to I2I prompts (deduplicated)
    console.log('[AddToI2I] Current bulkI2iPrompts:', bulkI2iPrompts.length, bulkI2iPrompts.slice(0, 2))
    console.log('[AddToI2I] Generated prompts:', generatedPrompts.length, generatedPrompts.slice(0, 2))
    const combined = [...new Set([...bulkI2iPrompts, ...generatedPrompts])]
    console.log('[AddToI2I] Combined prompts:', combined.length, combined.slice(0, 2))
    setBulkI2iPrompts(combined)
  }

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
          intensity: enhanceIntensity,
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
            // FLUX params (all FLUX models: flux-general, flux-2-*, flux-kontext-*)
            ...((i2iModel === 'flux-general' || i2iModel.startsWith('flux-2') || i2iModel.startsWith('flux-kontext')) ? {
              flux_strength: i2iModel === 'flux-general' ? fluxStrength : undefined,
              flux_guidance_scale: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxGuidanceScale : undefined,
              flux_num_inference_steps: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxNumInferenceSteps : undefined,
              flux_seed: fluxSeed,
              flux_scheduler: i2iModel === 'flux-general' ? fluxScheduler : undefined,
              // FLUX.2 specific params (per-model support)
              flux_enable_prompt_expansion: ['flux-2-dev', 'flux-2-flex'].includes(i2iModel) ? fluxEnablePromptExpansion : undefined,
              flux_acceleration: i2iModel === 'flux-2-dev' ? fluxAcceleration : undefined,
            } : {}),
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

  // Persist mode selections to localStorage
  useEffect(() => {
    localStorage.setItem('playground-default-mode', mode)
  }, [mode])

  useEffect(() => {
    localStorage.setItem('playground-default-bulkMode', bulkMode)
  }, [bulkMode])

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
      // Debug log to see what's being sent
      const requestBody = {
        name: runName.trim() || `Bulk ${bulkMode === 'photos' ? 'Photos' : bulkMode === 'videos' ? 'Videos' : 'Photos + Videos'} - ${new Date().toLocaleString()}`,
        source_images: effectiveSourceImages,
        i2i_config: includePhotos && bulkI2iPrompts.length > 0 ? {
          enabled: true,
          prompts: bulkI2iPrompts,
          model: i2iModel,
          images_per_prompt: 1,
          aspect_ratio: i2iAspectRatio,
          quality: i2iQuality,
          negative_prompt: bulkI2iNegativePrompt || undefined,
          // FLUX params (all FLUX models)
          ...((i2iModel === 'flux-general' || i2iModel.startsWith('flux-2') || i2iModel.startsWith('flux-kontext')) ? {
            flux_strength: i2iModel === 'flux-general' ? fluxStrength : undefined,
            flux_guidance_scale: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxGuidanceScale : undefined,
            flux_num_inference_steps: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxNumInferenceSteps : undefined,
            flux_seed: fluxSeed,
            flux_scheduler: i2iModel === 'flux-general' ? fluxScheduler : undefined,
            // FLUX.2 specific params (per-model support)
            flux_enable_prompt_expansion: ['flux-2-dev', 'flux-2-flex'].includes(i2iModel) ? fluxEnablePromptExpansion : undefined,
            flux_acceleration: i2iModel === 'flux-2-dev' ? fluxAcceleration : undefined,
          } : {}),
        } : null,
        i2v_config: includeVideos ? {
          prompts: bulkI2vPrompts,
          model: i2vModel,
          resolution,
          duration_sec: parseInt(duration),
          negative_prompt: bulkI2vNegativePrompt || undefined,
          enable_audio: supportsAudio(i2vModel) ? enableAudio : false,
        } : { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration), enable_audio: false },
      }

      console.log('[Bulk Generate] Sending request:', JSON.stringify(requestBody, null, 2))
      console.log('[Bulk Generate] FLUX params:', { fluxStrength, fluxGuidanceScale, fluxNumInferenceSteps, fluxSeed, fluxScheduler })
      console.log('[Bulk Generate] I2I Prompts:', bulkI2iPrompts)

      const response = await fetch('/api/pipelines/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        console.error('Bulk pipeline creation failed:', response.status, errorData)
        setPipelineStatus('failed')
        setIsGenerating(false)

        // Extract error message from various FastAPI error formats
        let errorMessage = 'Unknown error'
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail
        } else if (Array.isArray(errorData.detail)) {
          // FastAPI validation errors return array of {loc, msg, type}
          errorMessage = errorData.detail.map((e: {msg?: string; loc?: string[]}) =>
            e.msg || JSON.stringify(e)
          ).join('; ')
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          errorMessage = JSON.stringify(errorData.detail)
        } else if (errorData.message) {
          errorMessage = errorData.message
        } else if (typeof errorData === 'string') {
          errorMessage = errorData
        }

        alert(`Failed to create pipeline (${response.status}): ${errorMessage}`)
        return
      }

      const data = await response.json()
      setBulkPipelineId(data.pipeline_id)

      // Show "Job sent!" and reset immediately so user can create another job
      setJobSent(true)
      setIsGenerating(false)
      setPipelineStatus('pending')
      setTimeout(() => setJobSent(false), 4000)  // Hide after 4 seconds

      // Note: User can check progress on Jobs page - no polling needed here
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
          name: runName.trim() || `Carousel - ${new Date().toLocaleString()}`,
          source_images: effectiveSourceImages,
          i2i_config: {
            enabled: true,
            prompts: carouselPrompts,
            model: i2iModel,
            images_per_prompt: 1,
            aspect_ratio: i2iAspectRatio,
            quality: i2iQuality,
            negative_prompt: carouselNegativePrompt || undefined,
            // FLUX params (all FLUX models)
            ...((i2iModel === 'flux-general' || i2iModel.startsWith('flux-2') || i2iModel.startsWith('flux-kontext')) ? {
              flux_strength: i2iModel === 'flux-general' ? fluxStrength : undefined,
              flux_guidance_scale: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxGuidanceScale : undefined,
              flux_num_inference_steps: ['flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) ? fluxNumInferenceSteps : undefined,
              flux_seed: fluxSeed,
              flux_scheduler: i2iModel === 'flux-general' ? fluxScheduler : undefined,
              // FLUX.2 specific params (per-model support)
              flux_enable_prompt_expansion: ['flux-2-dev', 'flux-2-flex'].includes(i2iModel) ? fluxEnablePromptExpansion : undefined,
              flux_acceleration: i2iModel === 'flux-2-dev' ? fluxAcceleration : undefined,
            } : {}),
          },
          i2v_config: { prompts: [], model: i2vModel, resolution, duration_sec: parseInt(duration), enable_audio: false },
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setBulkPipelineId(data.pipeline_id)

        // Show "Job sent!" and reset immediately so user can create another job
        setJobSent(true)
        setIsGenerating(false)
        setPipelineStatus('pending')
        setTimeout(() => setJobSent(false), 4000)
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
          name: runName.trim() || `Animate Selected - ${new Date().toLocaleString()}`,
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
        console.error('Animate pipeline creation failed:', response.status, errorData)
        setPipelineStatus('failed')
        setIsGenerating(false)

        // Extract error message from various FastAPI error formats
        let errorMessage = 'Unknown error'
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((e: {msg?: string; loc?: string[]}) =>
            e.msg || JSON.stringify(e)
          ).join('; ')
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          errorMessage = JSON.stringify(errorData.detail)
        } else if (errorData.message) {
          errorMessage = errorData.message
        } else if (typeof errorData === 'string') {
          errorMessage = errorData
        }

        alert(`Failed to create pipeline (${response.status}): ${errorMessage}`)
        return
      }

      const data = await response.json()
      setBulkPipelineId(data.pipeline_id)

      // Show "Job sent!" and reset immediately so user can create another job
      setJobSent(true)
      setIsGenerating(false)
      setPipelineStatus('pending')
      setTimeout(() => setJobSent(false), 4000)
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

  // Handler to check if confirmation modal should be shown
  const handleGenerateClick = () => {
    if (mode === 'bulk' && shouldShowConfirmation(bulkCostEstimate)) {
      setShowConfirmModal(true)
    } else {
      mode === 'bulk' ? handleBulkGenerate() : handleCarouselGenerate()
    }
  }

  // Confirm and start generation
  const handleConfirmGenerate = () => {
    setShowConfirmModal(false)
    mode === 'bulk' ? handleBulkGenerate() : handleCarouselGenerate()
  }

  // Cancel running pipeline
  const handleCancelPipeline = async () => {
    if (!bulkPipelineId) return
    try {
      await cancelPipeline(bulkPipelineId)
      setPipelineStatus('cancelled')
      setIsGenerating(false)
    } catch (error) {
      console.error('Failed to cancel pipeline:', error)
    }
  }

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
        {/* Job Sent Toast */}
        {jobSent && (
          <div className="fixed top-20 right-4 z-50 animate-in slide-in-from-right duration-300">
            <div className="bg-green-500 text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="font-medium">Job sent! Check Jobs page for progress.</span>
            </div>
          </div>
        )}

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
                  maxFiles={200}
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

                {/* Prompt Builder - AI prompt generation */}
                {(bulkMode === 'photos' || bulkMode === 'both') && (
                  <Card>
                    <CardHeader
                      className="cursor-pointer"
                      onClick={() => setShowPromptBuilder(!showPromptBuilder)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-5 w-5 text-primary" />
                          <CardTitle className="text-lg">AI Prompt Builder</CardTitle>
                        </div>
                        <Button variant="ghost" size="sm">
                          {showPromptBuilder ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                      <CardDescription>
                        Generate i2i prompts with on-screen TikTok captions
                      </CardDescription>
                    </CardHeader>

                    {showPromptBuilder && (
                      <CardContent className="space-y-4">
                        {/* Settings Row */}
                        <div className="grid grid-cols-4 gap-3">
                          <div className="space-y-1">
                            <Label className="text-xs">Style/Niche</Label>
                            <select
                              value={promptBuilderStyle}
                              onChange={(e) => setPromptBuilderStyle(e.target.value as 'cosplay' | 'cottagecore' | 'gym' | 'bookish' | 'nurse')}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={promptBuilderLoading}
                            >
                              <option value="cosplay">Cosplay (anime)</option>
                              <option value="cottagecore">Cottagecore</option>
                              <option value="gym">Gym / Fitness</option>
                              <option value="bookish">Bookish / Dark Academia</option>
                              <option value="nurse">Nurse / Medical</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Location</Label>
                            <select
                              value={promptBuilderLocation}
                              onChange={(e) => setPromptBuilderLocation(e.target.value as 'outdoor' | 'indoor' | 'mixed')}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={promptBuilderLoading}
                            >
                              <option value="mixed">Mixed</option>
                              <option value="outdoor">Outdoor</option>
                              <option value="indoor">Indoor</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Framing</Label>
                            <select
                              value={promptBuilderFraming}
                              onChange={(e) => setPromptBuilderFraming(e.target.value as 'close' | 'medium' | 'full')}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={promptBuilderLoading}
                            >
                              <option value="close">Close (face)</option>
                              <option value="medium">Medium (waist up)</option>
                              <option value="full">Full body</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Count</Label>
                            <input
                              type="number"
                              min={1}
                              max={50}
                              value={promptBuilderCount}
                              onChange={(e) => setPromptBuilderCount(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={promptBuilderLoading}
                            />
                          </div>
                        </div>

                        {/* Modifier Toggles */}
                        <div className="flex flex-wrap gap-4">
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={promptBuilderPreserveIdentity}
                              onChange={(e) => setPromptBuilderPreserveIdentity(e.target.checked)}
                              disabled={promptBuilderLoading}
                              className="rounded"
                            />
                            <span className="text-muted-foreground">Preserve identity</span>
                          </label>
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={promptBuilderRealism}
                              onChange={(e) => setPromptBuilderRealism(e.target.checked)}
                              disabled={promptBuilderLoading}
                              className="rounded"
                            />
                            <span className="text-muted-foreground">Realistic backgrounds</span>
                          </label>
                          <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                              type="checkbox"
                              checked={promptBuilderExaggeratedBust}
                              onChange={(e) => setPromptBuilderExaggeratedBust(e.target.checked)}
                              disabled={promptBuilderLoading}
                              className="rounded"
                            />
                            <span className="text-muted-foreground">Exaggerated bust</span>
                          </label>
                        </div>

                        {/* Generate Button */}
                        <Button
                          onClick={handleGeneratePrompts}
                          disabled={promptBuilderLoading}
                          className="w-full"
                        >
                          {promptBuilderLoading ? (
                            <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Generating...</>
                          ) : (
                            <><Sparkles className="h-4 w-4 mr-2" /> Generate {promptBuilderCount} Prompts</>
                          )}
                        </Button>

                        {/* Generated Prompts Output */}
                        {generatedPrompts.length > 0 && (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <Label className="text-sm font-medium">Generated Prompts ({generatedPrompts.length})</Label>
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={handleAddGeneratedToI2i}
                                  disabled={isGenerating}
                                >
                                  <Plus className="h-4 w-4 mr-1" />
                                  Add to Photo Prompts
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={handleCopyAllPrompts}
                                >
                                  {promptBuilderCopied ? (
                                    <><Check className="h-4 w-4 mr-1" /> Copied!</>
                                  ) : (
                                    <><Copy className="h-4 w-4 mr-1" /> Copy All</>
                                  )}
                                </Button>
                              </div>
                            </div>
                            <Textarea
                              value={generatedPrompts.join('\n\n')}
                              readOnly
                              rows={10}
                              className="font-mono text-xs"
                            />
                          </div>
                        )}
                      </CardContent>
                    )}
                  </Card>
                )}

                {/* Photo descriptions - shown for 'photos' and 'both' modes */}
                {(bulkMode === 'photos' || bulkMode === 'both') && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center justify-between">
                        <span>Describe the photo variations you want</span>
                        <div className="flex gap-2">
                          {recentI2iPrompts.length > 0 && (
                            <Button
                              type="button"
                              variant={showRecentI2i ? "secondary" : "outline"}
                              size="sm"
                              onClick={() => setShowRecentI2i(!showRecentI2i)}
                              disabled={isGenerating}
                            >
                              <History className="h-4 w-4 mr-1" />
                              Recent
                              {showRecentI2i ? (
                                <ChevronUp className="h-3 w-3 ml-1" />
                              ) : (
                                <ChevronDown className="h-3 w-3 ml-1" />
                              )}
                            </Button>
                          )}
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
                            Expand
                          </Button>
                        </div>
                      </CardTitle>
                      <CardDescription>
                        Write one description per line. Each one creates a new version of every photo you uploaded.
                      </CardDescription>

                      {/* Recent Prompts Panel */}
                      {showRecentI2i && recentI2iPrompts.length > 0 && (
                        <div className="mt-3 p-3 bg-muted/50 rounded-lg border max-h-64 overflow-y-auto">
                          <p className="text-sm font-medium mb-2">Recently used prompts</p>
                          <div className="space-y-2">
                            {recentI2iPrompts.map((p, idx) => (
                              <div key={idx} className="p-2 bg-background rounded border text-sm">
                                <p className="text-foreground mb-2 whitespace-pre-wrap">{p.prompt}</p>
                                <div className="flex gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs"
                                    onClick={() => handleAddRecentPrompt('i2i', p.prompt)}
                                    disabled={bulkI2iPrompts.includes(p.prompt)}
                                  >
                                    <Plus className="h-3 w-3 mr-1" />
                                    {bulkI2iPrompts.includes(p.prompt) ? 'Added' : 'Add'}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs"
                                    onClick={() => handleCopyPrompt(p.prompt)}
                                  >
                                    {copiedPrompt === p.prompt ? (
                                      <><Check className="h-3 w-3 mr-1" /> Copied</>
                                    ) : (
                                      <><Copy className="h-3 w-3 mr-1" /> Copy</>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
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
                        <div className="grid grid-cols-3 gap-3">
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
                            <Label className="text-xs">Intensity</Label>
                            <select
                              value={enhanceIntensity}
                              onChange={(e) => setEnhanceIntensity(e.target.value as typeof enhanceIntensity)}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={isGenerating}
                            >
                              <option value="subtle">Subtle</option>
                              <option value="moderate">Moderate</option>
                              <option value="wild">Wild</option>
                            </select>
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Variations</Label>
                            <select
                              value={enhanceCount}
                              onChange={(e) => setEnhanceCount(parseInt(e.target.value))}
                              className="w-full h-9 px-2 text-sm rounded-md border bg-background"
                              disabled={isGenerating}
                            >
                              <option value={2}>2 each</option>
                              <option value={3}>3 each</option>
                              <option value={5}>5 each</option>
                              <option value={10}>10 each</option>
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
                        <div className="flex gap-2">
                          {recentI2vPrompts.length > 0 && (
                            <Button
                              type="button"
                              variant={showRecentI2v ? "secondary" : "outline"}
                              size="sm"
                              onClick={() => setShowRecentI2v(!showRecentI2v)}
                              disabled={isGenerating}
                            >
                              <History className="h-4 w-4 mr-1" />
                              Recent
                              {showRecentI2v ? (
                                <ChevronUp className="h-3 w-3 ml-1" />
                              ) : (
                                <ChevronDown className="h-3 w-3 ml-1" />
                              )}
                            </Button>
                          )}
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
                            Expand
                          </Button>
                        </div>
                      </CardTitle>
                      <CardDescription>
                        Write one motion per line. Each one will be applied to {bulkMode === 'both' ? 'every photo variation' : 'every photo you uploaded'}.
                      </CardDescription>

                      {/* Recent Prompts Panel */}
                      {showRecentI2v && recentI2vPrompts.length > 0 && (
                        <div className="mt-3 p-3 bg-muted/50 rounded-lg border max-h-64 overflow-y-auto">
                          <p className="text-sm font-medium mb-2">Recently used motions</p>
                          <div className="space-y-2">
                            {recentI2vPrompts.map((p, idx) => (
                              <div key={idx} className="p-2 bg-background rounded border text-sm">
                                <p className="text-foreground mb-2 whitespace-pre-wrap">{p.prompt}</p>
                                <div className="flex gap-2">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="h-7 text-xs"
                                    onClick={() => handleAddRecentPrompt('i2v', p.prompt)}
                                    disabled={bulkI2vPrompts.includes(p.prompt)}
                                  >
                                    <Plus className="h-3 w-3 mr-1" />
                                    {bulkI2vPrompts.includes(p.prompt) ? 'Added' : 'Add'}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 text-xs"
                                    onClick={() => handleCopyPrompt(p.prompt)}
                                  >
                                    {copiedPrompt === p.prompt ? (
                                      <><Check className="h-3 w-3 mr-1" /> Copied</>
                                    ) : (
                                      <><Copy className="h-3 w-3 mr-1" /> Copy</>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
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
                  onCancel={handleCancelPipeline}
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
              <div ref={resultsRef}>
                <BulkResults
                  groups={bulkGroups}
                  totals={bulkTotals}
                  onAnimateSelected={handleAnimateSelectedImages}
                />
              </div>
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

                        {/* FLUX settings - shown for all FLUX models (FLUX.1, FLUX.2, Kontext) */}
                        {(i2iModel === 'flux-general' || i2iModel.startsWith('flux-2') || i2iModel.startsWith('flux-kontext')) && (
                          <div className="p-3 bg-muted/50 rounded-lg border">
                            <button
                              type="button"
                              onClick={() => setShowFluxAdvanced(!showFluxAdvanced)}
                              className="w-full text-sm font-medium flex items-center justify-between"
                            >
                              <div className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4" />
                                {i2iModel.startsWith('flux-2') ? 'FLUX.2 Settings' : i2iModel.startsWith('flux-kontext') ? 'FLUX Kontext Settings' : 'FLUX Settings'}
                                {['flux-2-pro', 'flux-2-max'].includes(i2iModel) && (
                                  <span className="text-xs text-muted-foreground ml-2">(Zero-config model)</span>
                                )}
                              </div>
                              {showFluxAdvanced ? (
                                <ChevronUp className="h-4 w-4 text-muted-foreground" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-muted-foreground" />
                              )}
                            </button>

                            {showFluxAdvanced && (
                              <div className="space-y-4 mt-4 pt-4 border-t">
                            {/* Strength slider - FLUX.1 only */}
                            {i2iModel === 'flux-general' && (
                              <div className="space-y-2">
                                <div className="flex justify-between text-sm">
                                  <Label>Strength (transformation)</Label>
                                  <span className="text-muted-foreground">{fluxStrength.toFixed(2)}</span>
                                </div>
                                <input
                                  type="range"
                                  min="0"
                                  max="1"
                                  step="0.05"
                                  value={fluxStrength}
                                  onChange={(e) => setFluxStrength(parseFloat(e.target.value))}
                                  className="w-full accent-primary"
                                />
                                <p className="text-xs text-muted-foreground">Lower = more original preserved, Higher = more transformation</p>
                              </div>
                            )}

                            {/* Guidance Scale slider - dev, flex, kontext only */}
                            {['flux-general', 'flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) && (
                              <div className="space-y-2">
                                <div className="flex justify-between text-sm">
                                  <Label>Guidance Scale</Label>
                                  <span className="text-muted-foreground">{fluxGuidanceScale.toFixed(1)}</span>
                                </div>
                                <input
                                  type="range"
                                  min="0"
                                  max={i2iModel === 'flux-general' ? 5 : i2iModel === 'flux-2-flex' ? 10 : 20}
                                  step="0.1"
                                  value={fluxGuidanceScale}
                                  onChange={(e) => setFluxGuidanceScale(parseFloat(e.target.value))}
                                  className="w-full accent-primary"
                                />
                                <p className="text-xs text-muted-foreground">
                                  {i2iModel === 'flux-general' && 'How strictly to follow prompt (3-4 recommended)'}
                                  {i2iModel === 'flux-2-dev' && 'Default 2.5, range 0-20'}
                                  {i2iModel === 'flux-2-flex' && 'Default 3.5, range 1.5-10'}
                                  {i2iModel.startsWith('flux-kontext') && 'Default 3.5, range 0-20'}
                                </p>
                              </div>
                            )}

                            {/* Inference Steps slider - dev, flex, kontext only */}
                            {['flux-general', 'flux-2-dev', 'flux-2-flex', 'flux-kontext-dev', 'flux-kontext-pro'].includes(i2iModel) && (
                              <div className="space-y-2">
                                <div className="flex justify-between text-sm">
                                  <Label>Inference Steps</Label>
                                  <span className="text-muted-foreground">{fluxNumInferenceSteps}</span>
                                </div>
                                <input
                                  type="range"
                                  min={i2iModel === 'flux-2-dev' ? 4 : 2}
                                  max="50"
                                  step="1"
                                  value={fluxNumInferenceSteps}
                                  onChange={(e) => setFluxNumInferenceSteps(parseInt(e.target.value))}
                                  className="w-full accent-primary"
                                />
                                <p className="text-xs text-muted-foreground">More steps = higher quality but slower (28 default)</p>
                              </div>
                            )}

                            {/* Seed input - all models */}
                            <div className="space-y-2">
                              <div className="flex justify-between text-sm">
                                <Label>Seed (optional)</Label>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setFluxSeed(null)}
                                  className="h-6 text-xs"
                                >
                                  Random
                                </Button>
                              </div>
                              <input
                                type="number"
                                placeholder="Leave empty for random"
                                value={fluxSeed ?? ''}
                                onChange={(e) => setFluxSeed(e.target.value ? parseInt(e.target.value) : null)}
                                className="w-full h-9 px-3 rounded-md border bg-background text-sm"
                              />
                              <p className="text-xs text-muted-foreground">Same seed = reproducible results</p>
                            </div>

                            {/* Scheduler dropdown - FLUX.1 only */}
                            {i2iModel === 'flux-general' && (
                              <div className="space-y-2">
                                <Label className="text-sm">Scheduler / Sampler</Label>
                                <select
                                  value={fluxScheduler}
                                  onChange={(e) => setFluxScheduler(e.target.value as 'euler' | 'dpmpp_2m')}
                                  className="w-full h-9 px-3 rounded-md border bg-background text-sm"
                                >
                                  <option value="euler">Euler (default, faster)</option>
                                  <option value="dpmpp_2m">DPM++ 2M (higher quality)</option>
                                </select>
                                <p className="text-xs text-muted-foreground">Sampling algorithm for generation</p>
                              </div>
                            )}

                            {/* Acceleration - flux-2-dev only */}
                            {i2iModel === 'flux-2-dev' && (
                              <div className="space-y-2">
                                <Label className="text-sm">Acceleration</Label>
                                <select
                                  value={fluxAcceleration}
                                  onChange={(e) => setFluxAcceleration(e.target.value as 'none' | 'regular' | 'high')}
                                  className="w-full h-9 px-3 rounded-md border bg-background text-sm"
                                >
                                  <option value="none">None (highest quality)</option>
                                  <option value="regular">Regular (balanced)</option>
                                  <option value="high">High (fastest)</option>
                                </select>
                                <p className="text-xs text-muted-foreground">Speed vs quality tradeoff</p>
                              </div>
                            )}

                            {/* Prompt Expansion - dev, flex only */}
                            {['flux-2-dev', 'flux-2-flex'].includes(i2iModel) && (
                              <div className="flex items-center justify-between">
                                <div>
                                  <Label className="text-sm">Prompt Expansion</Label>
                                  <p className="text-xs text-muted-foreground">Auto-enhance prompt for better results</p>
                                </div>
                                <input
                                  type="checkbox"
                                  checked={fluxEnablePromptExpansion}
                                  onChange={(e) => setFluxEnablePromptExpansion(e.target.checked)}
                                  className="h-4 w-4 accent-primary"
                                />
                              </div>
                            )}
                              </div>
                            )}
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

                        {/* Audio checkbox */}
                        <div className="space-y-2">
                          <label className="flex items-center gap-3 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={enableAudio}
                              onChange={(e) => setEnableAudio(e.target.checked)}
                              disabled={!supportsAudio(i2vModel)}
                              className="w-5 h-5 rounded border-2 border-gray-400 accent-primary"
                            />
                            <span className={!supportsAudio(i2vModel) ? 'text-muted-foreground' : ''}>
                              Generate with audio
                            </span>
                          </label>
                          <p className="text-xs text-muted-foreground ml-8">
                            {!supportsAudio(i2vModel)
                              ? 'Only available with Veo models'
                              : enableAudio
                                ? 'Audio ON - costs ~1.5-2x more'
                                : 'Audio OFF'}
                          </p>
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

            {/* Run Name Input */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Run Name</CardTitle>
                <CardDescription>Name your run for easier identification in downloads</CardDescription>
              </CardHeader>
              <CardContent>
                <input
                  type="text"
                  value={runName}
                  onChange={(e) => setRunName(e.target.value)}
                  placeholder="e.g., Beach photoshoot v2"
                  className="w-full h-10 px-3 py-2 text-sm rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                  disabled={isGenerating}
                />
              </CardContent>
            </Card>

            {/* Warning: Generated prompts not added */}
            {generatedPrompts.length > 0 && (bulkMode === 'photos' || bulkMode === 'both') && !generatedPrompts.every(p => bulkI2iPrompts.includes(p)) && (
              <div className="p-3 bg-amber-100 dark:bg-amber-900/30 border border-amber-400 dark:border-amber-600 rounded-lg">
                <p className="text-sm text-amber-800 dark:text-amber-200 font-medium mb-2">
                  You have {generatedPrompts.filter(p => !bulkI2iPrompts.includes(p)).length} generated prompts not added yet
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full border-amber-500 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800"
                  onClick={handleAddGeneratedToI2i}
                >
                  Add to Photo Prompts Now
                </Button>
              </div>
            )}

            {/* Generate Button */}
            <Button
              size="lg"
              className="w-full"
              disabled={!canGenerate}
              onClick={handleGenerateClick}
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

      {/* Confirmation Modal */}
      <ConfirmGenerationModal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        onConfirm={handleConfirmGenerate}
        costEstimate={bulkCostEstimate}
        sourceImageCount={effectiveSourceImages.length}
        bulkMode={bulkMode}
      />
    </div>
  )
}

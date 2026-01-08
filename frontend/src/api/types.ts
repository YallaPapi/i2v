// Video job types
export interface VideoJob {
  id: number
  image_url: string
  motion_prompt: string
  negative_prompt: string | null
  resolution: string
  duration_sec: number
  model: string
  wan_request_id: string | null
  wan_status: 'pending' | 'submitted' | 'running' | 'completed' | 'failed'
  wan_video_url: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface CreateVideoJobRequest {
  image_url: string
  motion_prompt: string
  negative_prompt?: string
  resolution: '480p' | '720p' | '1080p'
  duration_sec: 5 | 10
  model: VideoModel
}

export type VideoModel =
  | 'wan' | 'wan21' | 'wan22' | 'wan-pro'
  | 'kling' | 'kling-master' | 'kling-standard'
  | 'veo2' | 'veo31-fast' | 'veo31' | 'veo31-flf' | 'veo31-fast-flf'
  | 'sora-2' | 'sora-2-pro'
  | 'luma' | 'luma-ray2'

// Image job types
export interface ImageJob {
  id: number
  source_image_url: string
  prompt: string
  negative_prompt: string | null
  model: string
  aspect_ratio: string
  quality: string
  num_images: number
  request_id: string | null
  status: 'pending' | 'submitted' | 'running' | 'completed' | 'failed'
  result_image_urls: string[] | null
  local_image_paths: string[] | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface CreateImageJobRequest {
  source_image_url: string
  prompt: string
  negative_prompt?: string
  model: ImageModel
  aspect_ratio: '1:1' | '9:16' | '16:9' | '4:3' | '3:4'
  quality: 'low' | 'medium' | 'high'
  num_images: 1 | 2 | 3 | 4
}

export type ImageModel =
  | 'gpt-image-1.5'
  | 'kling-image'
  | 'nano-banana-pro'
  | 'nano-banana'
  | 'flux-general'
  // FLUX.2 variants
  | 'flux-2-dev'
  | 'flux-2-pro'
  | 'flux-2-flex'
  | 'flux-2-max'
  // FLUX.1 Kontext (in-context editing)
  | 'flux-kontext-dev'
  | 'flux-kontext-pro'
  // Ideogram
  | 'ideogram-2'

// Helper to check if model is FLUX.2 or Kontext
export const isFlux2Model = (model: string): boolean => {
  return model.startsWith('flux-2') || model.startsWith('flux-kontext')
}

// Per-model feature support (based on fal.ai API docs Jan 2026)
export const FLUX_MODEL_FEATURES = {
  'flux-2-dev': {
    supportsGuidanceScale: true,
    defaultGuidanceScale: 2.5,
    maxGuidanceScale: 20,
    supportsNumSteps: true,
    supportsPromptExpansion: true,
    defaultPromptExpansion: false,
    supportsSafetyTolerance: false,
    supportsAcceleration: true,
    supportsMultiRef: true,
    maxReferences: 4,
  },
  'flux-2-pro': {
    supportsGuidanceScale: false,  // Zero-config
    supportsNumSteps: false,
    supportsPromptExpansion: false,
    supportsSafetyTolerance: true,
    supportsAcceleration: false,
    supportsMultiRef: true,
    maxReferences: 9,
  },
  'flux-2-flex': {
    supportsGuidanceScale: true,
    defaultGuidanceScale: 3.5,
    maxGuidanceScale: 10,
    supportsNumSteps: true,
    supportsPromptExpansion: true,
    defaultPromptExpansion: true,
    supportsSafetyTolerance: true,
    supportsAcceleration: false,
    supportsMultiRef: true,
    maxReferences: 10,
  },
  'flux-2-max': {
    supportsGuidanceScale: false,  // Zero-config
    supportsNumSteps: false,
    supportsPromptExpansion: false,
    supportsSafetyTolerance: true,
    supportsAcceleration: false,
    supportsMultiRef: true,
    maxReferences: 10,
  },
  'flux-kontext-dev': {
    supportsGuidanceScale: true,
    defaultGuidanceScale: 3.5,
    maxGuidanceScale: 20,
    supportsNumSteps: true,
    supportsPromptExpansion: false,
    supportsSafetyTolerance: false,
    supportsAcceleration: false,
    supportsMultiRef: false,  // Single image_url
    maxReferences: 1,
  },
  'flux-kontext-pro': {
    supportsGuidanceScale: true,
    defaultGuidanceScale: 3.5,
    maxGuidanceScale: 20,
    supportsNumSteps: true,
    supportsPromptExpansion: false,
    supportsSafetyTolerance: false,
    supportsAcceleration: false,
    supportsMultiRef: false,
    maxReferences: 1,
  },
} as const

// Helper to get features for a model
export const getFluxFeatures = (model: string) => {
  return FLUX_MODEL_FEATURES[model as keyof typeof FLUX_MODEL_FEATURES] || null
}

// Helper to check if model supports multi-reference
export const supportsMultiRef = (model: string): boolean => {
  const features = getFluxFeatures(model)
  return features?.supportsMultiRef ?? false
}

// Helper to check if model supports guidance scale
export const supportsGuidanceScale = (model: string): boolean => {
  const features = getFluxFeatures(model)
  return features?.supportsGuidanceScale ?? false
}

// Helper to check if model supports safety tolerance
export const supportsSafetyTolerance = (model: string): boolean => {
  const features = getFluxFeatures(model)
  return features?.supportsSafetyTolerance ?? false
}

// FLUX.2 specific parameter types
export interface Flux2Config {
  // FLUX.1 only
  flux_strength?: number  // 0.0-1.0, default 0.75
  flux_scheduler?: 'euler' | 'dpmpp_2m'  // FLUX.1 only
  // FLUX.2 & Kontext (per-model support)
  flux_guidance_scale?: number  // dev/flex/kontext only
  flux_num_inference_steps?: number  // dev/flex/kontext only
  flux_seed?: number
  flux_image_urls?: string[]  // Multi-ref: dev(4), pro(9), flex/max(10)
  flux_output_format?: 'png' | 'jpeg' | 'webp'
  flux_enable_safety_checker?: boolean  // false for NSFW
  flux_enable_prompt_expansion?: boolean  // dev/flex only
  flux_safety_tolerance?: '1' | '2' | '3' | '4' | '5'  // pro/flex/max only ("5" = permissive)
  flux_acceleration?: 'none' | 'regular' | 'high'  // dev only
}

// Model info
export interface ImageModelInfo {
  name: string
  endpoint: string
  pricing: string
  features: string[]
}

export interface HealthResponse {
  status: string
}

// Video model info for display - fal.ai January 2026 pricing (per-second)
export const VIDEO_MODELS: { value: VideoModel; label: string; pricing: string }[] = [
  { value: 'wan', label: 'Wan 2.5', pricing: '$0.05-0.15/s' },
  { value: 'wan21', label: 'Wan 2.1', pricing: '$0.20-0.40/vid' },
  { value: 'wan22', label: 'Wan 2.2', pricing: '$0.04-0.08/s' },
  { value: 'wan-pro', label: 'Wan Pro', pricing: '$0.16/s' },
  { value: 'kling', label: 'Kling v2.5 Turbo', pricing: '$0.07/s' },
  { value: 'kling-master', label: 'Kling v2.1 Master', pricing: '$0.28/s' },
  { value: 'kling-standard', label: 'Kling v2.1 Standard', pricing: '$0.05/s' },
  { value: 'veo2', label: 'Google Veo2', pricing: '$0.50/s' },
  { value: 'veo31-fast', label: 'Google Veo3.1 Fast', pricing: '$0.10/s' },
  { value: 'veo31', label: 'Google Veo3.1', pricing: '$0.20/s' },
  { value: 'veo31-flf', label: 'Veo3.1 First-Last Frame', pricing: '$0.20/s' },
  { value: 'veo31-fast-flf', label: 'Veo3.1 Fast FLF', pricing: '$0.10/s' },
  { value: 'sora-2', label: 'OpenAI Sora 2', pricing: '$0.10/s' },
  { value: 'sora-2-pro', label: 'OpenAI Sora 2 Pro', pricing: '$0.30-0.50/s' },
  { value: 'luma', label: 'Luma Dream Machine', pricing: '$0.032/s' },
  { value: 'luma-ray2', label: 'Luma Ray2', pricing: '$0.05/s' },
]

export const IMAGE_MODELS: { value: ImageModel; label: string; pricing: string }[] = [
  { value: 'gpt-image-1.5', label: 'GPT Image 1.5', pricing: '$0.009-0.20/image' },
  { value: 'kling-image', label: 'Kling Image', pricing: '$0.028/image' },
  { value: 'nano-banana-pro', label: 'Nano Banana Pro', pricing: '$0.15/image' },
  { value: 'nano-banana', label: 'Nano Banana', pricing: '$0.039/image' },
  // FLUX.1 (Legacy)
  { value: 'flux-general', label: 'FLUX 1.0 General', pricing: '$0.025/image' },
  // FLUX.2 Models (Nov 2025)
  { value: 'flux-2-dev', label: 'FLUX.2 Dev', pricing: '$0.025/image' },
  { value: 'flux-2-pro', label: 'FLUX.2 Pro', pricing: '$0.05/image' },
  { value: 'flux-2-flex', label: 'FLUX.2 Flex', pricing: '$0.04/image' },
  { value: 'flux-2-max', label: 'FLUX.2 Max', pricing: '$0.08/image' },
  // FLUX.1 Kontext
  { value: 'flux-kontext-dev', label: 'FLUX Kontext Dev', pricing: '$0.025/image' },
  { value: 'flux-kontext-pro', label: 'FLUX Kontext Pro', pricing: '$0.04/image' },
  // Ideogram
  { value: 'ideogram-2', label: 'Ideogram V2', pricing: '$0.04/image' },
]

export const RESOLUTIONS = [
  { value: '480p', label: '480p' },
  { value: '720p', label: '720p' },
  { value: '1080p', label: '1080p' },
]

export const DURATIONS = [
  { value: '5', label: '5 seconds' },
  { value: '10', label: '10 seconds' },
]

export const ASPECT_RATIOS = [
  { value: '1:1', label: '1:1 (Square)' },
  { value: '9:16', label: '9:16 (Portrait)' },
  { value: '16:9', label: '16:9 (Landscape)' },
  { value: '4:3', label: '4:3' },
  { value: '3:4', label: '3:4' },
]

export const QUALITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

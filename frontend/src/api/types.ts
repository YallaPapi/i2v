// Video provider type - internal only, determined by model
export type VideoProvider = 'fal' | 'vastai'

// ============================================================
// MODEL CATEGORIZATION
// ============================================================
// Open Source (Vast.ai): Wan, CogVideoX, Stable Video Diffusion
// Proprietary (fal.ai): Kling, Veo, Sora, Luma
// ============================================================

// Vast.ai open source video models
export type VastaiVideoModel =
  | 'vastai-wan22-i2v'      // Wan 2.2 I2V 14B (Q4 GGUF) - main model
  | 'vastai-wan22-t2v'      // Wan 2.2 T2V 14B (future)
  | 'vastai-cogvideox'      // CogVideoX-5B (future)
  | 'vastai-svd'            // Stable Video Diffusion (future)

// fal.ai proprietary/cloud video models
export type FalVideoModel =
  | 'wan' | 'wan21' | 'wan22' | 'wan-pro' | 'wan26'
  | 'kling' | 'kling-master' | 'kling-standard' | 'kling26-pro'
  | 'veo2' | 'veo31-fast' | 'veo31' | 'veo31-flf' | 'veo31-fast-flf'
  | 'sora-2' | 'sora-2-pro'
  | 'luma' | 'luma-ray2'
  | 'cogvideox' | 'stable-video'

export type VideoModel = FalVideoModel | VastaiVideoModel

// Helper to check if model runs on Vast.ai
export const isVastaiModel = (model: string): boolean => {
  return model.startsWith('vastai-')
}

// Helper to get provider for a model
export const getProviderForModel = (model: string): VideoProvider => {
  return isVastaiModel(model) ? 'vastai' : 'fal'
}

// Video job types
export interface VideoJob {
  id: number
  image_url: string
  motion_prompt: string
  negative_prompt: string | null
  resolution: string
  duration_sec: number
  model: string
  provider: VideoProvider
  wan_request_id: string | null
  wan_status: 'pending' | 'submitted' | 'running' | 'completed' | 'failed'
  wan_video_url: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

// Vast.ai specific generation parameters
export interface VastaiVideoConfig {
  lora?: string              // LoRA model name (e.g., 'wan2.2_i2v_lightx2v_4steps')
  lora_strength?: number     // LoRA strength 0.0-1.0, default 1.0
  steps?: number             // Inference steps, default 4 (with 4-step LoRA)
  cfg_scale?: number         // CFG scale 1.0-20.0, default 1.0
  frames?: number            // Number of frames (17-81 for Wan 2.2)
  fps?: number               // Output FPS, default 16
  seed?: number              // Random seed for reproducibility
}

export interface CreateVideoJobRequest {
  image_url: string
  motion_prompt: string
  negative_prompt?: string
  resolution: '480p' | '720p' | '1080p'
  duration_sec: 5 | 10
  model: VideoModel
  // Vast.ai specific config (ignored for fal.ai models)
  vastai_config?: VastaiVideoConfig
}

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
  // NSFW Models (vast.ai GPU)
  | 'pony-v6'
  | 'pony-realistic'
  | 'sdxl-base'

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

// Video model info for display
export interface VideoModelInfo {
  value: VideoModel
  label: string
  pricing: string
  provider: VideoProvider
  openSource?: boolean
  description?: string
}

// fal.ai Cloud Models (proprietary + hosted open source)
export const FAL_VIDEO_MODELS: VideoModelInfo[] = [
  { value: 'wan', label: 'Wan 2.5', pricing: '$0.05-0.15/s', provider: 'fal', openSource: true },
  { value: 'wan21', label: 'Wan 2.1', pricing: '$0.20-0.40/vid', provider: 'fal', openSource: true },
  { value: 'wan22', label: 'Wan 2.2', pricing: '$0.04-0.08/s', provider: 'fal', openSource: true },
  { value: 'wan-pro', label: 'Wan Pro', pricing: '$0.16/s', provider: 'fal', openSource: true },
  { value: 'wan26', label: 'Wan 2.6', pricing: '$0.10-0.15/s', provider: 'fal', openSource: true },
  { value: 'kling', label: 'Kling v2.5 Turbo', pricing: '$0.07/s', provider: 'fal' },
  { value: 'kling-master', label: 'Kling v2.1 Master', pricing: '$0.28/s', provider: 'fal' },
  { value: 'kling-standard', label: 'Kling v2.1 Standard', pricing: '$0.05/s', provider: 'fal' },
  { value: 'kling26-pro', label: 'Kling 2.6 Pro', pricing: '$0.07/s', provider: 'fal' },
  { value: 'veo2', label: 'Google Veo2', pricing: '$0.50/s', provider: 'fal' },
  { value: 'veo31-fast', label: 'Google Veo3.1 Fast', pricing: '$0.10/s', provider: 'fal' },
  { value: 'veo31', label: 'Google Veo3.1', pricing: '$0.20/s', provider: 'fal' },
  { value: 'veo31-flf', label: 'Veo3.1 First-Last Frame', pricing: '$0.20/s', provider: 'fal' },
  { value: 'veo31-fast-flf', label: 'Veo3.1 Fast FLF', pricing: '$0.10/s', provider: 'fal' },
  { value: 'sora-2', label: 'OpenAI Sora 2', pricing: '$0.10/s', provider: 'fal' },
  { value: 'sora-2-pro', label: 'OpenAI Sora 2 Pro', pricing: '$0.30-0.50/s', provider: 'fal' },
  { value: 'luma', label: 'Luma Dream Machine', pricing: '$0.032/s', provider: 'fal' },
  { value: 'luma-ray2', label: 'Luma Ray2', pricing: '$0.05/s', provider: 'fal' },
  { value: 'cogvideox', label: 'CogVideoX-5B', pricing: '$0.20/vid', provider: 'fal', openSource: true },
  { value: 'stable-video', label: 'Stable Video Diffusion', pricing: '$0.075/vid', provider: 'fal', openSource: true },
]

// Vast.ai Self-Hosted Models (open source, GPU rental cost only)
export const VASTAI_VIDEO_MODELS: VideoModelInfo[] = [
  {
    value: 'vastai-wan22-i2v',
    label: 'Wan 2.2 I2V (Self-hosted)',
    pricing: '~$0.17/hr GPU',
    provider: 'vastai',
    openSource: true,
    description: 'Wan 2.2 14B Image-to-Video, 4-step LoRA accelerated'
  },
  {
    value: 'vastai-wan22-t2v',
    label: 'Wan 2.2 T2V (Coming Soon)',
    pricing: '~$0.17/hr GPU',
    provider: 'vastai',
    openSource: true,
    description: 'Wan 2.2 14B Text-to-Video'
  },
  {
    value: 'vastai-cogvideox',
    label: 'CogVideoX-5B (Coming Soon)',
    pricing: '~$0.17/hr GPU',
    provider: 'vastai',
    openSource: true,
    description: 'Tsinghua/ZhipuAI open source video model'
  },
  {
    value: 'vastai-svd',
    label: 'Stable Video (Coming Soon)',
    pricing: '~$0.17/hr GPU',
    provider: 'vastai',
    openSource: true,
    description: 'Stability AI Stable Video Diffusion'
  },
]

// Combined list for backward compatibility
export const VIDEO_MODELS: VideoModelInfo[] = [...FAL_VIDEO_MODELS, ...VASTAI_VIDEO_MODELS]

// Available LoRAs for Vast.ai models
export const VASTAI_LORAS = [
  { value: 'wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise', label: '4-Step Accelerator (Recommended)', steps: 4 },
  { value: 'none', label: 'No LoRA (20+ steps)', steps: 20 },
]

// Frame count options for Vast.ai models
export const VASTAI_FRAME_OPTIONS = [
  { value: 17, label: '17 frames (~1s @ 16fps)' },
  { value: 33, label: '33 frames (~2s @ 16fps)' },
  { value: 49, label: '49 frames (~3s @ 16fps)' },
  { value: 65, label: '65 frames (~4s @ 16fps)' },
  { value: 81, label: '81 frames (~5s @ 16fps)' },
]

export const IMAGE_MODELS: { value: ImageModel; label: string; pricing: string; nsfw?: boolean }[] = [
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
  // NSFW Models (vast.ai GPU - open source, GPU compute only)
  { value: 'pony-v6', label: 'Pony V6 XL (NSFW)', pricing: '~$0.005/image', nsfw: true },
  { value: 'pony-realistic', label: 'Pony Realism (NSFW)', pricing: '~$0.005/image', nsfw: true },
  { value: 'sdxl-base', label: 'SDXL Base (NSFW)', pricing: '~$0.004/image', nsfw: true },
]

// Helper to check if model is NSFW (requires vast.ai)
export const isNSFWModel = (model: string): boolean => {
  return ['pony-v6', 'pony-realistic', 'sdxl-base'].includes(model)
}

export const RESOLUTIONS = [
  { value: '480p', label: '480p' },
  { value: '720p', label: '720p' },
  { value: '1080p', label: '1080p' },
]

export const DURATIONS = [
  { value: '5', label: '5 seconds' },
  { value: '10', label: '10 seconds' },
]

// Provider info (for reference, not user selection - provider determined by model)
export const VIDEO_PROVIDERS = [
  { value: 'fal', label: 'fal.ai Cloud', description: 'Pay-per-use cloud API' },
  { value: 'vastai', label: 'Vast.ai Self-hosted', description: 'GPU rental, open source models' },
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

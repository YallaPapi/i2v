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

export type ImageModel = 'gpt-image-1.5' | 'kling-image' | 'nano-banana-pro' | 'nano-banana'

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
]

export const IMAGE_MODELS: { value: ImageModel; label: string; pricing: string }[] = [
  { value: 'gpt-image-1.5', label: 'GPT Image 1.5', pricing: '$0.009-0.20/image' },
  { value: 'kling-image', label: 'Kling Image', pricing: '$0.028/image' },
  { value: 'nano-banana-pro', label: 'Nano Banana Pro', pricing: '$0.15/image' },
  { value: 'nano-banana', label: 'Nano Banana', pricing: '$0.039/image' },
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

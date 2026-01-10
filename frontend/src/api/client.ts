import axios from 'axios'
import type {
  VideoJob,
  CreateVideoJobRequest,
  ImageJob,
  CreateImageJobRequest,
  HealthResponse,
  ImageModelInfo,
} from './types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Health check
export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}

// Video jobs
export async function createVideoJob(request: CreateVideoJobRequest): Promise<VideoJob> {
  const { data } = await api.post<VideoJob>('/jobs', request)
  return data
}

export async function getVideoJob(id: number): Promise<VideoJob> {
  const { data } = await api.get<VideoJob>(`/jobs/${id}`)
  return data
}

export async function listVideoJobs(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<VideoJob[]> {
  const { data } = await api.get<VideoJob[]>('/jobs', { params })
  return data
}

// Image jobs
export async function createImageJob(request: CreateImageJobRequest): Promise<ImageJob> {
  const { data } = await api.post<ImageJob>('/images', request)
  return data
}

export async function getImageJob(id: number): Promise<ImageJob> {
  const { data } = await api.get<ImageJob>(`/images/${id}`)
  return data
}

export async function listImageJobs(params?: {
  status?: string
  model?: string
  limit?: number
  offset?: number
}): Promise<ImageJob[]> {
  const { data } = await api.get<ImageJob[]>('/images', { params })
  return data
}

export async function getImageModels(): Promise<Record<string, ImageModelInfo>> {
  const { data } = await api.get<{ models: Record<string, ImageModelInfo> }>('/images/models')
  return data.models
}

// Pipeline types
export interface PipelineSummary {
  id: number
  name: string
  status: string
  created_at: string
  updated_at: string
  tags: string[] | null
  is_favorite: boolean
  is_hidden: boolean
  output_count: number
  step_count: number
  total_cost: number | null
  first_thumbnail_url: string | null
  model_info: string | null
  first_prompt: string | null
}

export interface PipelineSummaryListResponse {
  pipelines: PipelineSummary[]
  total: number
}

export interface PipelineStep {
  id: number
  step_type: string
  status: string
  config: { model?: string; resolution?: string; duration_sec?: number; quality?: string }
  inputs: { prompts?: string[]; image_urls?: string[] } | null
  outputs: { items?: { url: string; type: string; prompt?: string }[]; thumbnail_urls?: string[] } | null
  cost_actual: number | null
  error_message: string | null
}

export interface PipelineDetails {
  id: number
  name: string
  status: string
  steps: PipelineStep[]
}

// Pipelines
export async function listPipelines(params?: {
  favorites?: boolean
  hidden?: boolean
  tag?: string
  status?: string
  search?: string
  limit?: number
  offset?: number
}): Promise<PipelineSummaryListResponse> {
  const { data } = await api.get<PipelineSummaryListResponse>('/pipelines', { params })
  return data
}

export async function getPipeline(id: number): Promise<PipelineDetails> {
  const { data } = await api.get<PipelineDetails>(`/pipelines/${id}`)
  return data
}

export async function togglePipelineFavorite(id: number): Promise<void> {
  await api.put(`/pipelines/${id}/favorite`)
}

export async function togglePipelineHidden(id: number): Promise<void> {
  await api.put(`/pipelines/${id}/hide`)
}

export async function updatePipelineTags(id: number, tags: string[]): Promise<void> {
  await api.put(`/pipelines/${id}/tags`, tags)
}

export async function cancelPipeline(id: number): Promise<void> {
  await api.post(`/pipelines/${id}/cancel`)
}

// vast.ai GPU video generation (ComfyUI-based)
export interface GPUVideoRequest {
  image_url: string
  prompt: string
  negative_prompt?: string
  num_frames?: number
  steps?: number
  cfg_scale?: number
  seed?: number
  width?: number
  height?: number
}

export interface GPUVideoResponse {
  status: string
  videos: string[]
  images?: string[]
  instance_id: number | null
  gpu_used: string
  params: {
    num_frames: number
    steps: number
    seed: number
  }
}

// ComfyUI-based generation (recommended for vast.ai instances)
export async function generateGPUVideo(request: GPUVideoRequest): Promise<GPUVideoResponse> {
  const { data } = await api.post<GPUVideoResponse>('/vastai/generate-video', request)
  return data
}

// SwarmUI (vast.ai GPU) video generation - for SwarmUI-based instances
export interface SwarmUIVideoRequest {
  image_url: string
  prompt: string
  negative_prompt?: string
  num_frames?: number
  fps?: number
  steps?: number
  cfg_scale?: number
  seed?: number
}

export interface SwarmUIVideoResponse {
  status: string
  video_url: string
  seed: number
  model: string
  frames: number
  instance_id: number | null
  gpu_used: string
}

export async function generateSwarmUIVideo(request: SwarmUIVideoRequest): Promise<SwarmUIVideoResponse> {
  const { data } = await api.post<SwarmUIVideoResponse>('/vastai/swarmui/generate-video', request)
  return data
}

// GPU configuration
export interface GPUConfigRequest {
  comfyui_url?: string
  swarmui_url?: string
  gpu_provider?: 'none' | 'local' | 'vastai'
  vastai_instance_id?: number
}

export interface GPUConfigResponse {
  comfyui_url: string
  comfyui_available: boolean
  swarmui_url: string
  swarmui_available: boolean
  gpu_provider: string
  vastai_instance_id: number | null
}

export async function getGPUConfig(): Promise<GPUConfigResponse> {
  const { data } = await api.get<GPUConfigResponse>('/gpu/config')
  return data
}

export async function setGPUConfig(config: GPUConfigRequest): Promise<GPUConfigResponse> {
  const { data } = await api.post<GPUConfigResponse>('/gpu/config', config)
  return data
}

export async function checkSwarmUIHealth(instanceId: number): Promise<{
  instance_id: number
  status: string
  swarmui_url?: string
  gpu?: string
  error?: string
}> {
  const { data } = await api.get(`/vastai/swarmui/instances/${instanceId}/health`)
  return data
}

export { api }

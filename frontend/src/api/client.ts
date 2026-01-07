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

export { api }

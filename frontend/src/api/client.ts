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

export { api }

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listVideoJobs,
  getVideoJob,
  createVideoJob,
  listImageJobs,
  getImageJob,
  createImageJob,
  checkHealth,
  listPipelines,
  getPipeline,
  togglePipelineFavorite,
  togglePipelineHidden,
  updatePipelineTags,
} from '@/api/client'
import type { CreateVideoJobRequest, CreateImageJobRequest } from '@/api/types'

// Health check
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 30000, // Check every 30 seconds
  })
}

// Video jobs
export function useVideoJobs(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['videoJobs', params],
    queryFn: () => listVideoJobs(params),
    refetchInterval: 5000, // Poll every 5 seconds for status updates
  })
}

export function useVideoJob(id: number) {
  return useQuery({
    queryKey: ['videoJob', id],
    queryFn: () => getVideoJob(id),
    refetchInterval: 3000, // Poll more frequently for single job
  })
}

export function useCreateVideoJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: CreateVideoJobRequest) => createVideoJob(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videoJobs'] })
    },
  })
}

// Image jobs
export function useImageJobs(params?: { status?: string; model?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['imageJobs', params],
    queryFn: () => listImageJobs(params),
    refetchInterval: 5000,
  })
}

export function useImageJob(id: number) {
  return useQuery({
    queryKey: ['imageJob', id],
    queryFn: () => getImageJob(id),
    refetchInterval: 3000,
  })
}

export function useCreateImageJob() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: CreateImageJobRequest) => createImageJob(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['imageJobs'] })
    },
  })
}

// Pipeline jobs (summaries list)
export function usePipelines(params?: {
  favorites?: boolean
  hidden?: boolean
  tag?: string
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ['pipelines', params],
    queryFn: () => listPipelines(params),
    staleTime: 5 * 60 * 1000, // 5 minute cache - data changes rarely
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
  })
}

// Pipeline full details (fetched on-demand when expanding)
export function usePipelineDetails(id: number, enabled: boolean = false) {
  return useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => getPipeline(id),
    enabled, // Only fetch when expanded
    staleTime: 5 * 60 * 1000, // 5 minute cache
  })
}

// Toggle favorite mutation
export function useTogglePipelineFavorite() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => togglePipelineFavorite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
    },
  })
}

// Toggle hidden mutation
export function useTogglePipelineHidden() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => togglePipelineHidden(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
    },
  })
}

// Update tags mutation
export function useUpdatePipelineTags() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, tags }: { id: number; tags: string[] }) => updatePipelineTags(id, tags),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelines'] })
    },
  })
}

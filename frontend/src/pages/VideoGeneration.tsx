import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { FileUpload } from '@/components/ui/file-upload'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useCreateVideoJob, useVideoJobs } from '@/hooks/useJobs'
import { VIDEO_MODELS, RESOLUTIONS, DURATIONS, isSelfHostedModel } from '@/api/types'
import { generateGPUVideo } from '@/api/client'
import type { VideoJob, VideoModel } from '@/api/types'
import { Video, CheckCircle, XCircle, Clock, ExternalLink, Link, Upload } from 'lucide-react'

const videoJobSchema = z.object({
  image_url: z.string().optional(),
  motion_prompt: z.string().min(1, 'Motion prompt is required'),
  negative_prompt: z.string().optional(),
  resolution: z.enum(['480p', '720p', '1080p']),
  duration_sec: z.string(),
  model: z.string(),
})

type VideoJobFormData = z.infer<typeof videoJobSchema>

function getStatusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success"><CheckCircle className="h-3 w-3 mr-1" />Completed</Badge>
    case 'failed':
      return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>
    case 'running':
    case 'submitted':
      return <Badge variant="pending"><Clock className="h-3 w-3 mr-1" />Processing</Badge>
    default:
      return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" />Pending</Badge>
  }
}

export function VideoGeneration() {
  const [selectedModel, setSelectedModel] = useState<VideoModel>('kling')
  const [inputMode, setInputMode] = useState<'url' | 'upload'>('url')
  const [uploadedUrl, setUploadedUrl] = useState<string>('')
  const [gpuResult, setGPUResult] = useState<{ video_url: string; gpu_used: string } | null>(null)
  const createJob = useCreateVideoJob()
  const { data: recentJobs, isLoading: jobsLoading } = useVideoJobs({ limit: 10 })

  // GPU video generation (ComfyUI-based for vast.ai instances)
  const gpuGenerate = useMutation({
    mutationFn: generateGPUVideo,
    onSuccess: (data) => {
      // ComfyUI returns videos array
      const videoUrl = data.videos?.[0] || ''
      setGPUResult({ video_url: videoUrl, gpu_used: data.gpu_used })
    },
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<VideoJobFormData>({
    resolver: zodResolver(videoJobSchema),
    defaultValues: {
      resolution: '1080p',
      duration_sec: '5',
      model: 'kling',
    },
  })

  const onSubmit = async (data: VideoJobFormData) => {
    try {
      const imageUrl = inputMode === 'upload' ? uploadedUrl : data.image_url
      if (!imageUrl) {
        return
      }

      // Check if using GPU (self-hosted on vast.ai)
      if (isSelfHostedModel(data.model)) {
        setGPUResult(null)
        await gpuGenerate.mutateAsync({
          image_url: imageUrl,
          prompt: data.motion_prompt,
          negative_prompt: data.negative_prompt,
          num_frames: 81,  // ~3.4s at 24fps
          steps: 4,        // LightX2V fast
          cfg_scale: 1.0,
          width: 832,      // Wan 2.2 optimal resolution
          height: 480,
        })
        reset()
        setUploadedUrl('')
        return
      }

      // Cloud models (fal.ai)
      await createJob.mutateAsync({
        image_url: imageUrl,
        motion_prompt: data.motion_prompt,
        negative_prompt: data.negative_prompt,
        resolution: data.resolution,
        duration_sec: parseInt(data.duration_sec, 10) as 5 | 10,
        model: data.model as VideoModel,
      })
      reset()
      setUploadedUrl('')
    } catch (error) {
      console.error('Failed to create job:', error)
    }
  }

  const isGenerating = createJob.isPending || gpuGenerate.isPending

  const modelInfo = VIDEO_MODELS.find((m) => m.value === selectedModel)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Video Generation</h1>
        <p className="text-muted-foreground">
          Create AI-powered videos from images using state-of-the-art models
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Video className="h-5 w-5" />
              New Video Job
            </CardTitle>
            <CardDescription>
              Configure your image-to-video generation settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label>Source Image</Label>
                <Tabs value={inputMode} onValueChange={(v) => setInputMode(v as 'url' | 'upload')}>
                  <TabsList className="w-full">
                    <TabsTrigger value="url" className="flex-1">
                      <Link className="h-4 w-4 mr-2" />
                      URL
                    </TabsTrigger>
                    <TabsTrigger value="upload" className="flex-1">
                      <Upload className="h-4 w-4 mr-2" />
                      Upload
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="url">
                    <Input
                      id="image_url"
                      placeholder="https://example.com/image.jpg"
                      {...register('image_url')}
                    />
                    {errors.image_url && inputMode === 'url' && (
                      <p className="text-sm text-destructive mt-1">{errors.image_url.message}</p>
                    )}
                  </TabsContent>
                  <TabsContent value="upload">
                    <FileUpload
                      onUpload={(url) => setUploadedUrl(url)}
                      disabled={isGenerating}
                    />
                    {uploadedUrl && (
                      <p className="text-xs text-green-600 mt-1">Image uploaded successfully</p>
                    )}
                  </TabsContent>
                </Tabs>
              </div>

              <div className="space-y-2">
                <Label htmlFor="motion_prompt">Motion Prompt</Label>
                <Textarea
                  id="motion_prompt"
                  placeholder="Describe the motion and camera movement..."
                  rows={3}
                  {...register('motion_prompt')}
                />
                {errors.motion_prompt && (
                  <p className="text-sm text-destructive">{errors.motion_prompt.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="negative_prompt">Negative Prompt (Optional)</Label>
                <Textarea
                  id="negative_prompt"
                  placeholder="Things to avoid in the video..."
                  rows={2}
                  {...register('negative_prompt')}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Select
                    id="model"
                    options={VIDEO_MODELS.map((m) => ({ value: m.value, label: m.label }))}
                    {...register('model', {
                      onChange: (e) => setSelectedModel(e.target.value as VideoModel),
                    })}
                  />
                  {modelInfo && (
                    <p className="text-xs text-muted-foreground">{modelInfo.pricing}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="resolution">Resolution</Label>
                  <Select
                    id="resolution"
                    options={RESOLUTIONS}
                    {...register('resolution')}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="duration_sec">Duration</Label>
                <Select
                  id="duration_sec"
                  options={DURATIONS}
                  {...register('duration_sec')}
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    {isSelfHostedModel(selectedModel) ? 'Generating on GPU...' : 'Creating Job...'}
                  </>
                ) : (
                  isSelfHostedModel(selectedModel) ? 'Generate on GPU (5090)' : 'Create Video Job'
                )}
              </Button>

              {(createJob.isError || gpuGenerate.isError) && (
                <p className="text-sm text-destructive text-center">
                  Failed to generate. {gpuGenerate.error?.message || 'Please try again.'}
                </p>
              )}

              {createJob.isSuccess && (
                <p className="text-sm text-green-600 text-center">
                  Job created successfully! ID: {createJob.data?.id}
                </p>
              )}

              {gpuResult && (
                <div className="border rounded-lg p-4 bg-green-50 space-y-2">
                  <p className="text-sm font-medium text-green-800">
                    Video generated on {gpuResult.gpu_used}!
                  </p>
                  <a
                    href={gpuResult.video_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-sm text-blue-600 hover:underline"
                  >
                    <ExternalLink className="h-3 w-3 mr-1" />
                    View Video
                  </a>
                </div>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Recent Jobs */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Video Jobs</CardTitle>
            <CardDescription>Your latest video generation requests</CardDescription>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : recentJobs && recentJobs.length > 0 ? (
              <div className="space-y-4">
                {recentJobs.map((job: VideoJob) => (
                  <div key={job.id} className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">Job #{job.id}</p>
                        <p className="text-xs text-muted-foreground">
                          {job.model} • {job.resolution} • {job.duration_sec}s
                        </p>
                      </div>
                      {getStatusBadge(job.wan_status)}
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {job.motion_prompt}
                    </p>
                    {job.wan_video_url && (
                      <a
                        href={job.wan_video_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-sm text-blue-600 hover:underline"
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        View Video
                      </a>
                    )}
                    {job.error_message && (
                      <p className="text-xs text-destructive">{job.error_message}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No video jobs yet. Create your first one!
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

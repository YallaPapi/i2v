import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
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
import { Switch } from '@/components/ui/switch'
import { useCreateVideoJob, useVideoJobs } from '@/hooks/useJobs'
import {
  FAL_VIDEO_MODELS,
  VASTAI_VIDEO_MODELS,
  RESOLUTIONS,
  DURATIONS,
  VASTAI_LORAS,
  LORA_SET_MAP,
  VASTAI_FRAME_OPTIONS,
  isVastaiModel,
} from '@/api/types'
import type { VideoJob, VideoModel, VastaiVideoConfig } from '@/api/types'
import { Video, CheckCircle, XCircle, Clock, ExternalLink, Link, Upload, Cpu, Cloud } from 'lucide-react'

const videoJobSchema = z.object({
  image_url: z.string().optional(),
  motion_prompt: z.string().min(1, 'Motion prompt is required'),
  negative_prompt: z.string().optional(),
  resolution: z.enum(['480p', '720p', '1080p']),
  duration_sec: z.string(),
  model: z.string(),
  // Vast.ai specific fields
  vastai_lora: z.string().optional(),
  vastai_steps: z.number().optional(),
  vastai_cfg: z.number().optional(),
  vastai_frames: z.number().optional(),
  // FPS randomization for batch variety
  vastai_fps_randomize: z.boolean().optional(),
  // Post-processing options
  vastai_caption: z.string().optional(),
  vastai_apply_spoof: z.boolean().optional(),
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
  const [selectedModel, setSelectedModel] = useState<VideoModel>('vastai-wan22-remix-i2v')
  const [inputMode, setInputMode] = useState<'url' | 'upload'>('url')
  const [uploadedUrl, setUploadedUrl] = useState<string>('')
  const createJob = useCreateVideoJob()
  const { data: recentJobs, isLoading: jobsLoading } = useVideoJobs({ limit: 10 })

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
    setValue,
  } = useForm<VideoJobFormData>({
    resolver: zodResolver(videoJobSchema),
    defaultValues: {
      resolution: '720p',   // 720p default for Vast.ai (9:16 portrait)
      duration_sec: '5',
      model: 'vastai-wan22-remix-i2v',  // Default to Vast.ai model
      vastai_lora: 'seko',  // Seko 4-step Lightning LoRA
      vastai_steps: 5,      // 5 video steps with Seko LoRA
      vastai_cfg: 1.0,
      vastai_frames: 81,    // ~5 seconds at 16fps
      vastai_fps_randomize: false,  // Fixed FPS by default
      vastai_caption: '',   // No caption by default
      vastai_apply_spoof: false,  // Spoof disabled by default
    },
  })

  const watchedModel = watch('model')
  const isVastai = isVastaiModel(watchedModel)

  const onSubmit = async (data: VideoJobFormData) => {
    try {
      const imageUrl = inputMode === 'upload' ? uploadedUrl : data.image_url
      if (!imageUrl) {
        return
      }

      // Build vastai_config if using Vast.ai model
      const loraSet = data.vastai_lora && data.vastai_lora !== 'none'
        ? LORA_SET_MAP[data.vastai_lora]
        : undefined
      const vastaiConfig: VastaiVideoConfig | undefined = isVastaiModel(data.model) ? {
        lora_high: loraSet?.high,
        lora_low: loraSet?.low,
        lora_strength: 1.0,
        steps: data.vastai_steps,
        cfg_scale: data.vastai_cfg,
        frames: data.vastai_frames,
        fps: 16,  // Base FPS (ignored if fps_randomize is true)
        fps_randomize: data.vastai_fps_randomize || false,  // Randomize 14-18 FPS for variety
        // Post-processing options
        caption: data.vastai_caption || undefined,
        apply_spoof: data.vastai_apply_spoof || false,
      } : undefined

      await createJob.mutateAsync({
        image_url: imageUrl,
        motion_prompt: data.motion_prompt,
        negative_prompt: data.negative_prompt,
        resolution: data.resolution,
        duration_sec: parseInt(data.duration_sec, 10) as 5 | 10,
        model: data.model as VideoModel,
        vastai_config: vastaiConfig,
      })
      reset()
      setUploadedUrl('')
    } catch (error) {
      console.error('Failed to create job:', error)
    }
  }

  const isGenerating = createJob.isPending

  // Get model info from combined list
  const allModels = [...FAL_VIDEO_MODELS, ...VASTAI_VIDEO_MODELS]
  const modelInfo = allModels.find((m) => m.value === selectedModel)

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

              {/* Model Selection - Single dropdown with Vast.ai at TOP */}
              <div className="space-y-2">
                <Label htmlFor="model">Video Model</Label>
                <Select
                  id="model"
                  options={[
                    // Vast.ai Self-hosted models FIRST (at top)
                    ...VASTAI_VIDEO_MODELS.filter(m => !m.label.includes('Coming Soon')).map((m) => ({
                      value: m.value,
                      label: `⚡ ${m.label} (${m.pricing})`,
                    })),
                    // fal.ai Cloud models below
                    ...FAL_VIDEO_MODELS.map((m) => ({
                      value: m.value,
                      label: `☁️ ${m.label} (${m.pricing})`,
                    })),
                  ]}
                  {...register('model', {
                    onChange: (e) => setSelectedModel(e.target.value as VideoModel),
                  })}
                />
                {modelInfo && (
                  <p className="text-xs text-muted-foreground">
                    {isVastai ? '⚡ Self-hosted on Vast.ai GPU' : '☁️ Cloud via fal.ai'} — {modelInfo.description || modelInfo.pricing}
                  </p>
                )}
              </div>

              {/* Vast.ai Specific Parameters - shown only when Vast.ai model selected */}
              {isVastai && (
                <div className="space-y-4 p-4 border rounded-lg bg-muted/30">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Cpu className="h-4 w-4" />
                    Vast.ai Generation Settings
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="vastai_lora">LoRA Accelerator</Label>
                      <Select
                        id="vastai_lora"
                        options={VASTAI_LORAS.map((l) => ({
                          value: l.value,
                          label: l.label,
                        }))}
                        {...register('vastai_lora')}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="vastai_frames">Frame Count</Label>
                      <Select
                        id="vastai_frames"
                        options={VASTAI_FRAME_OPTIONS.map((f) => ({
                          value: f.value.toString(),
                          label: f.label,
                        }))}
                        {...register('vastai_frames', { valueAsNumber: true })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="vastai_steps">Inference Steps</Label>
                      <Input
                        id="vastai_steps"
                        type="number"
                        min={1}
                        max={50}
                        {...register('vastai_steps', { valueAsNumber: true })}
                      />
                      <p className="text-xs text-muted-foreground">4 with LoRA, 20+ without</p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="vastai_cfg">CFG Scale</Label>
                      <Input
                        id="vastai_cfg"
                        type="number"
                        min={1}
                        max={20}
                        step={0.1}
                        {...register('vastai_cfg', { valueAsNumber: true })}
                      />
                      <p className="text-xs text-muted-foreground">1.0 recommended</p>
                    </div>
                  </div>

                  {/* Post-processing Options */}
                  <div className="space-y-4 pt-2 border-t">
                    <p className="text-sm font-medium text-muted-foreground">Post-processing</p>

                    <div className="space-y-2">
                      <Label htmlFor="vastai_caption">Caption Overlay (Optional)</Label>
                      <Input
                        id="vastai_caption"
                        placeholder="Text to overlay on video..."
                        {...register('vastai_caption')}
                      />
                      <p className="text-xs text-muted-foreground">Adds text caption to the output video</p>
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="vastai_fps_randomize">Randomize FPS</Label>
                        <p className="text-xs text-muted-foreground">Vary FPS (14-18) for batch variety</p>
                      </div>
                      <Switch
                        id="vastai_fps_randomize"
                        checked={watch('vastai_fps_randomize') || false}
                        onCheckedChange={(checked) => setValue('vastai_fps_randomize', checked)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label htmlFor="vastai_apply_spoof">Apply Spoof</Label>
                        <p className="text-xs text-muted-foreground">Apply spoofing transforms to output</p>
                      </div>
                      <Switch
                        id="vastai_apply_spoof"
                        checked={watch('vastai_apply_spoof') || false}
                        onCheckedChange={(checked) => setValue('vastai_apply_spoof', checked)}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="resolution">Resolution</Label>
                  <Select
                    id="resolution"
                    options={RESOLUTIONS}
                    {...register('resolution')}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="duration_sec">Duration</Label>
                  <Select
                    id="duration_sec"
                    options={DURATIONS}
                    {...register('duration_sec')}
                  />
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Creating Job...
                  </>
                ) : (
                  'Create Video Job'
                )}
              </Button>

              {createJob.isError && (
                <p className="text-sm text-destructive text-center">
                  Failed to create job. Please try again.
                </p>
              )}

              {createJob.isSuccess && (
                <p className="text-sm text-green-600 text-center">
                  Job created successfully! ID: {createJob.data?.id}
                </p>
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
                          {job.model} • {job.resolution} • {job.duration_sec}s • {job.provider === 'vastai' ? 'Vast.ai' : 'fal.ai'}
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

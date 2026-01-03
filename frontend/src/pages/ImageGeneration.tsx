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
import { useCreateImageJob, useImageJobs } from '@/hooks/useJobs'
import { IMAGE_MODELS, ASPECT_RATIOS, QUALITY_OPTIONS } from '@/api/types'
import type { ImageJob, ImageModel } from '@/api/types'
import { Image as ImageIcon, CheckCircle, XCircle, Clock, ExternalLink, Link, Upload } from 'lucide-react'

const imageJobSchema = z.object({
  source_image_url: z.string().optional(),
  prompt: z.string().min(1, 'Prompt is required'),
  negative_prompt: z.string().optional(),
  model: z.string(),
  aspect_ratio: z.enum(['1:1', '9:16', '16:9', '4:3', '3:4']),
  quality: z.enum(['low', 'medium', 'high']),
  num_images: z.string(),
})

type ImageJobFormData = z.infer<typeof imageJobSchema>

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

export function ImageGeneration() {
  const [selectedModel, setSelectedModel] = useState<ImageModel>('gpt-image-1.5')
  const [inputMode, setInputMode] = useState<'url' | 'upload'>('url')
  const [uploadedUrl, setUploadedUrl] = useState<string>('')
  const createJob = useCreateImageJob()
  const { data: recentJobs, isLoading: jobsLoading } = useImageJobs({ limit: 10 })

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ImageJobFormData>({
    resolver: zodResolver(imageJobSchema),
    defaultValues: {
      model: 'gpt-image-1.5',
      aspect_ratio: '9:16',
      quality: 'high',
      num_images: '1',
    },
  })

  const onSubmit = async (data: ImageJobFormData) => {
    try {
      const sourceUrl = inputMode === 'upload' ? uploadedUrl : data.source_image_url
      if (!sourceUrl) {
        return
      }
      await createJob.mutateAsync({
        source_image_url: sourceUrl,
        prompt: data.prompt,
        negative_prompt: data.negative_prompt,
        model: data.model as ImageModel,
        aspect_ratio: data.aspect_ratio,
        quality: data.quality,
        num_images: parseInt(data.num_images, 10) as 1 | 2 | 3 | 4,
      })
      reset()
      setUploadedUrl('')
    } catch (error) {
      console.error('Failed to create job:', error)
    }
  }

  const modelInfo = IMAGE_MODELS.find((m) => m.value === selectedModel)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Image Generation</h1>
        <p className="text-muted-foreground">
          Create and edit images using AI-powered models
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              New Image Job
            </CardTitle>
            <CardDescription>
              Configure your image generation or editing settings
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
                      id="source_image_url"
                      placeholder="https://example.com/image.jpg"
                      {...register('source_image_url')}
                    />
                    {errors.source_image_url && inputMode === 'url' && (
                      <p className="text-sm text-destructive mt-1">{errors.source_image_url.message}</p>
                    )}
                  </TabsContent>
                  <TabsContent value="upload">
                    <FileUpload
                      onUpload={(url) => setUploadedUrl(url)}
                      disabled={createJob.isPending}
                    />
                    {uploadedUrl && (
                      <p className="text-xs text-green-600 mt-1">Image uploaded successfully</p>
                    )}
                  </TabsContent>
                </Tabs>
              </div>

              <div className="space-y-2">
                <Label htmlFor="prompt">Prompt</Label>
                <Textarea
                  id="prompt"
                  placeholder="Describe the image you want to generate or the edits to make..."
                  rows={3}
                  {...register('prompt')}
                />
                {errors.prompt && (
                  <p className="text-sm text-destructive">{errors.prompt.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="negative_prompt">Negative Prompt (Optional)</Label>
                <Textarea
                  id="negative_prompt"
                  placeholder="Things to avoid in the image..."
                  rows={2}
                  {...register('negative_prompt')}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Select
                    id="model"
                    options={IMAGE_MODELS.map((m) => ({ value: m.value, label: m.label }))}
                    {...register('model', {
                      onChange: (e) => setSelectedModel(e.target.value as ImageModel),
                    })}
                  />
                  {modelInfo && (
                    <p className="text-xs text-muted-foreground">{modelInfo.pricing}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="aspect_ratio">Aspect Ratio</Label>
                  <Select
                    id="aspect_ratio"
                    options={ASPECT_RATIOS}
                    {...register('aspect_ratio')}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="quality">Quality</Label>
                  <Select
                    id="quality"
                    options={QUALITY_OPTIONS}
                    {...register('quality')}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="num_images">Number of Images</Label>
                  <Select
                    id="num_images"
                    options={[
                      { value: '1', label: '1' },
                      { value: '2', label: '2' },
                      { value: '3', label: '3' },
                      { value: '4', label: '4' },
                    ]}
                    {...register('num_images')}
                  />
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={createJob.isPending}
              >
                {createJob.isPending ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Creating Job...
                  </>
                ) : (
                  'Create Image Job'
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
            <CardTitle>Recent Image Jobs</CardTitle>
            <CardDescription>Your latest image generation requests</CardDescription>
          </CardHeader>
          <CardContent>
            {jobsLoading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : recentJobs && recentJobs.length > 0 ? (
              <div className="space-y-4">
                {recentJobs.map((job: ImageJob) => (
                  <div key={job.id} className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">Job #{job.id}</p>
                        <p className="text-xs text-muted-foreground">
                          {job.model} • {job.aspect_ratio} • {job.num_images} image(s)
                        </p>
                      </div>
                      {getStatusBadge(job.status)}
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {job.prompt}
                    </p>
                    {job.result_image_urls && job.result_image_urls.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {job.result_image_urls.map((url, idx) => (
                          <a
                            key={idx}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-sm text-blue-600 hover:underline"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            Image {idx + 1}
                          </a>
                        ))}
                      </div>
                    )}
                    {job.error_message && (
                      <p className="text-xs text-destructive">{job.error_message}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No image jobs yet. Create your first one!
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

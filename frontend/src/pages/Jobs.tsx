import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { Select } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useVideoJobs, useImageJobs } from '@/hooks/useJobs'
import type { VideoJob, ImageJob } from '@/api/types'
import { Video, Image as ImageIcon, CheckCircle, XCircle, Clock, ExternalLink, RefreshCw } from 'lucide-react'

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

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString()
}

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export function Jobs() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialType = searchParams.get('type') === 'image' ? 'image' : 'video'
  const [activeTab, setActiveTab] = useState(initialType)
  const [statusFilter, setStatusFilter] = useState('')

  const {
    data: videoJobs,
    isLoading: videoLoading,
    refetch: refetchVideo,
  } = useVideoJobs({
    status: statusFilter || undefined,
    limit: 100,
  })

  const {
    data: imageJobs,
    isLoading: imageLoading,
    refetch: refetchImage,
  } = useImageJobs({
    status: statusFilter || undefined,
    limit: 100,
  })

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    setSearchParams({ type: value })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">All Jobs</h1>
          <p className="text-muted-foreground">
            View and manage all your generation jobs
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="w-48">
            <Select
              options={STATUS_OPTIONS}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            />
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => {
              refetchVideo()
              refetchImage()
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="video" className="flex items-center gap-2">
            <Video className="h-4 w-4" />
            Video Jobs ({videoJobs?.length ?? 0})
          </TabsTrigger>
          <TabsTrigger value="image" className="flex items-center gap-2">
            <ImageIcon className="h-4 w-4" />
            Image Jobs ({imageJobs?.length ?? 0})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="video">
          <Card>
            <CardHeader>
              <CardTitle>Video Generation Jobs</CardTitle>
              <CardDescription>All your image-to-video generation requests</CardDescription>
            </CardHeader>
            <CardContent>
              {videoLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : videoJobs && videoJobs.length > 0 ? (
                <div className="space-y-4">
                  {videoJobs.map((job: VideoJob) => (
                    <div key={job.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-4">
                          <div>
                            <p className="font-medium">Job #{job.id}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(job.created_at)}
                            </p>
                          </div>
                          <Badge variant="outline">{job.model}</Badge>
                          <span className="text-sm text-muted-foreground">
                            {job.resolution} • {job.duration_sec}s
                          </span>
                        </div>
                        {getStatusBadge(job.wan_status)}
                      </div>
                      <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                        {job.motion_prompt}
                      </p>
                      <div className="flex items-center gap-4">
                        {job.image_url && (
                          <a
                            href={job.image_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex items-center"
                          >
                            <ImageIcon className="h-3 w-3 mr-1" />
                            Source Image
                          </a>
                        )}
                        {job.wan_video_url && (
                          <a
                            href={job.wan_video_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex items-center"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            View Video
                          </a>
                        )}
                      </div>
                      {job.error_message && (
                        <p className="text-xs text-destructive mt-2">{job.error_message}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No video jobs found.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="image">
          <Card>
            <CardHeader>
              <CardTitle>Image Generation Jobs</CardTitle>
              <CardDescription>All your image generation and editing requests</CardDescription>
            </CardHeader>
            <CardContent>
              {imageLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner />
                </div>
              ) : imageJobs && imageJobs.length > 0 ? (
                <div className="space-y-4">
                  {imageJobs.map((job: ImageJob) => (
                    <div key={job.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-4">
                          <div>
                            <p className="font-medium">Job #{job.id}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(job.created_at)}
                            </p>
                          </div>
                          <Badge variant="outline">{job.model}</Badge>
                          <span className="text-sm text-muted-foreground">
                            {job.aspect_ratio} • {job.quality} • {job.num_images} image(s)
                          </span>
                        </div>
                        {getStatusBadge(job.status)}
                      </div>
                      <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                        {job.prompt}
                      </p>
                      <div className="flex items-center gap-4 flex-wrap">
                        {job.source_image_url && (
                          <a
                            href={job.source_image_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex items-center"
                          >
                            <ImageIcon className="h-3 w-3 mr-1" />
                            Source Image
                          </a>
                        )}
                        {job.result_image_urls && job.result_image_urls.map((url, idx) => (
                          <a
                            key={idx}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex items-center"
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            Result {idx + 1}
                          </a>
                        ))}
                      </div>
                      {job.error_message && (
                        <p className="text-xs text-destructive mt-2">{job.error_message}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No image jobs found.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

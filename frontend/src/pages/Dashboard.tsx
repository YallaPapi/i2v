import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { useVideoJobs, useImageJobs } from '@/hooks/useJobs'
import { Video, Image, Clock, CheckCircle, XCircle, ArrowRight } from 'lucide-react'
import type { VideoJob, ImageJob } from '@/api/types'

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

function truncatePrompt(prompt: string, maxLength = 50) {
  return prompt.length > maxLength ? prompt.substring(0, maxLength) + '...' : prompt
}

export function Dashboard() {
  const { data: videoJobs, isLoading: videoLoading } = useVideoJobs({ limit: 5 })
  const { data: imageJobs, isLoading: imageLoading } = useImageJobs({ limit: 5 })

  const stats = {
    totalVideos: videoJobs?.length ?? 0,
    completedVideos: videoJobs?.filter((j: VideoJob) => j.wan_status === 'completed').length ?? 0,
    processingVideos: videoJobs?.filter((j: VideoJob) => ['pending', 'submitted', 'running'].includes(j.wan_status)).length ?? 0,
    totalImages: imageJobs?.length ?? 0,
    completedImages: imageJobs?.filter((j: ImageJob) => j.status === 'completed').length ?? 0,
    processingImages: imageJobs?.filter((j: ImageJob) => ['pending', 'submitted', 'running'].includes(j.status)).length ?? 0,
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your AI generation jobs
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Video Generation</CardTitle>
            <Video className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalVideos} jobs</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedVideos} completed, {stats.processingVideos} processing
            </p>
            <Link to="/video">
              <Button className="mt-4 w-full">
                Create Video <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Image Generation</CardTitle>
            <Image className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalImages} jobs</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedImages} completed, {stats.processingImages} processing
            </p>
            <Link to="/image">
              <Button className="mt-4 w-full">
                Create Image <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Recent Jobs */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Video Jobs */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Video Jobs</CardTitle>
            <CardDescription>Latest video generation requests</CardDescription>
          </CardHeader>
          <CardContent>
            {videoLoading ? (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            ) : videoJobs && videoJobs.length > 0 ? (
              <div className="space-y-4">
                {videoJobs.slice(0, 5).map((job: VideoJob) => (
                  <div key={job.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">{truncatePrompt(job.motion_prompt)}</p>
                      <p className="text-xs text-muted-foreground">
                        {job.model} • {job.resolution} • {job.duration_sec}s
                      </p>
                    </div>
                    {getStatusBadge(job.wan_status)}
                  </div>
                ))}
                <Link to="/jobs?type=video">
                  <Button variant="ghost" className="w-full">
                    View all video jobs <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No video jobs yet. Create your first one!
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recent Image Jobs */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Image Jobs</CardTitle>
            <CardDescription>Latest image generation requests</CardDescription>
          </CardHeader>
          <CardContent>
            {imageLoading ? (
              <div className="flex justify-center py-4">
                <Spinner />
              </div>
            ) : imageJobs && imageJobs.length > 0 ? (
              <div className="space-y-4">
                {imageJobs.slice(0, 5).map((job: ImageJob) => (
                  <div key={job.id} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div className="space-y-1">
                      <p className="text-sm font-medium">{truncatePrompt(job.prompt)}</p>
                      <p className="text-xs text-muted-foreground">
                        {job.model} • {job.aspect_ratio} • {job.num_images} image(s)
                      </p>
                    </div>
                    {getStatusBadge(job.status)}
                  </div>
                ))}
                <Link to="/jobs?type=image">
                  <Button variant="ghost" className="w-full">
                    View all image jobs <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No image jobs yet. Create your first one!
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

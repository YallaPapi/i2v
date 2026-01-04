import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown, Download, Image, Video, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SourceGroup {
  source_image: string
  source_index: number
  i2i_outputs: string[]
  i2v_outputs: string[]
}

interface BulkResultsProps {
  groups: SourceGroup[]
  totals: {
    source_images: number
    i2i_generated: number
    i2v_generated: number
    total_cost: number
  }
}

export function BulkResults({ groups, totals }: BulkResultsProps) {
  const [openGroups, setOpenGroups] = useState<Set<number>>(new Set([0]))

  const toggleGroup = (index: number) => {
    const newOpen = new Set(openGroups)
    if (newOpen.has(index)) {
      newOpen.delete(index)
    } else {
      newOpen.add(index)
    }
    setOpenGroups(newOpen)
  }

  const downloadAll = async () => {
    // Collect all URLs
    const allUrls = groups.flatMap(g => [...g.i2i_outputs, ...g.i2v_outputs])
    for (const url of allUrls) {
      window.open(url, '_blank')
    }
  }

  const downloadGroupVideos = (group: SourceGroup) => {
    for (const url of group.i2v_outputs) {
      window.open(url, '_blank')
    }
  }

  if (groups.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Results</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1">
              <Image className="h-3 w-3" />
              {totals.i2i_generated}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <Video className="h-3 w-3" />
              {totals.i2v_generated}
            </Badge>
            {totals.total_cost > 0 && (
              <Badge variant="secondary">
                ${totals.total_cost.toFixed(2)}
              </Badge>
            )}
            <Button size="sm" variant="outline" onClick={downloadAll}>
              <Download className="h-4 w-4 mr-1" />
              Download All
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {groups.map((group, idx) => (
          <Collapsible
            key={idx}
            open={openGroups.has(idx)}
            onOpenChange={() => toggleGroup(idx)}
          >
            <div className="border rounded-lg">
              <CollapsibleTrigger className="w-full">
                <div className="flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors">
                  {/* Source Thumbnail */}
                  <img
                    src={group.source_image}
                    alt={`Source ${idx + 1}`}
                    className="w-12 h-12 object-cover rounded"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect fill="%23f0f0f0" width="24" height="24"/></svg>'
                    }}
                  />

                  <div className="flex-1 text-left">
                    <p className="font-medium">Source {idx + 1}</p>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      {group.i2i_outputs.length > 0 && (
                        <span>{group.i2i_outputs.length} images</span>
                      )}
                      {group.i2v_outputs.length > 0 && (
                        <span>{group.i2v_outputs.length} videos</span>
                      )}
                    </div>
                  </div>

                  <ChevronDown
                    className={cn(
                      "h-5 w-5 transition-transform",
                      openGroups.has(idx) && "rotate-180"
                    )}
                  />
                </div>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="p-3 pt-0 space-y-4">
                  {/* I2I Outputs */}
                  {group.i2i_outputs.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Image className="h-4 w-4" />
                        Image Variations
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        {group.i2i_outputs.map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="relative aspect-[9/16] rounded overflow-hidden border group"
                          >
                            <img
                              src={url}
                              alt={`Variation ${i + 1}`}
                              className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <ExternalLink className="h-5 w-5 text-white" />
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* I2V Outputs */}
                  {group.i2v_outputs.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Video className="h-4 w-4" />
                          Videos
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => downloadGroupVideos(group)}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          Download
                        </Button>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        {group.i2v_outputs.map((url, i) => (
                          <div
                            key={i}
                            className="relative aspect-[9/16] rounded overflow-hidden border bg-black"
                          >
                            <video
                              src={url}
                              className="w-full h-full object-cover"
                              controls
                              muted
                              loop
                              playsInline
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        ))}
      </CardContent>
    </Card>
  )
}

export type { SourceGroup }

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'
import {
  LayoutTemplate,
  Search,
  Sparkles,
  Image as ImageIcon,
  Video,
  LayoutGrid,
  Star,
  Lock,
  AlertCircle,
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

// Types
interface Template {
  id: string
  name: string
  description: string | null
  category: string
  output_type: string
  base_prompt: string
  recommended_model: string | null
  tier_required: string
  is_nsfw: boolean
  is_featured: boolean
  usage_count: number
  tags: string[]
}

interface TemplatesResponse {
  templates: Template[]
  total: number
}

// Category display config
const CATEGORIES = [
  { id: '', label: 'All', icon: LayoutGrid },
  { id: 'social_sfw', label: 'Social SFW', icon: ImageIcon },
  { id: 'nsfw', label: 'NSFW', icon: Lock },
  { id: 'brainrot', label: 'Brainrot', icon: Sparkles },
  { id: 'carousel', label: 'Carousel', icon: LayoutGrid },
]

const OUTPUT_TYPES = [
  { id: '', label: 'All Types' },
  { id: 'image', label: 'Image' },
  { id: 'video', label: 'Video' },
  { id: 'carousel', label: 'Carousel' },
]

const TIER_ORDER: Record<string, number> = {
  free: 0,
  starter: 1,
  pro: 2,
  agency: 3,
}

export function Templates() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [outputType, setOutputType] = useState('')
  const [showFeatured, setShowFeatured] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)

  // Fetch templates
  const { data, isLoading, error } = useQuery({
    queryKey: ['templates', category, outputType, showFeatured, search],
    queryFn: async () => {
      const params: Record<string, string | boolean> = {}
      if (category) params.category = category
      if (outputType) params.output_type = outputType
      if (showFeatured) params.featured = true
      if (search) params.search = search

      const { data } = await api.get<TemplatesResponse>('/templates', { params })
      return data
    },
  })

  // Check if user can access template tier
  const canAccessTier = (requiredTier: string) => {
    if (!user) return requiredTier === 'free'
    const userLevel = TIER_ORDER[user.tier] ?? 0
    const requiredLevel = TIER_ORDER[requiredTier] ?? 0
    return userLevel >= requiredLevel
  }

  // Get output type icon
  const getOutputIcon = (type: string) => {
    switch (type) {
      case 'image': return ImageIcon
      case 'video': return Video
      case 'carousel': return LayoutGrid
      default: return ImageIcon
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <LayoutTemplate className="h-6 w-6" />
            Templates
          </h1>
          <p className="text-muted-foreground mt-1">
            Browse and select content generation templates
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search templates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={cn(
              "w-full rounded-md border bg-background pl-9 pr-3 py-2 text-sm",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              "placeholder:text-muted-foreground"
            )}
          />
        </div>

        {/* Category pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon
            return (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium whitespace-nowrap",
                  "transition-colors",
                  category === cat.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {cat.label}
              </button>
            )
          })}
        </div>

        {/* Output type filter */}
        <select
          value={outputType}
          onChange={(e) => setOutputType(e.target.value)}
          className={cn(
            "rounded-md border bg-background px-3 py-2 text-sm",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          )}
        >
          {OUTPUT_TYPES.map((type) => (
            <option key={type.id} value={type.id}>
              {type.label}
            </option>
          ))}
        </select>

        {/* Featured toggle */}
        <button
          onClick={() => setShowFeatured(!showFeatured)}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium",
            "transition-colors",
            showFeatured
              ? "bg-amber-100 text-amber-700"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
        >
          <Star className={cn("h-4 w-4", showFeatured && "fill-current")} />
          Featured
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 p-4 flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-destructive" />
          <p className="text-sm text-destructive">Failed to load templates. Please try again.</p>
        </div>
      )}

      {/* Templates grid */}
      {data && (
        <>
          <div className="text-sm text-muted-foreground">
            {data.total} template{data.total !== 1 ? 's' : ''} found
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data.templates.map((template) => {
              const OutputIcon = getOutputIcon(template.output_type)
              const isLocked = !canAccessTier(template.tier_required)

              return (
                <div
                  key={template.id}
                  onClick={() => setSelectedTemplate(template)}
                  className={cn(
                    "relative rounded-lg border p-4 cursor-pointer transition-all",
                    "hover:border-primary hover:shadow-md",
                    selectedTemplate?.id === template.id && "border-primary ring-2 ring-primary/20",
                    isLocked && "opacity-60"
                  )}
                >
                  {/* Featured badge */}
                  {template.is_featured && (
                    <div className="absolute -top-2 -right-2">
                      <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
                    </div>
                  )}

                  {/* Locked overlay */}
                  {isLocked && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/50 rounded-lg">
                      <div className="flex items-center gap-1.5 text-sm font-medium">
                        <Lock className="h-4 w-4" />
                        {template.tier_required} tier
                      </div>
                    </div>
                  )}

                  {/* Header */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <OutputIcon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground capitalize">
                        {template.output_type}
                      </span>
                    </div>
                    {template.is_nsfw && (
                      <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                        NSFW
                      </span>
                    )}
                  </div>

                  {/* Name */}
                  <h3 className="font-medium mb-1">{template.name}</h3>

                  {/* Description */}
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                    {template.description || 'No description'}
                  </p>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1 mb-2">
                    {template.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="text-xs bg-muted px-1.5 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                    {template.tags.length > 3 && (
                      <span className="text-xs text-muted-foreground">
                        +{template.tags.length - 3}
                      </span>
                    )}
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                    <span>{template.recommended_model || 'Any model'}</span>
                    <span>{template.usage_count} uses</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Empty state */}
          {data.templates.length === 0 && (
            <div className="text-center py-12">
              <LayoutTemplate className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-1">No templates found</h3>
              <p className="text-muted-foreground">
                Try adjusting your filters or search query.
              </p>
            </div>
          )}
        </>
      )}

      {/* Template detail modal/sidebar could go here */}
      {selectedTemplate && (
        <div className="fixed inset-y-0 right-0 w-full max-w-md bg-background border-l shadow-xl z-50 overflow-y-auto">
          <div className="p-6 space-y-4">
            <div className="flex items-start justify-between">
              <h2 className="text-xl font-bold">{selectedTemplate.name}</h2>
              <button
                onClick={() => setSelectedTemplate(null)}
                className="p-1 rounded-md hover:bg-muted"
              >
                <span className="sr-only">Close</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <p className="text-muted-foreground">{selectedTemplate.description}</p>

            <div className="space-y-3">
              <div>
                <span className="text-sm font-medium">Category:</span>
                <span className="ml-2 text-sm text-muted-foreground capitalize">
                  {selectedTemplate.category.replace('_', ' ')}
                </span>
              </div>
              <div>
                <span className="text-sm font-medium">Output Type:</span>
                <span className="ml-2 text-sm text-muted-foreground capitalize">
                  {selectedTemplate.output_type}
                </span>
              </div>
              <div>
                <span className="text-sm font-medium">Recommended Model:</span>
                <span className="ml-2 text-sm text-muted-foreground">
                  {selectedTemplate.recommended_model || 'Any'}
                </span>
              </div>
              <div>
                <span className="text-sm font-medium">Required Tier:</span>
                <span className="ml-2 text-sm text-muted-foreground capitalize">
                  {selectedTemplate.tier_required}
                </span>
              </div>
            </div>

            <div>
              <span className="text-sm font-medium">Base Prompt:</span>
              <pre className="mt-1 p-3 rounded-md bg-muted text-xs whitespace-pre-wrap">
                {selectedTemplate.base_prompt}
              </pre>
            </div>

            <div className="flex flex-wrap gap-1">
              {selectedTemplate.tags.map((tag) => (
                <span key={tag} className="text-xs bg-muted px-2 py-1 rounded">
                  {tag}
                </span>
              ))}
            </div>

            <button
              onClick={() => {
                // TODO: Navigate to playground with template selected
                alert(`Use template: ${selectedTemplate.id}`)
              }}
              disabled={!canAccessTier(selectedTemplate.tier_required)}
              className={cn(
                "w-full rounded-md px-4 py-2 text-sm font-medium",
                "bg-primary text-primary-foreground hover:bg-primary/90",
                "disabled:opacity-50 disabled:cursor-not-allowed"
              )}
            >
              {canAccessTier(selectedTemplate.tier_required) ? 'Use Template' : `Requires ${selectedTemplate.tier_required} tier`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

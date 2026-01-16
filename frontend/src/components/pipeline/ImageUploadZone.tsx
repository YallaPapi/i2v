import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { cn } from '@/lib/utils'
import { Upload, X, Link, Loader2, FolderArchive } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

// Polyfill for crypto.randomUUID() - not available in non-secure contexts (HTTP)
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback for non-secure contexts
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

interface UploadedImage {
  id: string
  url: string
  preview: string
  name: string
  source: 'upload' | 'url'
}

interface ImageUploadZoneProps {
  images: UploadedImage[]
  onImagesChange: (images: UploadedImage[]) => void
  multiple?: boolean
  maxFiles?: number
  disabled?: boolean
  className?: string
}

export function ImageUploadZone({
  images,
  onImagesChange,
  multiple = true,
  maxFiles = 50,
  disabled = false,
  className,
}: ImageUploadZoneProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({ completed: 0, total: 0 })
  const [urlInput, setUrlInput] = useState('')
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadFile = async (file: File): Promise<{ image: UploadedImage | null; error?: string }> => {
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
        return { image: null, error: errorData.detail || `Upload failed: ${response.status}` }
      }

      const data = await response.json()
      return {
        image: {
          id: generateUUID(),
          url: data.url,
          preview: URL.createObjectURL(file),
          name: file.name,
          source: 'upload',
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      console.error('Upload error:', err)
      return { image: null, error: `Upload failed: ${message}. Is the backend running?` }
    }
  }

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (disabled) return
    setError(null)
    setIsUploading(true)

    const filesToUpload = acceptedFiles.slice(0, maxFiles - images.length)
    setUploadProgress({ completed: 0, total: filesToUpload.length })

    try {
      const successfulUploads: UploadedImage[] = []
      const errors: string[] = []

      // Upload files sequentially to track progress
      for (let i = 0; i < filesToUpload.length; i++) {
        const result = await uploadFile(filesToUpload[i])
        if (result.image) {
          successfulUploads.push(result.image)
        } else if (result.error) {
          errors.push(result.error)
        }
        setUploadProgress({ completed: i + 1, total: filesToUpload.length })
      }

      if (errors.length > 0) {
        setError(errors[0] || 'Some files failed to upload')
      }

      onImagesChange([...images, ...successfulUploads])
    } finally {
      setIsUploading(false)
      setUploadProgress({ completed: 0, total: 0 })
    }
  }, [images, maxFiles, disabled, onImagesChange])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.webp'],
    },
    multiple,
    maxFiles: maxFiles - images.length,
    disabled: disabled || isUploading,
  })

  const addFromUrl = async () => {
    if (!urlInput.trim()) return
    setError(null)

    try {
      // Validate URL
      new URL(urlInput)

      const newImage: UploadedImage = {
        id: generateUUID(),
        url: urlInput,
        preview: urlInput,
        name: urlInput.split('/').pop() || 'image',
        source: 'url',
      }

      onImagesChange([...images, newImage])
      setUrlInput('')
      setShowUrlInput(false)
    } catch {
      setError('Invalid URL')
    }
  }

  const removeImage = (id: string) => {
    onImagesChange(images.filter(img => img.id !== id))
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Upload Zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all",
          isDragActive ? "border-primary bg-primary/5 scale-[1.02]" : "border-muted-foreground/25 hover:border-primary/50",
          (disabled || isUploading) && "opacity-50 cursor-not-allowed",
          images.length > 0 && "p-4"
        )}
      >
        <input {...getInputProps()} />

        {isUploading ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
            <div className="text-center">
              <p className="text-sm text-muted-foreground">
                Uploading {uploadProgress.completed} of {uploadProgress.total} images...
              </p>
              {uploadProgress.total > 0 && (
                <div className="w-48 h-2 bg-muted rounded-full mt-2 overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${(uploadProgress.completed / uploadProgress.total) * 100}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        ) : images.length === 0 ? (
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-primary/10 rounded-full">
                <Upload className="h-8 w-8 text-primary" />
              </div>
              <div className="p-3 bg-muted rounded-full">
                <FolderArchive className="h-8 w-8 text-muted-foreground" />
              </div>
            </div>
            <div>
              <p className="text-lg font-medium">Drop images here</p>
              <p className="text-sm text-muted-foreground">
                or click to browse. Supports JPG, PNG, WebP
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Upload className="h-5 w-5" />
            <span>Drop more images or click to add</span>
          </div>
        )}
      </div>

      {/* URL Input Toggle */}
      {!showUrlInput ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setShowUrlInput(true)}
          disabled={disabled}
        >
          <Link className="h-4 w-4 mr-2" />
          Add from URL
        </Button>
      ) : (
        <div className="flex gap-2">
          <Input
            placeholder="https://example.com/image.jpg"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addFromUrl()}
          />
          <Button type="button" onClick={addFromUrl}>Add</Button>
          <Button type="button" variant="ghost" onClick={() => setShowUrlInput(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Image Previews */}
      {images.length > 0 && (
        <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
          {images.map((image) => (
            <div
              key={image.id}
              className="relative aspect-square rounded-lg overflow-hidden border bg-muted group"
            >
              <img
                src={image.preview}
                alt={image.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect fill="%23f0f0f0" width="24" height="24"/><text x="50%" y="50%" text-anchor="middle" dy=".3em" font-size="8" fill="%23999">?</text></svg>'
                }}
              />
              <button
                type="button"
                onClick={() => removeImage(image.id)}
                className="absolute top-1 right-1 p-1 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="h-3 w-3 text-white" />
              </button>
              {image.source === 'url' && (
                <div className="absolute bottom-1 left-1">
                  <Link className="h-3 w-3 text-white drop-shadow" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Image Count */}
      {images.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {images.length} image{images.length !== 1 ? 's' : ''} selected
          {maxFiles < Infinity && ` (max ${maxFiles})`}
        </p>
      )}
    </div>
  )
}

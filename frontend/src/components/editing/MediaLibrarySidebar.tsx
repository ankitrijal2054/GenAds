import React, { useState, useRef } from 'react'
import { Upload, Video, Music, X, Loader2, GripVertical } from 'lucide-react'
import { Button } from '@/components/ui'
import { useEditorStore, type TimelineClip } from '@/stores/editorStore'
import { formatDuration } from '@/utils/formatters'

interface MediaLibrarySidebarProps {
  isOpen: boolean
  onClose: () => void
  campaign?: any
}

/**
 * Media Library Sidebar Component
 * Shows all available media (scenes, music, uploaded files) as a list
 * Users can drag items from library to timeline
 */
export const MediaLibrarySidebar: React.FC<MediaLibrarySidebarProps> = ({
  isOpen,
  onClose,
  campaign
}) => {
  const { mediaLibrary, addToMediaLibrary, addClipToTrack } = useEditorStore()
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [draggedItem, setDraggedItem] = useState<TimelineClip | null>(null)
  const videoInputRef = useRef<HTMLInputElement>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('video/')) {
      setUploadError('Please select a valid video file')
      return
    }

    await uploadMedia(file, 'video')
  }

  const handleAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('audio/')) {
      setUploadError('Please select a valid audio file')
      return
    }

    await uploadMedia(file, 'audio')
  }

  const uploadMedia = async (file: File, type: 'video' | 'audio') => {
    setIsUploading(true)
    setUploadProgress(0)
    setUploadError(null)

    try {
      // Create a media element to get duration
      const url = URL.createObjectURL(file)
      const mediaElement = type === 'video' 
        ? document.createElement('video')
        : document.createElement('audio')
      
      mediaElement.src = url
      mediaElement.preload = 'metadata'

      await new Promise((resolve, reject) => {
        mediaElement.onloadedmetadata = () => resolve(null)
        mediaElement.onerror = reject
        setTimeout(() => reject(new Error('Timeout loading media metadata')), 10000)
      })

      const duration = mediaElement.duration || 30
      URL.revokeObjectURL(url)

      // Create clip for media library
      const clipId = `uploaded-${type}-${Date.now()}`
      const clip: TimelineClip = {
        id: clipId,
        libraryId: clipId,
        name: file.name,
        trackType: type,
        duration: duration,
        trimStart: 0,
        trimEnd: duration,
        effectiveDuration: duration,
        position: 0, // Will be set when added to timeline
        ...(type === 'video' 
          ? { videoUrl: url } 
          : { audioUrl: url }
        )
      }

      // Add to media library (not directly to timeline)
      addToMediaLibrary(clip)

      // Store clip source
      const store = useEditorStore.getState()
      store.setClipSource(clipId, url)

      setUploadProgress(100)
      
      // Reset input
      if (type === 'video' && videoInputRef.current) {
        videoInputRef.current.value = ''
      }
      if (type === 'audio' && audioInputRef.current) {
        audioInputRef.current.value = ''
      }
    } catch (err: any) {
      console.error('Upload error:', err)
      setUploadError(err?.message || `Failed to upload ${type} file`)
    } finally {
      setIsUploading(false)
      setTimeout(() => setUploadProgress(0), 2000)
    }
  }

  // Handle drag start
  const handleDragStart = (e: React.DragEvent, item: TimelineClip) => {
    setDraggedItem(item)
    e.dataTransfer.effectAllowed = 'copy'
    e.dataTransfer.setData('application/json', JSON.stringify(item))
  }

  // Handle drag end
  const handleDragEnd = () => {
    setDraggedItem(null)
  }

  // Group media by type
  const videoItems = mediaLibrary.filter(item => item.trackType === 'video')
  const audioItems = mediaLibrary.filter(item => item.trackType === 'audio')

  if (!isOpen) return null

  return (
    <div className="fixed right-0 top-[73px] h-[calc(100vh-73px)] w-80 bg-charcoal-900 border-l border-gray-700 z-[100] flex flex-col shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold text-white">Media Library</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Upload Section */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
            <Upload className="w-4 h-4" />
            <span>Upload Media</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="border-2 border-dashed border-gray-600 rounded-lg p-3 text-center hover:border-accent-gold transition-colors cursor-pointer">
              <input
                ref={videoInputRef}
                type="file"
                accept="video/*"
                onChange={handleVideoUpload}
                className="hidden"
                id="video-upload"
                disabled={isUploading}
              />
              <label
                htmlFor="video-upload"
                className="cursor-pointer flex flex-col items-center gap-1"
              >
                <Video className="w-5 h-5 text-gray-400" />
                <span className="text-xs text-gray-400">Video</span>
              </label>
            </div>
            <div className="border-2 border-dashed border-gray-600 rounded-lg p-3 text-center hover:border-accent-gold transition-colors cursor-pointer">
              <input
                ref={audioInputRef}
                type="file"
                accept="audio/*"
                onChange={handleAudioUpload}
                className="hidden"
                id="audio-upload"
                disabled={isUploading}
              />
              <label
                htmlFor="audio-upload"
                className="cursor-pointer flex flex-col items-center gap-1"
              >
                <Music className="w-5 h-5 text-gray-400" />
                <span className="text-xs text-gray-400">Audio</span>
              </label>
            </div>
          </div>
        </div>

        {/* Upload Progress */}
        {isUploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm text-gray-400">
              <span>Uploading...</span>
              <span>{Math.round(uploadProgress)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className="bg-accent-gold h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Error */}
        {uploadError && (
          <div className="p-3 bg-red-900/20 border border-red-700 rounded-lg">
            <p className="text-sm text-red-400">{uploadError}</p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUploadError(null)}
              className="mt-2 text-red-400 hover:text-red-300"
            >
              Dismiss
            </Button>
          </div>
        )}

        {/* Video Items */}
        {videoItems.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
              <Video className="w-4 h-4" />
              <span>Videos ({videoItems.length})</span>
            </div>
            <div className="space-y-2">
              {videoItems.map((item) => (
                <div
                  key={item.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, item)}
                  onDragEnd={handleDragEnd}
                  className={`p-3 bg-charcoal-800 rounded-lg border border-gray-700 cursor-move hover:border-accent-gold transition-colors ${
                    draggedItem?.id === item.id ? 'opacity-50' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <GripVertical className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{item.name}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {formatDuration(item.duration)}
                      </p>
                    </div>
                    <Video className="w-4 h-4 text-gray-500 flex-shrink-0" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Audio Items */}
        {audioItems.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
              <Music className="w-4 h-4" />
              <span>Audio ({audioItems.length})</span>
            </div>
            <div className="space-y-2">
              {audioItems.map((item) => (
                <div
                  key={item.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, item)}
                  onDragEnd={handleDragEnd}
                  className={`p-3 bg-charcoal-800 rounded-lg border border-gray-700 cursor-move hover:border-accent-gold transition-colors ${
                    draggedItem?.id === item.id ? 'opacity-50' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <GripVertical className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white truncate">{item.name}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {formatDuration(item.duration)}
                      </p>
                    </div>
                    <Music className="w-4 h-4 text-gray-500 flex-shrink-0" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {mediaLibrary.length === 0 && !isUploading && (
          <div className="text-center py-8">
            <p className="text-sm text-gray-400">No media in library</p>
            <p className="text-xs text-gray-500 mt-1">Upload files to get started</p>
          </div>
        )}

        {/* Info Section */}
        <div className="mt-8 p-4 bg-charcoal-800 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-300 mb-2">How to Use</h3>
          <ul className="text-xs text-gray-400 space-y-1">
            <li>• Drag items from library to timeline</li>
            <li>• Upload new files to add to library</li>
            <li>• All scenes and music are available here</li>
            <li>• Maximum file size: 100MB</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

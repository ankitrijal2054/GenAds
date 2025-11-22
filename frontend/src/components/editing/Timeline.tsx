import React, { useRef, useEffect, useState } from 'react'
import { useTimelineClips, useEditorStore, useTimelinePlayback } from '@/stores/editorStore'
import { TimelineClip } from './TimelineClip'
import { ZoomIn, ZoomOut } from 'lucide-react'
import { formatDuration } from '@/utils/formatters'

const DEFAULT_PIXELS_PER_SECOND = 0.5
const ZOOM_MIN = 0.1
const ZOOM_MAX = 10
const ZOOM_STEP = 0.1
const TRACK_HEADER_WIDTH = 110

/**
 * Helper to format time as MM:SS or HH:MM:SS
 */
const formatTime = (seconds: number): string => {
  return formatDuration(seconds)
}

/**
 * Calculate time marker interval based on zoom level
 */
const getTimeMarkerInterval = (zoomLevel: number): number => {
  if (zoomLevel <= 0.5) return 600 // 10 min
  if (zoomLevel <= 1) return 300 // 5 min
  if (zoomLevel <= 2) return 120 // 2 min
  if (zoomLevel <= 5) return 60 // 1 min
  return 30 // 30 sec at high zoom
}

/**
 * Generate time markers
 */
const generateTimeMarkers = (duration: number, interval: number): number[] => {
  const markers: number[] = []
  for (let time = 0; time <= duration; time += interval) {
    markers.push(time)
  }
  return markers
}

/**
 * Main Timeline Component
 */
export const Timeline: React.FC = () => {
  const { timelineVideoClips, timelineAudioClips, selectedClipId } = useTimelineClips()
  const { selectTimelineClip, splitClip, removeClipFromTrack, moveClip } = useEditorStore()
  const timelinePlayback = useTimelinePlayback()
  
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const playheadRef = useRef<HTMLDivElement>(null)
  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  
  // Calculate duration and pixels per second
  const calculateDuration = (): number => {
    const videoDuration = timelineVideoClips.reduce(
      (max, clip) => Math.max(max, clip.position + clip.effectiveDuration),
      0
    )
    const audioDuration = timelineAudioClips.reduce(
      (max, clip) => Math.max(max, clip.position + clip.effectiveDuration),
      0
    )
    return Math.max(videoDuration, audioDuration, 60) // Minimum 1 minute
  }
  
  const totalDuration = calculateDuration()
  const pixelsPerSecond = DEFAULT_PIXELS_PER_SECOND * zoomLevel
  const contentWidth = totalDuration * pixelsPerSecond
  const timelineWidth = Math.max(contentWidth, 1400)
  const timeMarkerInterval = getTimeMarkerInterval(zoomLevel)
  const timeMarkers = generateTimeMarkers(totalDuration, timeMarkerInterval)
  
  // Handle playhead area click to seek
  const handlePlayheadAreaClick = (e: React.MouseEvent<HTMLDivElement>): void => {
    if (!scrollContainerRef.current) return
    const rect = scrollContainerRef.current.getBoundingClientRect()
    const clickX = e.clientX - rect.left + scrollContainerRef.current.scrollLeft
    const timeX = clickX - TRACK_HEADER_WIDTH
    const time = Math.max(0, timeX / pixelsPerSecond)
    timelinePlayback.seek(Math.max(0, Math.min(time, totalDuration)))
  }
  
  // Handle playhead drag
  const handlePlayheadMouseDown = (e: React.MouseEvent<HTMLDivElement>): void => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingPlayhead(true)
  }
  
  useEffect(() => {
    if (!isDraggingPlayhead) return
    
    const handleMouseMove = (e: MouseEvent): void => {
      if (!scrollContainerRef.current) return
      const rect = scrollContainerRef.current.getBoundingClientRect()
      const clientX = e.clientX
      
      let clickX: number
      if (clientX < rect.left) {
        clickX = 0
      } else if (clientX > rect.right) {
        clickX = scrollContainerRef.current.scrollWidth
      } else {
        clickX = clientX - rect.left + scrollContainerRef.current.scrollLeft
      }
      
      const timeX = clickX - TRACK_HEADER_WIDTH
      const time = Math.max(0, timeX / pixelsPerSecond)
      timelinePlayback.seek(Math.max(0, Math.min(time, totalDuration)))
    }
    
    const handleMouseUp = (): void => {
      setIsDraggingPlayhead(false)
    }
    
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingPlayhead, pixelsPerSecond, totalDuration, timelinePlayback])
  
  // Handle zoom
  const handleZoomIn = (): void => {
    setZoomLevel((prev) => Math.min(prev + ZOOM_STEP, ZOOM_MAX))
  }
  
  const handleZoomOut = (): void => {
    setZoomLevel((prev) => Math.max(prev - ZOOM_STEP, ZOOM_MIN))
  }
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key === 's' || e.key === 'S') {
        if (selectedClipId) {
          e.preventDefault()
          splitClip(selectedClipId, timelinePlayback.currentTime)
        }
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedClipId) {
          e.preventDefault()
          const isInVideoTrack = timelineVideoClips.some((c) => c.id === selectedClipId)
          const trackType = isInVideoTrack ? 'video' : 'audio'
          removeClipFromTrack(trackType, selectedClipId)
        }
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedClipId, timelinePlayback.currentTime, timelineVideoClips, splitClip, removeClipFromTrack])
  
  const playheadPixelPosition = TRACK_HEADER_WIDTH + timelinePlayback.currentTime * pixelsPerSecond
  
  return (
    <div className="flex flex-col h-full bg-gray-900 border-t border-gray-700">
      {/* Zoom Controls */}
      <div className="flex items-center justify-between p-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            className="p-1 text-gray-400 hover:text-white disabled:opacity-50"
            disabled={zoomLevel <= ZOOM_MIN}
            title="Zoom out"
          >
            <ZoomOut size={16} />
          </button>
          <span className="text-sm text-gray-400">{Math.round(zoomLevel * 100)}%</span>
          <button
            onClick={handleZoomIn}
            className="p-1 text-gray-400 hover:text-white disabled:opacity-50"
            disabled={zoomLevel >= ZOOM_MAX}
            title="Zoom in"
          >
            <ZoomIn size={16} />
          </button>
        </div>
        <div className="text-xs text-gray-500">
          Playhead: {formatTime(timelinePlayback.currentTime)} / {formatTime(totalDuration)}
        </div>
      </div>
      
      {/* Timeline Scroll Container */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-x-auto overflow-y-hidden relative"
        style={{ height: '200px' }}
      >
        {/* Header with Time Markers */}
        <div
          className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700"
          style={{ width: `${timelineWidth}px`, minWidth: '100%' }}
          onClick={handlePlayheadAreaClick}
        >
          <div className="flex">
            <div style={{ width: `${TRACK_HEADER_WIDTH}px` }} className="border-r border-gray-700" />
            <div className="flex-1 relative h-8">
              {timeMarkers.map((time) => (
                <div
                  key={time}
                  className="absolute top-0 bottom-0 flex flex-col items-center"
                  style={{ left: `${time * pixelsPerSecond}px` }}
                >
                  <div className="w-px h-full bg-gray-600" />
                  <span className="text-xs text-gray-400 mt-1">{formatTime(time)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Playhead */}
        <div
          ref={playheadRef}
          className="absolute top-0 bottom-0 w-0.5 bg-red-500 z-20 pointer-events-none"
          style={{
            left: `${playheadPixelPosition}px`,
          }}
        >
          <div
            className="absolute top-0 left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-red-500"
            onMouseDown={handlePlayheadMouseDown}
            style={{ cursor: 'ew-resize', pointerEvents: 'all' }}
          />
        </div>
        
        {/* Video Track */}
        <div className="relative border-b border-gray-700" style={{ height: '80px' }}>
          <div className="flex h-full">
            <div
              className="flex items-center justify-center border-r border-gray-700 bg-gray-800 text-sm text-gray-400 font-medium"
              style={{ width: `${TRACK_HEADER_WIDTH}px` }}
            >
              Video
            </div>
            <div className="flex-1 relative" style={{ width: `${timelineWidth - TRACK_HEADER_WIDTH}px` }}>
              {timelineVideoClips.map((clip) => (
                <TimelineClip
                  key={clip.id}
                  clip={clip}
                  isSelected={selectedClipId === clip.id}
                  onSelect={() => selectTimelineClip(clip.id)}
                  pixelsPerSecond={pixelsPerSecond}
                  trackType="video"
                />
              ))}
            </div>
          </div>
        </div>
        
        {/* Audio Track */}
        <div className="relative" style={{ height: '80px' }}>
          <div className="flex h-full">
            <div
              className="flex items-center justify-center border-r border-gray-700 bg-gray-800 text-sm text-gray-400 font-medium"
              style={{ width: `${TRACK_HEADER_WIDTH}px` }}
            >
              Audio
            </div>
            <div className="flex-1 relative" style={{ width: `${timelineWidth - TRACK_HEADER_WIDTH}px` }}>
              {timelineAudioClips.map((clip) => (
                <TimelineClip
                  key={clip.id}
                  clip={clip}
                  isSelected={selectedClipId === clip.id}
                  onSelect={() => selectTimelineClip(clip.id)}
                  pixelsPerSecond={pixelsPerSecond}
                  trackType="audio"
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


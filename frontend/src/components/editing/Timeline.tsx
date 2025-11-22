import React, { useRef, useEffect, useState } from 'react'
import { useTimelineClips, useEditorStore, useTimelinePlayback, type TimelineClip } from '@/stores/editorStore'
import { TimelineClip as TimelineClipComponent } from './TimelineClip'
import { ZoomIn, ZoomOut, Volume2, VolumeX } from 'lucide-react'
import { formatDuration } from '@/utils/formatters'

// Base viewport width for timeline content (excluding header)
const TIMELINE_VIEWPORT_WIDTH = 1200
// Default duration to show in viewport at 0% zoom (2 minutes)
const DEFAULT_VIEWPORT_DURATION = 120 // 2 minutes in seconds
// Calculate base pixels per second so 2 minutes fills viewport at zoom level 1
const BASE_PIXELS_PER_SECOND = TIMELINE_VIEWPORT_WIDTH / DEFAULT_VIEWPORT_DURATION

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
  const { selectTimelineClip, splitClip, removeClipFromTrack, moveClip, addClipToTrack, toggleTrackMute, isMuted } = useEditorStore()
  const timelinePlayback = useTimelinePlayback()
  
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const playheadRef = useRef<HTMLDivElement>(null)
  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [viewportWidth, setViewportWidth] = useState(TIMELINE_VIEWPORT_WIDTH)
  const [dragOverTrack, setDragOverTrack] = useState<'video' | 'audio' | null>(null)
  const [playheadDragTime, setPlayheadDragTime] = useState<number | null>(null)
  const playheadDragTimeRef = useRef<number | null>(null)
  
  // Update viewport width when container resizes
  useEffect(() => {
    const updateViewportWidth = () => {
      if (scrollContainerRef.current) {
        const width = scrollContainerRef.current.clientWidth - TRACK_HEADER_WIDTH
        if (width > 0) {
          setViewportWidth(width)
        }
      }
    }
    
    updateViewportWidth()
    const resizeObserver = new ResizeObserver(updateViewportWidth)
    if (scrollContainerRef.current) {
      resizeObserver.observe(scrollContainerRef.current)
    }
    
    return () => resizeObserver.disconnect()
  }, [])
  
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
    return Math.max(videoDuration, audioDuration, 120) // Minimum 2 minutes (default)
  }
  
  const totalDuration = calculateDuration()
  // Calculate pixels per second: at zoom level 1, 2 minutes should fill viewport
  // Recalculate base pixels per second based on actual viewport width
  const basePixelsPerSecond = viewportWidth / DEFAULT_VIEWPORT_DURATION
  const pixelsPerSecond = basePixelsPerSecond * zoomLevel
  // Content width is based on actual content duration
  const contentWidth = totalDuration * pixelsPerSecond
  // Timeline width should be at least the viewport width (2 minutes), or content width if larger
  const timelineWidth = Math.max(contentWidth, viewportWidth)
  const timeMarkerInterval = getTimeMarkerInterval(zoomLevel)
  const timeMarkers = generateTimeMarkers(totalDuration, timeMarkerInterval)
  
  // Handle playhead area click to seek (only if not dragging playhead)
  const handlePlayheadAreaClick = (e: React.MouseEvent<HTMLDivElement>): void => {
    if (isDraggingPlayhead) return
    if (!scrollContainerRef.current) return
    const rect = scrollContainerRef.current.getBoundingClientRect()
    const clickX = e.clientX - rect.left + scrollContainerRef.current.scrollLeft
    const timeX = clickX - TRACK_HEADER_WIDTH
    const time = Math.max(0, timeX / pixelsPerSecond)
    timelinePlayback.seek(Math.max(0, Math.min(time, totalDuration)))
  }
  
  // Handle playhead drag start
  const handlePlayheadMouseDown = (e: React.MouseEvent<HTMLDivElement>): void => {
    e.preventDefault()
    e.stopPropagation()
    setIsDraggingPlayhead(true)
    // Pause playback when starting to drag
    if (timelinePlayback.isPlaying) {
      timelinePlayback.pause()
    }
  }
  
  useEffect(() => {
    if (!isDraggingPlayhead) {
      setPlayheadDragTime(null)
      playheadDragTimeRef.current = null
      return
    }
    
    const handleMouseMove = (e: MouseEvent): void => {
      if (!scrollContainerRef.current || !playheadRef.current) return
      
      // Get current values from refs/state to ensure we have latest
      const rect = scrollContainerRef.current.getBoundingClientRect()
      const clientX = e.clientX
      
      // Recalculate pixels per second based on current viewport and zoom
      const currentViewportWidth = Math.max(scrollContainerRef.current.clientWidth - TRACK_HEADER_WIDTH, 100)
      const currentBasePixelsPerSecond = currentViewportWidth / DEFAULT_VIEWPORT_DURATION
      const currentPixelsPerSecond = currentBasePixelsPerSecond * zoomLevel
      
      // Calculate position relative to timeline
      let clickX: number
      if (clientX < rect.left) {
        clickX = 0
        // Auto-scroll when near left edge
        if (scrollContainerRef.current.scrollLeft > 0) {
          scrollContainerRef.current.scrollLeft = Math.max(0, scrollContainerRef.current.scrollLeft - 10)
        }
      } else if (clientX > rect.right) {
        clickX = scrollContainerRef.current.scrollWidth
        // Auto-scroll when near right edge
        const maxScroll = scrollContainerRef.current.scrollWidth - scrollContainerRef.current.clientWidth
        if (scrollContainerRef.current.scrollLeft < maxScroll) {
          scrollContainerRef.current.scrollLeft = Math.min(maxScroll, scrollContainerRef.current.scrollLeft + 10)
        }
      } else {
        clickX = clientX - rect.left + scrollContainerRef.current.scrollLeft
      }
      
      const timeX = clickX - TRACK_HEADER_WIDTH
      const calculatedTime = Math.max(0, Math.min(timeX / currentPixelsPerSecond, totalDuration))
      
      // Update ref immediately for position calculation
      playheadDragTimeRef.current = calculatedTime
      
      // Update playhead position DIRECTLY in DOM for instant visual feedback
      const playheadElement = playheadRef.current
      if (playheadElement) {
        const pixelPosition = TRACK_HEADER_WIDTH + calculatedTime * currentPixelsPerSecond
        playheadElement.style.left = `${pixelPosition}px`
      }
      
      // Update state for React (triggers re-render, but DOM is already updated)
      setPlayheadDragTime(calculatedTime)
      // Also update the playback time
      timelinePlayback.seek(calculatedTime)
    }
    
    const handleMouseUp = (): void => {
      setIsDraggingPlayhead(false)
      setPlayheadDragTime(null)
      playheadDragTimeRef.current = null
    }
    
    // Add cursor style to body during drag
    document.body.style.cursor = 'ew-resize'
    document.body.style.userSelect = 'none'
    
    // Use capture phase to ensure we catch all events - NO passive to allow preventDefault
    window.addEventListener('mousemove', handleMouseMove, true)
    window.addEventListener('mouseup', handleMouseUp, true)
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove, true)
      window.removeEventListener('mouseup', handleMouseUp, true)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDraggingPlayhead, zoomLevel, totalDuration, timelinePlayback])
  
  // Handle zoom
  const handleZoomIn = (): void => {
    setZoomLevel((prev) => Math.min(prev + ZOOM_STEP, ZOOM_MAX))
  }
  
  const handleZoomOut = (): void => {
    setZoomLevel((prev) => Math.max(prev - ZOOM_STEP, ZOOM_MIN))
  }

  // Handle mouse wheel zoom
  useEffect(() => {
    const handleWheel = (e: WheelEvent) => {
      // Only zoom if holding Ctrl/Cmd key
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        if (e.deltaY < 0) {
          // Zoom in
          setZoomLevel((prev) => Math.min(prev + ZOOM_STEP * 2, ZOOM_MAX))
        } else {
          // Zoom out
          setZoomLevel((prev) => Math.max(prev - ZOOM_STEP * 2, ZOOM_MIN))
        }
      }
    }

    const container = scrollContainerRef.current
    if (container) {
      container.addEventListener('wheel', handleWheel, { passive: false })
      return () => container.removeEventListener('wheel', handleWheel)
    }
  }, [])

  // Handle drag and drop from media library
  const handleDragOver = (e: React.DragEvent, trackType: 'video' | 'audio') => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
    setDragOverTrack(trackType)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverTrack(null)
  }

  const handleDrop = (e: React.DragEvent, trackType: 'video' | 'audio') => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverTrack(null)

    try {
      const data = e.dataTransfer.getData('application/json')
      if (!data) return

      const item: TimelineClip = JSON.parse(data)
      
      // Only allow dropping items of the correct type
      if (item.trackType !== trackType) {
        return
      }

      // Calculate drop position based on mouse X position
      if (!scrollContainerRef.current) return
      const rect = scrollContainerRef.current.getBoundingClientRect()
      const dropX = e.clientX - rect.left + scrollContainerRef.current.scrollLeft
      const timeX = dropX - TRACK_HEADER_WIDTH
      const dropTime = Math.max(0, timeX / pixelsPerSecond)

      // Create new clip instance for timeline (with unique ID)
      const newClip: TimelineClip = {
        ...item,
        id: `${item.libraryId}-${Date.now()}`,
        position: dropTime,
        trimStart: 0,
        trimEnd: item.duration,
        effectiveDuration: item.duration
      }

      // Get the clip source from the original library item
      const store = useEditorStore.getState()
      // Try to get source from clipSources map first, then fall back to URL properties
      const clipSource = store.getClipSource(item.libraryId) || item.videoUrl || item.audioUrl
      
      // Set clip source for the new timeline clip BEFORE adding to track
      if (clipSource) {
        store.setClipSource(newClip.id, clipSource)
        // Also ensure the clip's URL property is set
        if (trackType === 'video') {
          newClip.videoUrl = clipSource
        } else {
          newClip.audioUrl = clipSource
        }
      } else {
        console.warn('No clip source found for dropped item:', item)
      }

      // Add clip to track
      addClipToTrack(trackType, newClip)
    } catch (err) {
      console.error('Error handling drop:', err)
    }
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
  
  // Use drag time if dragging, otherwise use current playback time
  // During drag, use ref for immediate updates; after drag, use state
  const currentTime = playheadDragTime !== null 
    ? playheadDragTime 
    : timelinePlayback.currentTime
  const playheadPixelPosition = TRACK_HEADER_WIDTH + currentTime * pixelsPerSecond
  
  return (
    <div className="flex flex-col h-full bg-gray-900 border-t border-gray-700">
      {/* Zoom Controls */}
      <div className="flex items-center justify-between p-2 border-b border-gray-700 bg-gray-800">
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            disabled={zoomLevel <= ZOOM_MIN}
            title="Zoom out (Ctrl/Cmd + Scroll)"
            aria-label="Zoom out"
          >
            <ZoomOut size={18} />
          </button>
          <span className="text-sm font-medium text-gray-300 min-w-[50px] text-center">
            {Math.round(zoomLevel * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="p-2 rounded hover:bg-gray-700 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            disabled={zoomLevel >= ZOOM_MAX}
            title="Zoom in (Ctrl/Cmd + Scroll)"
            aria-label="Zoom in"
          >
            <ZoomIn size={18} />
          </button>
          <span className="text-xs text-gray-500 ml-2">
            (Ctrl/Cmd + Scroll to zoom)
          </span>
        </div>
        <div className="text-xs text-gray-500">
          Playhead: {formatTime(timelinePlayback.currentTime)} / {formatTime(totalDuration)}
        </div>
      </div>
      
      {/* Timeline Scroll Container */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-x-auto overflow-y-hidden relative"
        style={{ 
          height: '200px',
          width: '100%'
        }}
      >
        {/* Header with Time Markers */}
        <div
          className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 cursor-pointer"
          style={{ width: `${timelineWidth}px` }}
          onClick={handlePlayheadAreaClick}
          onMouseDown={(e) => {
            // Prevent dragging playhead when clicking header
            if (isDraggingPlayhead) {
              e.preventDefault()
            }
          }}
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
          className="absolute top-0 bottom-0 z-30 pointer-events-none"
          style={{
            left: isDraggingPlayhead && playheadDragTimeRef.current !== null
              ? `${TRACK_HEADER_WIDTH + playheadDragTimeRef.current * pixelsPerSecond}px`
              : `${playheadPixelPosition}px`,
            transition: isDraggingPlayhead ? 'none' : 'left 0.1s linear',
          }}
        >
          {/* Playhead line */}
          <div
            className={`absolute top-0 bottom-0 ${
              isDraggingPlayhead ? 'bg-red-400 w-1 shadow-lg shadow-red-500/50' : 'bg-red-500 w-0.5'
            }`}
            style={{ 
              left: '50%', 
              transform: 'translateX(-50%)',
              transition: isDraggingPlayhead ? 'none' : 'all 0.2s',
            }}
          />
          
          {/* Playhead handle */}
          <div
            className={`absolute top-0 left-1/2 transform -translate-x-1/2 border-transparent border-t-red-500 cursor-ew-resize pointer-events-all ${
              isDraggingPlayhead 
                ? 'border-l-6 border-r-6 border-t-6 scale-110' 
                : 'border-l-4 border-r-4 border-t-4 hover:border-l-5 hover:border-r-5 hover:border-t-5'
            }`}
            onMouseDown={handlePlayheadMouseDown}
            style={{ 
              cursor: isDraggingPlayhead ? 'ew-resize' : 'grab',
              transition: isDraggingPlayhead ? 'none' : 'all 0.2s',
            }}
          />
          
          {/* Time tooltip when dragging */}
          {isDraggingPlayhead && playheadDragTime !== null && (
            <div
              className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-red-500 text-white text-xs font-medium rounded shadow-lg whitespace-nowrap z-40"
            >
              {formatTime(playheadDragTime)}
            </div>
          )}
        </div>
        
        {/* Video Track */}
        <div 
          className={`relative border-b border-gray-700 transition-colors cursor-pointer ${
            dragOverTrack === 'video' ? 'bg-gray-800/50' : ''
          } ${isDraggingPlayhead ? '' : 'hover:bg-gray-800/30'}`}
          style={{ height: '80px' }}
          onDragOver={(e) => handleDragOver(e, 'video')}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDrop(e, 'video')}
          onClick={(e) => {
            if (!isDraggingPlayhead) {
              handlePlayheadAreaClick(e)
            }
          }}
        >
          <div className="flex h-full">
            <div
              className="flex items-center justify-between px-2 border-r border-gray-700 bg-gray-800 text-sm text-gray-400 font-medium"
              style={{ width: `${TRACK_HEADER_WIDTH}px` }}
            >
              <span>Video</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  toggleTrackMute('video')
                }}
                className="p-1 hover:bg-gray-700 rounded transition-colors"
                title={isMuted.video ? 'Unmute video audio' : 'Mute video audio'}
                aria-label={isMuted.video ? 'Unmute video audio' : 'Mute video audio'}
              >
                {isMuted.video ? (
                  <VolumeX className="w-4 h-4 text-gray-400 hover:text-red-400" />
                ) : (
                  <Volume2 className="w-4 h-4 text-gray-400 hover:text-white" />
                )}
              </button>
            </div>
            <div className="relative" style={{ width: `${timelineWidth - TRACK_HEADER_WIDTH}px`, minWidth: `${viewportWidth}px` }}>
              {timelineVideoClips.map((clip) => (
                <TimelineClipComponent
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
        <div 
          className={`relative transition-colors cursor-pointer ${
            dragOverTrack === 'audio' ? 'bg-gray-800/50' : ''
          } ${isDraggingPlayhead ? '' : 'hover:bg-gray-800/30'}`}
          style={{ height: '80px' }}
          onDragOver={(e) => handleDragOver(e, 'audio')}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDrop(e, 'audio')}
          onClick={(e) => {
            if (!isDraggingPlayhead) {
              handlePlayheadAreaClick(e)
            }
          }}
        >
          <div className="flex h-full">
            <div
              className="flex items-center justify-between px-2 border-r border-gray-700 bg-gray-800 text-sm text-gray-400 font-medium"
              style={{ width: `${TRACK_HEADER_WIDTH}px` }}
            >
              <span>Audio</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  toggleTrackMute('audio')
                }}
                className="p-1 hover:bg-gray-700 rounded transition-colors"
                title={isMuted.audio ? 'Unmute audio track' : 'Mute audio track'}
                aria-label={isMuted.audio ? 'Unmute audio track' : 'Mute audio track'}
              >
                {isMuted.audio ? (
                  <VolumeX className="w-4 h-4 text-gray-400 hover:text-red-400" />
                ) : (
                  <Volume2 className="w-4 h-4 text-gray-400 hover:text-white" />
                )}
              </button>
            </div>
            <div className="relative" style={{ width: `${timelineWidth - TRACK_HEADER_WIDTH}px`, minWidth: `${viewportWidth}px` }}>
              {timelineAudioClips.map((clip) => (
                <TimelineClipComponent
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


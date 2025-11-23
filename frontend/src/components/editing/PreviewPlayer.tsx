import React, { useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Pause, Volume2, VolumeX, Maximize, Minimize } from 'lucide-react'
import { useTimelineClips } from '@/stores/editorStore'
import { useTimelinePlayback } from '@/hooks/useTimelinePlayback'
import { useEditorStore } from '@/stores/editorStore'
import { formatDuration } from '@/utils/formatters'
import { Button } from '@/components/ui'
import { Slider } from '@/components/ui/slider'

interface PreviewPlayerProps {
  isFullscreen?: boolean
  onFullscreenChange?: (isFullscreen: boolean) => void
}

/**
 * PreviewPlayer component - Adapted for web (S3 URLs)
 * Supports multi-clip timeline playback
 */
export const PreviewPlayer: React.FC<PreviewPlayerProps> = ({ onFullscreenChange }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const { timelineVideoClips, timelineAudioClips } = useTimelineClips()
  const timelinePlayback = useTimelinePlayback()
  const { volume, isMuted, setVolume, toggleTrackMute } = useEditorStore()

  const hasTimelineClips = timelineVideoClips.length > 0 || timelineAudioClips.length > 0

  // Handle fullscreen toggle
  const toggleFullscreen = () => {
    const newFullscreenState = !isFullscreen
    setIsFullscreen(newFullscreenState)
    onFullscreenChange?.(newFullscreenState)
    
    if (newFullscreenState) {
      containerRef.current?.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }

  // Handle fullscreen change events
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  // Auto-hide controls in fullscreen
  useEffect(() => {
    if (isFullscreen) {
      const handleMouseMove = () => {
        setShowControls(true)
        if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
        controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 3000)
      }

      if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
      controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 3000)

      document.addEventListener('mousemove', handleMouseMove)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
      }
    } else {
      setShowControls(true)
      if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
      return undefined
    }
  }, [isFullscreen])

  // Handle seek
  const handleSeek = (value: number[]) => {
    const time = value[0]
    timelinePlayback.seek(time)
  }

  // Handle volume change
  const handleVolumeChange = (value: number[]) => {
    setVolume(value[0])
  }

  // Handle play/pause
  const handlePlayPause = () => {
    if (timelinePlayback.isPlaying) {
      timelinePlayback.pause()
    } else {
      timelinePlayback.play()
    }
  }

  const playheadPercent = timelinePlayback.totalDuration > 0
    ? (timelinePlayback.currentTime / timelinePlayback.totalDuration) * 100
    : 0

  if (!hasTimelineClips) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 rounded-xl border border-gray-700">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
            <Play className="w-10 h-10 text-white" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">Timeline Ready</h3>
          <p className="text-gray-400 mb-4">
            Video preview will appear here when timeline clips are loaded
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Video Preview Area */}
      <div
        ref={containerRef}
        className={`relative bg-black overflow-hidden group shadow-2xl flex-1 ${
          isFullscreen ? 'rounded-none' : 'rounded-xl'
        }`}
        style={isFullscreen ? { width: '100vw', height: '100vh' } : undefined}
        onMouseEnter={() => setShowControls(true)}
        onMouseLeave={() => {
          if (isFullscreen) {
            if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
            controlsTimeoutRef.current = setTimeout(() => setShowControls(false), 2000)
          }
        }}
      >
        {/* Video Element */}
        <video
          ref={timelinePlayback.videoRef}
          className="w-full h-full object-contain"
          preload="metadata"
          crossOrigin="anonymous"
          onError={(e) => {
            console.error('Timeline video error:', e)
          }}
          onClick={handlePlayPause}
        />

        {/* Hidden Audio Element */}
        <audio
          ref={timelinePlayback.audioRef}
          preload="metadata"
          crossOrigin="anonymous"
        />

        {/* Play/Pause Overlay */}
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.button
            onClick={handlePlayPause}
            className="p-4 bg-black bg-opacity-50 rounded-full text-white hover:bg-opacity-70 transition-all"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            initial={{ opacity: 0 }}
            animate={{ opacity: showControls ? 1 : 0 }}
            transition={{ duration: 0.2 }}
          >
            {timelinePlayback.isPlaying ? <Pause className="w-8 h-8" /> : <Play className="w-8 h-8" />}
          </motion.button>
        </div>

        {/* Controls Overlay */}
        <motion.div
          className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{
            opacity: showControls ? 1 : 0,
            y: showControls ? 0 : 20
          }}
          transition={{ duration: 0.2 }}
        >
          {/* Progress Bar */}
          <div className="mb-4">
            <div className="relative">
              <Slider
                value={[timelinePlayback.currentTime]}
                onValueChange={handleSeek}
                max={timelinePlayback.totalDuration || 1}
                step={0.1}
                className="w-full"
              />
              {/* Playhead indicator */}
              <div
                className="absolute top-0 w-1 h-2 bg-red-500 rounded"
                style={{ left: `${playheadPercent}%` }}
              />
            </div>
            {/* Time display */}
            <div className="flex justify-between text-xs text-gray-300 mt-2">
              <span className="font-medium">{formatDuration(timelinePlayback.currentTime)}</span>
              <span className="text-gray-400">
                Timeline {formatDuration(timelinePlayback.totalDuration)}
              </span>
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex items-center justify-between">
            {/* Left Controls */}
            <div className="flex items-center space-x-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handlePlayPause}
                className="text-white hover:bg-white/20 h-8 w-8 p-0"
                title="Play/Pause (Space)"
              >
                {timelinePlayback.isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </Button>
            </div>

            {/* Center - Video Info */}
            <div className="text-center flex-1 px-4">
              <p className="text-sm text-white font-medium truncate">
                Timeline Playback
              </p>
              <p className="text-xs text-gray-400">
                {timelineVideoClips.length} video clips + {timelineAudioClips.length} audio clips
              </p>
            </div>

            {/* Right Controls */}
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => toggleTrackMute(isMuted.video && isMuted.audio ? 'video' : 'audio')}
                className="text-white hover:bg-white/20 h-8 w-8 p-0"
                title="Mute (M)"
              >
                {isMuted.video && isMuted.audio ? (
                  <VolumeX className="w-4 h-4" />
                ) : (
                  <Volume2 className="w-4 h-4" />
                )}
              </Button>

              <div className="w-16">
                <Slider
                  value={[isMuted.video && isMuted.audio ? 0 : volume]}
                  onValueChange={handleVolumeChange}
                  max={1}
                  step={0.1}
                  className="w-full"
                />
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={toggleFullscreen}
                className="text-white hover:bg-white/20 h-8 w-8 p-0"
                title="Fullscreen (F)"
              >
                {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Video Info Panel */}
      <div className="bg-gray-800 rounded-lg p-3 border border-gray-700 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Timeline with {timelineVideoClips.length} video clips + {timelineAudioClips.length} audio clips
          </div>
        </div>
      </div>
    </div>
  )
}


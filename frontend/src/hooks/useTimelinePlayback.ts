import { useRef, useEffect, useCallback } from 'react'
import { useEditorStore, type TimelineClip } from '@/stores/editorStore'

/**
 * Helper: Calculate total timeline duration
 */
const getTimelineDuration = (videoClips: TimelineClip[], audioClips: TimelineClip[]): number => {
  const videoDuration = videoClips.length > 0
    ? Math.max(...videoClips.map((clip) => clip.position + clip.effectiveDuration))
    : 0
  const audioDuration = audioClips.length > 0
    ? Math.max(...audioClips.map((clip) => clip.position + clip.effectiveDuration))
    : 0
  return Math.max(videoDuration, audioDuration)
}

/**
 * Helper: Find active clip at current time
 */
const getActiveClip = (clips: TimelineClip[], currentTime: number): TimelineClip | null => {
  return clips.find(
    (clip) => currentTime >= clip.position && currentTime < clip.position + clip.effectiveDuration
  ) || null
}

/**
 * Calculate playback time within a clip accounting for trim
 */
const calculateClipPlaybackTime = (currentTime: number, clip: TimelineClip): number => {
  return currentTime - clip.position + clip.trimStart
}

/**
 * Get video source URL - adapted for web (S3 URLs)
 */
const getVideoSrc = (url: string | undefined): string => {
  if (!url) return ''
  // If it's already a full URL, use it
  if (url.startsWith('http') || url.startsWith('blob:')) {
    return url
  }
  // Otherwise, assume it needs API proxy
  if (url.includes('amazonaws.com')) {
    return url // S3 URLs should work directly if CORS is configured
  }
  return url
}

/**
 * Hook for timeline playback
 */
export const useTimelinePlayback = () => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const playbackIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const pendingVideoSrcRef = useRef<string | null>(null)
  const pendingAudioSrcRef = useRef<string | null>(null)
  const prevIsPlayingRef = useRef<boolean>(false)
  const prevActiveVideoClipIdRef = useRef<string | null>(null)
  const prevActiveAudioClipIdRef = useRef<string | null>(null)

  const {
    timelineVideoClips,
    timelineAudioClips,
    isMuted,
    timelineCurrentTime,
    timelineIsPlaying,
    setTimelineCurrentTime,
    setTimelinePlaying,
    getClipSource
  } = useEditorStore()

  const totalDuration = getTimelineDuration(timelineVideoClips, timelineAudioClips)

  // Update total duration in store
  useEffect(() => {
    useEditorStore.getState().setTimelineTotalDuration(totalDuration)
  }, [totalDuration])

  // Synchronize playback with timeline state
  useEffect(() => {
    if (totalDuration === 0) return

    // Find active video clip
    const activeVideoClip = getActiveClip(timelineVideoClips, timelineCurrentTime)

    // Update video element
    if (videoRef.current && activeVideoClip) {
      const clipUrl = getClipSource(activeVideoClip.id) || activeVideoClip.videoUrl
      const videoSrc = getVideoSrc(clipUrl)
      const playbackTime = calculateClipPlaybackTime(timelineCurrentTime, activeVideoClip)

      // Load clip if src changed
      if (videoSrc && (!pendingVideoSrcRef.current || pendingVideoSrcRef.current !== videoSrc)) {
        videoRef.current.src = videoSrc
        pendingVideoSrcRef.current = videoSrc
      }

      // Seek to playback time
      if (!timelineIsPlaying || pendingVideoSrcRef.current !== videoSrc) {
        videoRef.current.currentTime = playbackTime
      }

      videoRef.current.muted = isMuted.video

      // Play/pause
      if (timelineIsPlaying) {
        videoRef.current.play().catch((e) => console.log('Video play error:', e))
        prevActiveVideoClipIdRef.current = activeVideoClip.id
      } else {
        videoRef.current.pause()
      }
    } else if (videoRef.current && !activeVideoClip) {
      videoRef.current.pause()
    }

    // Find active audio clip
    const activeAudioClip = getActiveClip(timelineAudioClips, timelineCurrentTime)

    // Update audio element
    if (audioRef.current && activeAudioClip && !isMuted.audio) {
      const clipUrl = getClipSource(activeAudioClip.id) || activeAudioClip.audioUrl
      const audioSrc = getVideoSrc(clipUrl)
      const playbackTime = calculateClipPlaybackTime(timelineCurrentTime, activeAudioClip)

      // Load clip if src changed
      if (audioSrc && (!pendingAudioSrcRef.current || pendingAudioSrcRef.current !== audioSrc)) {
        audioRef.current.src = audioSrc
        pendingAudioSrcRef.current = audioSrc
      }

      // Seek to playback time
      if (!timelineIsPlaying || pendingAudioSrcRef.current !== audioSrc) {
        audioRef.current.currentTime = playbackTime
      }

      // Play/pause
      if (timelineIsPlaying) {
        audioRef.current.play().catch((e) => console.log('Audio play error:', e))
        prevActiveAudioClipIdRef.current = activeAudioClip.id
      } else {
        audioRef.current.pause()
      }
    } else if (audioRef.current && (!activeAudioClip || isMuted.audio)) {
      audioRef.current.pause()
    }

    prevIsPlayingRef.current = timelineIsPlaying
  }, [
    timelineCurrentTime,
    timelineVideoClips,
    timelineAudioClips,
    timelineIsPlaying,
    isMuted,
    getClipSource
  ])

  // Playback loop - update currentTime while playing
  useEffect(() => {
    if (!timelineIsPlaying) {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current)
        playbackIntervalRef.current = null
      }
      return
    }

    playbackIntervalRef.current = setInterval(() => {
      const currentTime = timelineCurrentTime + 0.1
      if (currentTime >= totalDuration) {
        setTimelinePlaying(false)
        setTimelineCurrentTime(totalDuration)
      } else {
        setTimelineCurrentTime(currentTime)
      }
    }, 100)

    return () => {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current)
        playbackIntervalRef.current = null
      }
    }
  }, [timelineIsPlaying, timelineCurrentTime, totalDuration, setTimelineCurrentTime, setTimelinePlaying])

  const play = useCallback(() => {
    setTimelinePlaying(true)
  }, [setTimelinePlaying])

  const pause = useCallback(() => {
    setTimelinePlaying(false)
  }, [setTimelinePlaying])

  const seek = useCallback((time: number) => {
    setTimelineCurrentTime(Math.max(0, Math.min(time, totalDuration)))
  }, [setTimelineCurrentTime, totalDuration])

  return {
    videoRef,
    audioRef,
    isPlaying: timelineIsPlaying,
    currentTime: timelineCurrentTime,
    totalDuration,
    play,
    pause,
    seek
  }
}


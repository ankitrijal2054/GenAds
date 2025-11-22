import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

/**
 * Timeline clip interface
 */
export interface TimelineClip {
  id: string
  libraryId: string
  name: string
  trackType: 'video' | 'audio'
  duration: number
  trimStart: number
  trimEnd: number
  effectiveDuration: number
  position: number
  color?: string
  videoUrl?: string  // S3 URL for video clips
  audioUrl?: string  // S3 URL for audio clips
}

/**
 * Editor store state interface
 */
export interface EditorStore {
  // Timeline clips
  timelineVideoClips: TimelineClip[]
  timelineAudioClips: TimelineClip[]
  selectedClipId: string | null
  isMuted: {
    video: boolean
    audio: boolean
  }
  
  // Timeline playback state
  timelineCurrentTime: number
  timelineIsPlaying: boolean
  timelineTotalDuration: number
  
  // Playback controls
  volume: number
  
  // Clip sources map (for storing S3 URLs)
  clipSources: Record<string, string>
  
  // Actions
  setTimelineVideoClips: (clips: TimelineClip[]) => void
  setTimelineAudioClips: (clips: TimelineClip[]) => void
  selectTimelineClip: (clipId: string | null) => void
  toggleTrackMute: (trackType: 'video' | 'audio') => void
  setVolume: (volume: number) => void
  setTimelineCurrentTime: (time: number) => void
  setTimelinePlaying: (isPlaying: boolean) => void
  setTimelineTotalDuration: (duration: number) => void
  setClipSource: (clipId: string, url: string) => void
  getClipSource: (clipId: string) => string | undefined
  
  // Timeline manipulation actions
  addClipToTrack: (trackType: 'video' | 'audio', clip: TimelineClip) => void
  removeClipFromTrack: (trackType: 'video' | 'audio', clipId: string) => void
  moveClip: (trackType: 'video' | 'audio', clipId: string, newPosition: number) => void
  updateClipTrim: (clipId: string, trimStart: number, trimEnd: number) => void
  splitClip: (clipId: string, splitTime: number) => void
  
  // Timeline state getter for export
  getTimelineState: () => {
    video_clips: Array<{
      id: string
      library_id: string
      name: string
      track_type: string
      duration: number
      trim_start: number
      trim_end: number
      effective_duration: number
      position: number
    }>
    audio_clips: Array<{
      id: string
      library_id: string
      name: string
      track_type: string
      duration: number
      trim_start: number
      trim_end: number
      effective_duration: number
      position: number
    }>
    total_duration: number
  }
}

/**
 * Helper function to recalculate positions for all clips in a track
 */
const recalculatePositions = (clips: TimelineClip[]): TimelineClip[] => {
  let cumulativePosition = 0
  return clips.map((clip) => ({
    ...clip,
    position: (cumulativePosition += clip.effectiveDuration) - clip.effectiveDuration,
    effectiveDuration: clip.trimEnd - clip.trimStart
  }))
}

/**
 * Editor store - Zustand store for timeline editing state
 */
export const useEditorStore = create<EditorStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        timelineVideoClips: [],
        timelineAudioClips: [],
        selectedClipId: null,
        isMuted: {
          video: false,
          audio: false
        },
        timelineCurrentTime: 0,
        timelineIsPlaying: false,
        timelineTotalDuration: 0,
        volume: 1,
        clipSources: {},
        
        // Actions
        setTimelineVideoClips: (clips) => set({ timelineVideoClips: clips }),
        setTimelineAudioClips: (clips) => set({ timelineAudioClips: clips }),
        selectTimelineClip: (clipId) => set({ selectedClipId: clipId }),
        toggleTrackMute: (trackType) => set((state) => ({
          isMuted: {
            ...state.isMuted,
            [trackType]: !state.isMuted[trackType]
          }
        })),
        setVolume: (volume) => set({ volume: Math.max(0, Math.min(1, volume)) }),
        setTimelineCurrentTime: (time) => set({ timelineCurrentTime: Math.max(0, time) }),
        setTimelinePlaying: (isPlaying) => set({ timelineIsPlaying: isPlaying }),
        setTimelineTotalDuration: (duration) => set({ timelineTotalDuration: duration }),
        setClipSource: (clipId, url) => set((state) => ({
          clipSources: {
            ...state.clipSources,
            [clipId]: url
          }
        })),
        getClipSource: (clipId) => get().clipSources[clipId],
        
        // Timeline manipulation
        addClipToTrack: (trackType, clip) => set((state) => {
          const trackClips = trackType === 'video' ? state.timelineVideoClips : state.timelineAudioClips
          const position = trackClips.reduce((sum, c) => sum + c.effectiveDuration, 0)
          const newClip: TimelineClip = {
            ...clip,
            position,
            effectiveDuration: clip.trimEnd - clip.trimStart
          }
          const updatedClips = trackType === 'video'
            ? [...state.timelineVideoClips, newClip]
            : [...state.timelineAudioClips, newClip]
          return trackType === 'video'
            ? { timelineVideoClips: updatedClips }
            : { timelineAudioClips: updatedClips }
        }),
        
        removeClipFromTrack: (trackType, clipId) => set((state) => {
          const trackClips = trackType === 'video'
            ? state.timelineVideoClips.filter((c) => c.id !== clipId)
            : state.timelineAudioClips.filter((c) => c.id !== clipId)
          const updatedClips = recalculatePositions(trackClips)
          return trackType === 'video'
            ? { timelineVideoClips: updatedClips, selectedClipId: state.selectedClipId === clipId ? null : state.selectedClipId }
            : { timelineAudioClips: updatedClips }
        }),
        
        moveClip: (trackType, clipId, newPosition) => set((state) => {
          const trackClips = trackType === 'video' ? state.timelineVideoClips : state.timelineAudioClips
          const clipIndex = trackClips.findIndex((c) => c.id === clipId)
          if (clipIndex === -1) return state
          
          // Simple reordering based on position
          let targetIndex = 0
          let cumulativePos = 0
          for (let i = 0; i < trackClips.length; i++) {
            if (i === clipIndex) continue
            if (cumulativePos + trackClips[i].effectiveDuration <= newPosition) {
              cumulativePos += trackClips[i].effectiveDuration
              targetIndex = i + 1
            }
          }
          
          const updatedClips = [...trackClips]
          updatedClips.splice(clipIndex, 1)
          updatedClips.splice(targetIndex, 0, trackClips[clipIndex])
          const repositionedClips = recalculatePositions(updatedClips)
          
          return trackType === 'video'
            ? { timelineVideoClips: repositionedClips }
            : { timelineAudioClips: repositionedClips }
        }),
        
        updateClipTrim: (clipId, trimStart, trimEnd) => set((state) => {
          const finalTrimStart = Math.max(0, Math.min(trimStart, trimEnd - 0.05))
          const finalTrimEnd = Math.max(trimStart + 0.05, trimEnd)
          
          let updatedVideoClips = state.timelineVideoClips
          let updatedAudioClips = state.timelineAudioClips
          
          const videoClipIndex = state.timelineVideoClips.findIndex((c) => c.id === clipId)
          if (videoClipIndex !== -1) {
            updatedVideoClips = [...state.timelineVideoClips]
            updatedVideoClips[videoClipIndex] = {
              ...updatedVideoClips[videoClipIndex],
              trimStart: finalTrimStart,
              trimEnd: finalTrimEnd,
              effectiveDuration: finalTrimEnd - finalTrimStart
            }
            updatedVideoClips = recalculatePositions(updatedVideoClips)
          } else {
            const audioClipIndex = state.timelineAudioClips.findIndex((c) => c.id === clipId)
            if (audioClipIndex !== -1) {
              updatedAudioClips = [...state.timelineAudioClips]
              updatedAudioClips[audioClipIndex] = {
                ...updatedAudioClips[audioClipIndex],
                trimStart: finalTrimStart,
                trimEnd: finalTrimEnd,
                effectiveDuration: finalTrimEnd - finalTrimStart
              }
              updatedAudioClips = recalculatePositions(updatedAudioClips)
            }
          }
          
          return {
            timelineVideoClips: updatedVideoClips,
            timelineAudioClips: updatedAudioClips
          }
        }),
        
        splitClip: (clipId, splitTime) => set((state) => {
          const videoClipIndex = state.timelineVideoClips.findIndex((c) => c.id === clipId)
          const isInVideoTrack = videoClipIndex !== -1
          const audioClipIndex = state.timelineAudioClips.findIndex((c) => c.id === clipId)
          const clipIndex = isInVideoTrack ? videoClipIndex : audioClipIndex
          const clips = isInVideoTrack ? state.timelineVideoClips : state.timelineAudioClips
          const clip = clipIndex !== -1 ? clips[clipIndex] : null
          
          if (!clip) return state
          
          const splitPointInClip = splitTime - clip.position + clip.trimStart
          if (splitPointInClip <= clip.trimStart || splitPointInClip >= clip.trimEnd) {
            return state
          }
          
          const clip1: TimelineClip = {
            ...clip,
            id: `clip-${Date.now()}`,
            trimEnd: splitPointInClip,
            effectiveDuration: splitPointInClip - clip.trimStart
          }
          
          const clip2: TimelineClip = {
            ...clip,
            id: `clip-${Date.now()}-split`,
            trimStart: splitPointInClip,
            effectiveDuration: clip.trimEnd - splitPointInClip
          }
          
          const updatedClips = [...clips]
          updatedClips.splice(clipIndex, 1, clip1, clip2)
          const repositionedClips = recalculatePositions(updatedClips)
          
          return isInVideoTrack
            ? { timelineVideoClips: repositionedClips }
            : { timelineAudioClips: repositionedClips }
        }),
        
        // Export state getter
        getTimelineState: () => {
          const state = get()
          const videoDuration = state.timelineVideoClips.reduce(
            (max, clip) => Math.max(max, clip.position + clip.effectiveDuration),
            0
          )
          const audioDuration = state.timelineAudioClips.reduce(
            (max, clip) => Math.max(max, clip.position + clip.effectiveDuration),
            0
          )
          const totalDuration = Math.max(videoDuration, audioDuration)
          
          return {
            video_clips: state.timelineVideoClips.map((clip) => ({
              id: clip.id,
              library_id: clip.libraryId,
              name: clip.name,
              track_type: clip.trackType,
              duration: clip.duration,
              trim_start: clip.trimStart,
              trim_end: clip.trimEnd,
              effective_duration: clip.effectiveDuration,
              position: clip.position
            })),
            audio_clips: state.timelineAudioClips.map((clip) => ({
              id: clip.id,
              library_id: clip.libraryId,
              name: clip.name,
              track_type: clip.trackType,
              duration: clip.duration,
              trim_start: clip.trimStart,
              trim_end: clip.trimEnd,
              effective_duration: clip.effectiveDuration,
              position: clip.position
            })),
            total_duration: totalDuration
          }
        }
      }),
      {
        name: 'genads-editor-store',
        partialize: (state) => ({
          volume: state.volume,
          isMuted: state.isMuted
        })
      }
    ),
    {
      name: 'genads-editor-store'
    }
  )
)

// Selector hooks
export const useTimelineClips = () => {
  const timelineVideoClips = useEditorStore((state) => state.timelineVideoClips)
  const timelineAudioClips = useEditorStore((state) => state.timelineAudioClips)
  const selectedClipId = useEditorStore((state) => state.selectedClipId)
  return { timelineVideoClips, timelineAudioClips, selectedClipId }
}

export const useTimelinePlayback = () => {
  const timelineCurrentTime = useEditorStore((state) => state.timelineCurrentTime)
  const timelineIsPlaying = useEditorStore((state) => state.timelineIsPlaying)
  const timelineTotalDuration = useEditorStore((state) => state.timelineTotalDuration)
  const setTimelineCurrentTime = useEditorStore((state) => state.setTimelineCurrentTime)
  const setTimelinePlaying = useEditorStore((state) => state.setTimelinePlaying)
  return {
    currentTime: timelineCurrentTime,
    isPlaying: timelineIsPlaying,
    totalDuration: timelineTotalDuration,
    seek: setTimelineCurrentTime,
    play: () => setTimelinePlaying(true),
    pause: () => setTimelinePlaying(false)
  }
}


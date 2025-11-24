import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui'
import { PreviewPlayer } from '@/components/editing/PreviewPlayer'
import { Timeline } from '@/components/editing/Timeline'
import { MediaLibrarySidebar } from '@/components/editing/MediaLibrarySidebar'
import { useCampaigns } from '@/hooks/useCampaigns'
import { useEditorStore, type TimelineClip } from '@/stores/editorStore'
import { manualEditing } from '@/services/api'
import { ArrowLeft, CheckCircle2, Loader2, FolderOpen, Download } from 'lucide-react'

/**
 * Initialize timeline from campaign data
 * Shows scene clips if manual_editing_done is false, final video if true
 */
const initializeTimelineFromCampaign = async (
  campaign: any,
  variationIndex: number = 0
) => {
  const campaignJson = typeof campaign.campaign_json === 'string'
    ? JSON.parse(campaign.campaign_json)
    : campaign.campaign_json
  
  const store = useEditorStore.getState()
  
  // Check if manual editing is done - show final video instead of scenes
  if (campaign.manual_editing_done) {
    // Load final video from variationPaths
    const variationPaths = campaignJson.variationPaths || {}
    const variationPath = variationPaths[`variation_${variationIndex}`] || {}
    const aspectExports = variationPath.aspectExports || {}
    const finalVideoUrl = aspectExports['16:9'] || aspectExports['9:16'] || null
    
    if (finalVideoUrl) {
      // Create single video clip for final video
      // Estimate duration (we'll get actual duration from video metadata if needed)
      const estimatedDuration = 120 // Default 2 minutes, will be updated when video loads
      
      const finalVideoClip: TimelineClip = {
        id: 'final-video',
        libraryId: 'final-video',
        name: 'Final Video',
        trackType: 'video',
        duration: estimatedDuration,
        trimStart: 0,
        trimEnd: estimatedDuration,
        effectiveDuration: estimatedDuration,
        position: 0,
        videoUrl: finalVideoUrl
      }
      
      store.setTimelineVideoClips([finalVideoClip])
      store.setTimelineAudioClips([])
      store.setTimelineTotalDuration(estimatedDuration)
      store.setClipSource('final-video', finalVideoUrl)
    } else {
      // No final video found, show empty timeline
      store.setTimelineVideoClips([])
      store.setTimelineAudioClips([])
      store.setTimelineTotalDuration(120) // Default 2 minutes
    }
    return
  }
  
  // Manual editing not done - show scene clips
  const scenes = campaignJson.scenes || []
  
  // Fetch scene data from API
  const scenesResponse = await manualEditing.getEditingScenes(campaign.campaign_id, variationIndex)
  const sceneInfos = scenesResponse.data
  
  // Fetch music data from API
  const musicResponse = await manualEditing.getEditingMusic(campaign.campaign_id, variationIndex)
  const musicInfo = musicResponse.data
  
  // Create video clips for each scene
  const videoClips: TimelineClip[] = sceneInfos.map((scene: any, index: number) => ({
    id: `scene-${index}`,
    libraryId: `scene-${index}`,
    name: `Scene ${index + 1} - ${scene.role}`,
    trackType: 'video',
    duration: scene.duration,
    trimStart: 0,
    trimEnd: scene.duration,
    effectiveDuration: scene.duration,
    position: sceneInfos.slice(0, index).reduce((sum: number, s: any) => sum + s.duration, 0),
    videoUrl: scene.video_url
  }))
  
  // Create audio clip for music
  const totalDuration = Math.max(
    scenes.reduce((sum: number, s: any) => sum + (s.duration || 4), 0),
    120 // Minimum 2 minutes
  )
  const audioClip: TimelineClip = {
    id: 'music-track',
    libraryId: 'music-track',
    name: 'Background Music',
    trackType: 'audio',
    duration: musicInfo.duration || totalDuration,
    trimStart: 0,
    trimEnd: musicInfo.duration || totalDuration,
    effectiveDuration: musicInfo.duration || totalDuration,
    position: 0,
    audioUrl: musicInfo.audio_url
  }
  
  // Initialize store
  store.setTimelineVideoClips(videoClips)
  store.setTimelineAudioClips([audioClip])
  store.setTimelineTotalDuration(totalDuration)
  
  // Populate media library with all scenes and music
  const allMediaItems: TimelineClip[] = [
    ...videoClips.map(clip => ({ ...clip, position: 0 })), // Reset position for library items
    { ...audioClip, position: 0 }
  ]
  store.setMediaLibrary(allMediaItems)
  
  // Set clip sources for playback
  videoClips.forEach((clip) => {
    if (clip.videoUrl) {
      store.setClipSource(clip.id, clip.videoUrl)
    }
  })
  if (audioClip.audioUrl) {
    store.setClipSource(audioClip.id, audioClip.audioUrl)
  }
}

export const ManualEditing = () => {
  const { campaignId } = useParams<{ campaignId: string }>()
  const navigate = useNavigate()
  const { getCampaign } = useCampaigns()
  
  const [campaign, setCampaign] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exportProgress, setExportProgress] = useState(0)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  
  // Load campaign and initialize timeline
  useEffect(() => {
    const loadCampaign = async () => {
      if (!campaignId) return
      
      try {
        setIsLoading(true)
        const data = await getCampaign(campaignId)
        setCampaign(data)
        
        // Get selected variation index
        const variationIndex = data.selected_variation_index || 0
        
        // Initialize timeline (shows scenes if not done, final video if done)
        await initializeTimelineFromCampaign(data, variationIndex)
      } catch (err: any) {
        console.error('Failed to load campaign:', err)
        setError(err?.response?.data?.detail || 'Failed to load campaign')
      } finally {
        setIsLoading(false)
      }
    }
    
    loadCampaign()
  }, [campaignId, navigate, getCampaign])
  
  // Handle direct download (client-side recording)
  const handleDownload = async () => {
    if (!campaignId) return
    
    setIsDownloading(true)
    setError(null)
    
    try {
      // Record video using shared function
      const videoBlob = await recordTimelineVideo()
      
      // Download the blob
      const url = URL.createObjectURL(videoBlob)
      const a = document.createElement('a')
      a.href = url
      const extension = videoBlob.type.includes('webm') ? 'webm' : 'mp4'
      a.download = `edited-video-${campaignId}-${Date.now()}.${extension}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      
      setIsDownloading(false)
    } catch (err: any) {
      console.error('Download error:', err)
      setError(err?.message || 'Failed to download video')
      setIsDownloading(false)
    }
  }
  
  // Record video from timeline (shared between download and export)
  const recordTimelineVideo = async (onProgress?: (progress: number) => void): Promise<Blob> => {
    const store = useEditorStore.getState()
    const { timelineVideoClips, timelineAudioClips } = store
    
    if (timelineVideoClips.length === 0 && timelineAudioClips.length === 0) {
      throw new Error('No clips to record')
    }
    
    // Create canvas for rendering
    const canvas = document.createElement('canvas')
    canvas.width = 1080
    canvas.height = 1920
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('Could not get canvas context')
    }
    
    // Fill with black background initially
    ctx.fillStyle = '#000000'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    
    // Create MediaRecorder from canvas stream
    const canvasStream = canvas.captureStream(30) // 30 fps
    
    // Create audio context for mixing audio
    const audioContext = new AudioContext({ sampleRate: 44100 })
    const audioDestination = audioContext.createMediaStreamDestination()
    const audioGainNode = audioContext.createGain()
    audioGainNode.gain.value = 1.0
    audioGainNode.connect(audioDestination)
    
    // Load and connect audio clips
    const audioElements: Map<string, HTMLAudioElement> = new Map()
    const audioSourceNodes: Map<string, MediaElementAudioSourceNode> = new Map()
    
    for (const audioClip of timelineAudioClips) {
      const audioSource = store.getClipSource(audioClip.id) || audioClip.audioUrl
      if (!audioSource) continue
      
      const audio = document.createElement('audio')
      audio.crossOrigin = 'anonymous'
      audio.preload = 'auto'
      audio.loop = false
      
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error(`Timeout loading audio: ${audioClip.name}`))
        }, 10000)
        
        const cleanup = () => {
          clearTimeout(timeout)
          audio.removeEventListener('loadeddata', onLoadedData)
          audio.removeEventListener('error', onError)
          audio.removeEventListener('canplay', onCanPlay)
        }
        
        const onLoadedData = () => {
          cleanup()
          resolve()
        }
        
        const onCanPlay = () => {
          cleanup()
          resolve()
        }
        
        const onError = (e: Event) => {
          cleanup()
          console.error('Audio load error:', e)
          reject(new Error(`Failed to load audio: ${audioClip.name}`))
        }
        
        audio.addEventListener('loadeddata', onLoadedData)
        audio.addEventListener('canplay', onCanPlay)
        audio.addEventListener('error', onError)
        
        audio.src = audioSource
        audio.load()
      })
      
      // Create audio source node and connect to gain node
      try {
        const sourceNode = audioContext.createMediaElementSource(audio)
        const clipGainNode = audioContext.createGain()
        clipGainNode.gain.value = 1.0
        sourceNode.connect(clipGainNode)
        clipGainNode.connect(audioGainNode)
        
        audioSourceNodes.set(audioClip.id, sourceNode)
        audioElements.set(audioClip.id, audio)
      } catch (e) {
        console.warn('Could not create audio source node:', e)
        // Continue without audio for this clip
      }
    }
    
    // Add audio tracks to canvas stream
    const audioTracks = audioDestination.stream.getAudioTracks()
    audioTracks.forEach(track => canvasStream.addTrack(track))
    
    // Check for supported MIME types
    let mimeType = 'video/webm'
    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')) {
      mimeType = 'video/webm;codecs=vp9,opus'
    } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')) {
      mimeType = 'video/webm;codecs=vp8,opus'
    } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) {
      mimeType = 'video/webm;codecs=vp9'
    } else if (MediaRecorder.isTypeSupported('video/webm')) {
      mimeType = 'video/webm'
    }
    
    const mediaRecorder = new MediaRecorder(canvasStream, {
      mimeType,
      videoBitsPerSecond: 5000000,
      audioBitsPerSecond: 128000
    })
    
    const chunks: Blob[] = []
    let recordingStarted = false
    
    return new Promise<Blob>((resolve, reject) => {
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunks.push(e.data)
        }
      }
      
      mediaRecorder.onstop = () => {
        if (chunks.length === 0) {
          audioContext.close()
          reject(new Error('No video data recorded. Please try again.'))
          return
        }
        
        const blob = new Blob(chunks, { type: mimeType })
        audioContext.close()
        resolve(blob)
      }
      
      mediaRecorder.onerror = (e) => {
        console.error('MediaRecorder error:', e)
        audioContext.close()
        reject(new Error('Recording error occurred'))
      }
      
      // Start recording
      mediaRecorder.start(100) // Collect data every 100ms
      recordingStarted = true
      
      // Render timeline to canvas frame by frame
      const frameRate = 30
      const frameTime = 1 / frameRate
      const totalDuration = store.timelineTotalDuration || 120
      
      // Sort clips by position to ensure correct order
      const sortedClips = [...timelineVideoClips].sort((a, b) => a.position - b.position)
      
      // Pre-load all video clips
      const videoElements: Map<string, HTMLVideoElement> = new Map()
      
      // Load all videos first
      Promise.all(
        sortedClips.map(async (clip) => {
          const clipSource = store.getClipSource(clip.id) || clip.videoUrl
          if (!clipSource) return null
          
          const video = document.createElement('video')
          video.crossOrigin = 'anonymous'
          video.muted = false
          video.playsInline = true
          video.preload = 'auto'
          
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error(`Timeout loading video: ${clip.name}`))
            }, 15000)
            
            const cleanup = () => {
              clearTimeout(timeout)
              video.removeEventListener('loadeddata', onLoadedData)
              video.removeEventListener('error', onError)
              video.removeEventListener('canplay', onCanPlay)
            }
            
            const onLoadedData = () => {
              cleanup()
              resolve()
            }
            
            const onCanPlay = () => {
              if (video.readyState >= 2) {
                cleanup()
                resolve()
              }
            }
            
            const onError = (e: Event) => {
              cleanup()
              console.error('Video load error:', e, clipSource)
              reject(new Error(`Failed to load video: ${clip.name}`))
            }
            
            video.addEventListener('loadeddata', onLoadedData)
            video.addEventListener('canplay', onCanPlay)
            video.addEventListener('error', onError)
            
            video.src = clipSource
            video.load()
          })
          
          videoElements.set(clip.id, video)
          return video
        })
      ).then(() => {
        // Render frame by frame through entire timeline
        const totalFrames = Math.ceil(totalDuration * frameRate)
        let lastActiveClipId: string | null = null
        
        const renderFrame = async (frame: number) => {
          if (frame >= totalFrames) {
            // Stop all audio
            audioElements.forEach(audio => {
              audio.pause()
              audio.currentTime = 0
            })
            
            // Wait a bit to ensure all frames are captured
            await new Promise(r => setTimeout(r, 500))
            
            // Stop recording
            if (recordingStarted && mediaRecorder.state !== 'inactive') {
              mediaRecorder.stop()
            } else {
              reject(new Error('Recording was not started properly'))
            }
            return
          }
          
          const currentTime = frame / frameRate
          
          // Find active clip at this time
          const activeClip = sortedClips.find(
            clip => currentTime >= clip.position && 
                    currentTime < clip.position + clip.effectiveDuration
          )
          
          if (activeClip) {
            const video = videoElements.get(activeClip.id)
            if (video) {
              // Calculate time within clip
              const timeInClip = currentTime - activeClip.position
              const targetVideoTime = activeClip.trimStart + timeInClip
              
              // Only seek when clip changes or when significantly off
              const clipChanged = lastActiveClipId !== activeClip.id
              if (clipChanged) {
                video.currentTime = targetVideoTime
                while (video.readyState < 2) {
                  await new Promise(r => setTimeout(r, 50))
                }
                await new Promise(r => setTimeout(r, 50))
                lastActiveClipId = activeClip.id
              } else if (Math.abs(video.currentTime - targetVideoTime) > 0.3) {
                video.currentTime = targetVideoTime
                await new Promise(r => setTimeout(r, 50))
              } else {
                video.currentTime = targetVideoTime
              }
              
              // Ensure video is ready before drawing
              if (video.readyState < 2) {
                await new Promise(r => setTimeout(r, 30))
              }
              
              // Draw current frame
              try {
                if (video.videoWidth > 0 && video.videoHeight > 0) {
                  const videoAspect = video.videoWidth / video.videoHeight
                  const canvasAspect = canvas.width / canvas.height
                  
                  let drawWidth = canvas.width
                  let drawHeight = canvas.height
                  let drawX = 0
                  let drawY = 0
                  
                  if (videoAspect > canvasAspect) {
                    drawHeight = canvas.width / videoAspect
                    drawY = (canvas.height - drawHeight) / 2
                  } else {
                    drawWidth = canvas.height * videoAspect
                    drawX = (canvas.width - drawWidth) / 2
                  }
                  
                  ctx.fillStyle = '#000000'
                  ctx.fillRect(0, 0, canvas.width, canvas.height)
                  ctx.drawImage(video, drawX, drawY, drawWidth, drawHeight)
                } else {
                  ctx.fillStyle = '#000000'
                  ctx.fillRect(0, 0, canvas.width, canvas.height)
                }
              } catch (e) {
                console.error('Error drawing frame:', e)
                ctx.fillStyle = '#000000'
                ctx.fillRect(0, 0, canvas.width, canvas.height)
              }
            } else {
              ctx.fillStyle = '#000000'
              ctx.fillRect(0, 0, canvas.width, canvas.height)
            }
          } else {
            ctx.fillStyle = '#000000'
            ctx.fillRect(0, 0, canvas.width, canvas.height)
            lastActiveClipId = null
          }
          
          // Update audio playback synchronized with video
          for (const audioClip of timelineAudioClips) {
            const audio = audioElements.get(audioClip.id)
            if (!audio) continue
            
            if (currentTime >= audioClip.position && currentTime < audioClip.position + audioClip.effectiveDuration) {
              const timeInAudio = currentTime - audioClip.position
              const targetAudioTime = audioClip.trimStart + timeInAudio
              
              if (Math.abs(audio.currentTime - targetAudioTime) > 0.2) {
                audio.currentTime = targetAudioTime
              }
              
              if (audio.paused && audio.readyState >= 2) {
                audio.play().catch(e => console.warn('Audio play error:', e))
              }
            } else {
              if (!audio.paused) {
                audio.pause()
              }
            }
          }
          
          // Update progress
          if (onProgress) {
            onProgress(Math.min(95, (frame / totalFrames) * 90))
          }
          
          // Schedule next frame
          if (frame < totalFrames - 1) {
            setTimeout(() => renderFrame(frame + 1), frameTime * 1000)
          } else {
            renderFrame(frame + 1) // Final frame
          }
        }
        
        // Start rendering
        renderFrame(0)
      }).catch(reject)
    })
  }

  // Handle export
  const handleExport = async () => {
    if (!campaignId || !campaign) return
    
    setIsExporting(true)
    setExportProgress(0)
    setError(null)
    
    try {
      // Record video from timeline
      setExportProgress(5)
      const videoBlob = await recordTimelineVideo((progress) => {
        setExportProgress(Math.min(90, 5 + progress * 0.85)) // 5% to 90%
      })
      
      // Upload to backend
      setExportProgress(90)
      const response = await manualEditing.exportEditUpload(campaignId, videoBlob)
      
      setExportProgress(100)
      
      // Refresh campaign data to get updated manual_editing_done flag
      try {
        const updatedCampaign = await getCampaign(campaignId)
        setCampaign(updatedCampaign)
      } catch (err) {
        console.warn('Failed to refresh campaign data:', err)
      }
      
      // Navigate back to campaign dashboard
      if (campaign.perfume_id) {
        navigate(`/perfumes/${campaign.perfume_id}`)
      } else {
        navigate('/dashboard')
      }
    } catch (err: any) {
      console.error('Export failed:', err)
      setError(err?.message || err?.response?.data?.detail || 'Export failed')
      setIsExporting(false)
      setExportProgress(0)
    }
  }
  
  if (isLoading) {
    return (
      <div className="min-h-screen bg-charcoal-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-accent-gold animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Loading editor...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="min-h-screen bg-charcoal-950 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-400 mb-4">Error</div>
          <p className="text-gray-400 mb-4">{error}</p>
          <Button onClick={() => navigate(-1)}>Go Back</Button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="h-screen flex flex-col bg-charcoal-950 overflow-hidden relative">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-charcoal-900 z-10">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate(-1)}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-xl font-semibold text-white">
            {campaign?.manual_editing_done ? 'Video' : 'Manual Video Editor'}
          </h1>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Media Library Button - Only show if manual editing not done */}
          {campaign && !campaign.manual_editing_done && (
            <Button
              variant="ghost"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className={`text-gray-400 hover:text-white ${isSidebarOpen ? 'bg-gray-700' : ''}`}
            >
              <FolderOpen className="w-4 h-4 mr-2" />
              Media Library
            </Button>
          )}
          {/* Download Button */}
          <Button
            onClick={handleDownload}
            disabled={isDownloading || isExporting}
            variant="ghost"
            className="text-gray-400 hover:text-white"
          >
            {isDownloading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                Download
              </>
            )}
          </Button>
          {isExporting && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Exporting... {Math.round(exportProgress)}%</span>
            </div>
          )}
          {!campaign?.manual_editing_done && (
          <Button
            onClick={handleExport}
              disabled={isExporting || isDownloading}
            className="bg-accent-gold text-charcoal-950 hover:bg-accent-gold-dark"
          >
            {isExporting ? 'Exporting...' : 'Export to Campaign'}
          </Button>
          )}
        </div>
      </div>
      
      {/* Main Content Area */}
      <div className="flex-1 flex min-h-0 relative">
      {/* Preview Player */}
        <div className={`flex-1 min-h-0 p-4 transition-all duration-300 ${isSidebarOpen ? 'mr-80' : ''}`}>
        <PreviewPlayer />
        </div>
        
        {/* Media Library Sidebar */}
        {campaign && !campaign.manual_editing_done && (
          <MediaLibrarySidebar
            isOpen={isSidebarOpen}
            onClose={() => setIsSidebarOpen(false)}
            campaign={campaign}
          />
        )}
      </div>
      
      {/* Timeline - Only show if manual editing not done */}
      {campaign && !campaign.manual_editing_done && (
        <div className={`h-64 border-t border-gray-700 transition-all duration-300 ${isSidebarOpen ? 'mr-80' : ''}`}>
          <Timeline />
        </div>
      )}
    </div>
  )
}


import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui'
import { PreviewPlayer } from '@/components/editing/PreviewPlayer'
import { Timeline } from '@/components/editing/Timeline'
import { useCampaigns } from '@/hooks/useCampaigns'
import { useEditorStore, type TimelineClip } from '@/stores/editorStore'
import { manualEditing } from '@/services/api'
import { ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react'

/**
 * Initialize timeline from campaign data
 */
const initializeTimelineFromCampaign = async (
  campaign: any,
  variationIndex: number = 0
) => {
  const campaignJson = typeof campaign.campaign_json === 'string'
    ? JSON.parse(campaign.campaign_json)
    : campaign.campaign_json
  
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
  const totalDuration = scenes.reduce((sum: number, s: any) => sum + (s.duration || 4), 0)
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
  const store = useEditorStore.getState()
  store.setTimelineVideoClips(videoClips)
  store.setTimelineAudioClips([audioClip])
  store.setTimelineTotalDuration(totalDuration)
  
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
  const [error, setError] = useState<string | null>(null)
  const [exportProgress, setExportProgress] = useState(0)
  
  // Load campaign and initialize timeline
  useEffect(() => {
    const loadCampaign = async () => {
      if (!campaignId) return
      
      try {
        setIsLoading(true)
        const data = await getCampaign(campaignId)
        setCampaign(data)
        
        // Check if manual editing is already done
        if (data.manual_editing_done) {
          // Redirect to results page - editing not allowed
          navigate(`/campaigns/${campaignId}/results`)
          return
        }
        
        // Get selected variation index
        const variationIndex = data.selected_variation_index || 0
        
        // Initialize timeline with scenes and music
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
  
  // Handle export
  const handleExport = async () => {
    if (!campaignId) return
    
    setIsExporting(true)
    setExportProgress(0)
    
    try {
      // Get timeline state from store
      const timelineState = useEditorStore.getState().getTimelineState()
      
      // Call export API
      const response = await manualEditing.exportEdit(campaignId, timelineState)
      const jobId = response.data.job_id
      
      // Poll for completion
      await pollExportJob(jobId)
      
      // Show success and redirect
      navigate(`/campaigns/${campaignId}/results`)
    } catch (err: any) {
      console.error('Export failed:', err)
      setError(err?.response?.data?.detail || 'Export failed')
      setIsExporting(false)
      setExportProgress(0)
    }
  }
  
  // Poll export job status
  const pollExportJob = async (jobId: string) => {
    const maxAttempts = 300 // 5 minutes max (1 second intervals)
    let attempts = 0
    
    while (attempts < maxAttempts) {
      try {
        // TODO: Add job status polling endpoint
        // For now, simulate progress
        setExportProgress(Math.min(100, (attempts / maxAttempts) * 100))
        
        // Wait 1 second before next poll
        await new Promise(resolve => setTimeout(resolve, 1000))
        attempts++
        
        // TODO: Check actual job status and break when complete
        // For now, just wait a fixed time (will be replaced with actual polling)
        if (attempts > 30) {
          break // Temporary: simulate completion after 30 seconds
        }
      } catch (err) {
        console.error('Error polling job:', err)
        throw err
      }
    }
    
    setExportProgress(100)
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
    <div className="h-screen flex flex-col bg-charcoal-950 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-charcoal-900">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => navigate(-1)}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-xl font-semibold text-white">Manual Video Editor</h1>
        </div>
        
        <div className="flex items-center gap-2">
          {isExporting && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Exporting... {Math.round(exportProgress)}%</span>
            </div>
          )}
          <Button
            onClick={handleExport}
            disabled={isExporting}
            className="bg-accent-gold text-charcoal-950 hover:bg-accent-gold-dark"
          >
            {isExporting ? 'Exporting...' : 'Export to Campaign'}
          </Button>
        </div>
      </div>
      
      {/* Preview Player */}
      <div className="flex-1 min-h-0 p-4">
        <PreviewPlayer />
      </div>
      
      {/* Timeline */}
      <div className="h-64 border-t border-gray-700">
        <Timeline />
      </div>
    </div>
  )
}


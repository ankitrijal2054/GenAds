# Phase 4: Manual Video Editing Feature - Complete Implementation Plan

**Version:** 1.0  
**Created:** January 20, 2025  
**Feature:** Manual timeline-based video editing with scene management  
**Estimated Timeline:** 35-45 hours (4.5-5.5 days)  
**Integration Point:** After prompt-based editing on VideoResults page

---

## Table of Contents

1. [Overview](#overview)
2. [User Experience Flow](#user-experience-flow)
3. [Architecture Design](#architecture-design)
4. [Component Adaptation Strategy](#component-adaptation-strategy)
5. [Backend Implementation Tasks](#backend-implementation-tasks)
6. [Frontend Implementation Tasks](#frontend-implementation-tasks)
7. [Implementation Phases](#implementation-phases)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Checklist](#deployment-checklist)

---

## Overview

### Feature Goal
Add a manual video editing interface where users can:
- Edit videos using a timeline with drag-and-drop
- Trim, split, and rearrange scenes
- Preview edits in real-time
- Export edited videos back to the campaign

### Key Principles
- ✅ **Seamless Integration**: Natural flow from VideoResults → Manual Editing
- ✅ **Scene-Based Editing**: Each generated scene becomes a timeline clip
- ✅ **Automatic Music**: Background music loads automatically from campaign
- ✅ **Web-Compatible**: Adapted from Electron app to work with S3/API
- ✅ **Export to Campaign**: Edited videos replace original in campaign

### Technical Constraints
- Editing components adapted from Electron app (`editing/` folder)
- Videos stored in S3 (must download for editing, upload after export)
- Timeline state managed via Zustand store
- Export via backend API (FFmpeg processing)

---

## User Experience Flow

### Complete User Journey

```
USER COMPLETES PROMPT-BASED EDITING
→ On VideoResults page
  ↓
USER CLICKS "Next" BUTTON (new button)
  ↓
NAVIGATE TO MANUAL EDITING PAGE
┌─────────────────────────────────────────────────────────┐
│ Manual Video Editor                                      │
│ ─────────────────────────────────────────────────────── │
│                                                         │
│ TOP SECTION: Video Preview Player (60% height)         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │         [Video Preview - Playing Timeline]          │ │
│ │    [Play] [Pause] [Mute] [Volume] [Fullscreen]     │ │
│ │    [Timeline Scrubber - Shows Current Position]     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ BOTTOM SECTION: Timeline (40% height)                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ VIDEO TRACK                                          │ │
│ │ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                    │ │
│ │ │ S1  │ │ S2  │ │ S3  │ │ S4  │ [Mute] [Lock]     │ │
│ │ └─────┘ └─────┘ └─────┘ └─────┘                    │ │
│ │                                                      │ │
│ │ AUDIO TRACK                                          │ │
│ │ ┌──────────────────────────────────────────────┐   │ │
│ │ │         [Music Track - Full Duration]        │   │ │
│ │ └──────────────────────────────────────────────┘   │ │
│ │                                                      │ │
│ │ [Zoom In] [Zoom Out] [Fit to Screen] [Time: 0:30]  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ TOP RIGHT: Action Buttons                               │
│ [Save Draft] [Export to Campaign] [Cancel]             │
└─────────────────────────────────────────────────────────┘
  ↓
USER EDITS VIDEO
- Drag scenes to reorder
- Trim scene start/end points
- Split scenes at specific times
- Adjust volume/mute tracks
  ↓
USER CLICKS "EXPORT TO CAMPAIGN"
  ↓
BACKEND PROCESSING (2-5 minutes)
1. Download all scene videos from S3
2. Download music from S3
3. Apply timeline edits (trim, split, reorder)
4. Render final video with FFmpeg
5. Upload new final video to S3 (replaces old)
6. Update campaign_json with edit metadata
  ↓
EXPORT COMPLETE
→ Redirect back to VideoResults page
→ Show success message
→ Video automatically reloads with edited version
```

---

## Architecture Design

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND (React)                       │
├─────────────────────────────────────────────────────────┤
│ ManualEditing.tsx (New page) ← NEW                     │
│  ├─ PreviewPlayer (Adapted from editing/)              │
│  ├─ Timeline (Adapted from editing/)                  │
│  └─ ExportControls (New component)                    │
│                                                         │
│ Adapted Components (from editing/ folder):            │
│  ├─ Timeline.tsx (Web-adapted)                       │
│  ├─ TimelineClip.tsx (Web-adapted)                   │
│  ├─ PreviewPlayer.tsx (Web-adapted)                  │
│  └─ editorStore.ts (Web-adapted)                     │
└─────────────────────────────────────────────────────────┘
                          ↓ HTTP API
┌─────────────────────────────────────────────────────────┐
│                 BACKEND API (FastAPI)                  │
├─────────────────────────────────────────────────────────┤
│ editing.py (UPDATE)                                     │
│  ├─ GET /api/campaigns/{id}/editing/scenes             │
│  ├─ GET /api/campaigns/{id}/editing/music              │
│  └─ POST /api/campaigns/{id}/editing/export            │
└─────────────────────────────────────────────────────────┘
                          ↓ Enqueue Job
┌─────────────────────────────────────────────────────────┐
│                  RQ WORKER (Background)                │
├─────────────────────────────────────────────────────────┤
│ edit_pipeline.py (UPDATE)                              │
│  └─ ManualEditExportPipeline class                    │
│      ├─ Step 1: Load campaign + timeline data         │
│      ├─ Step 2: Download scenes from S3                │
│      ├─ Step 3: Download music from S3                 │
│      ├─ Step 4: Apply timeline edits (FFmpeg)          │
│      ├─ Step 5: Render final video                     │
│      ├─ Step 6: Upload to S3 (replace old)             │
│      └─ Step 7: Update campaign_json                   │
└─────────────────────────────────────────────────────────┘
                          ↓ Storage
┌─────────────────────────────────────────────────────────┐
│                    AWS S3 (Storage)                     │
├─────────────────────────────────────────────────────────┤
│ brands/{id}/perfumes/{id}/campaigns/{id}/variations/0/│
│  ├─ draft/                                             │
│  │   ├─ scene_1_bg.mp4                                 │
│  │   ├─ scene_2_bg.mp4                                 │
│  │   ├─ scene_3_bg.mp4                                 │
│  │   ├─ scene_4_bg.mp4                                 │
│  │   └─ music.mp3                                      │
│  └─ final_video.mp4 (REPLACED after export)           │
└─────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
1. PAGE LOAD
   User navigates to /campaigns/{id}/edit
   ↓
2. INITIALIZE EDITOR
   GET /api/campaigns/{id}/editing/scenes
   GET /api/campaigns/{id}/editing/music
   ↓
3. LOAD INTO TIMELINE
   Frontend:
   - Parse scene data from campaign_json
   - Create TimelineClip objects for each scene
   - Create TimelineClip for music track
   - Initialize editorStore with clips
   ↓
4. USER EDITS
   - Drag clips to reorder
   - Trim clip start/end
   - Split clips
   - Adjust volume/mute
   - Timeline state stored in Zustand store
   ↓
5. EXPORT REQUEST
   POST /api/campaigns/{id}/editing/export
   Body: { timelineState: {...} }
   ↓
6. BACKEND PROCESSING
   - Download all scenes from S3
   - Download music from S3
   - Apply edits (trim, split, reorder) via FFmpeg
   - Render final video
   - Upload to S3 (replaces old final_video.mp4)
   - Update campaign_json with edit metadata
   ↓
7. EXPORT COMPLETE
   Status: "completed"
   Response: { new_video_url: "s3://...", edit_id: "..." }
   ↓
8. FRONTEND REDIRECT
   Navigate back to VideoResults page
   Show success toast
   Video automatically reloads
```

---

## Component Adaptation Strategy

### Key Adaptations Required

#### 1. Video Source Handling

**File:** `editing/src/renderer/src/components/PreviewPlayer.tsx`

**Current (Electron):**
```typescript
function getVideoSrc(filePath: string): string {
  const normalizedPath = filePath.replace(/\\/g, '/')
  const pathNoLeadingScheme = normalizedPath.replace(/^\/+/, '/')
  return `clipforge://${encodeURI(pathNoLeadingScheme)}`
}
```

**Adapted (Web):**
```typescript
function getVideoSrc(filePath: string): string {
  // If it's already a URL (blob:, http:, https:)
  if (filePath.startsWith('blob:') || filePath.startsWith('http')) {
    return filePath
  }
  // If it's an S3 URL, use directly
  if (filePath.startsWith('s3://') || filePath.includes('amazonaws.com')) {
    return filePath
  }
  // Otherwise, assume it needs API proxy
  return filePath
}
```

#### 2. Export Functionality

**File:** `editing/src/stores/editorStore.ts`

**Current (Electron IPC):**
```typescript
await window.api.trimExport({...})
```

**Adapted (Web API):**
```typescript
// Replace with API call
const response = await fetch(`/api/campaigns/${campaignId}/editing/export`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    timeline_state: timelineState,
    export_settings: exportSettings
  })
})
```

#### 3. File Import Handling

**Current:** Electron file system access

**Adapted:** 
- Scenes loaded from campaign data (S3 URLs)
- Music loaded from campaign data (S3 URL)
- No file picker needed (auto-loaded from campaign)

#### 4. State Initialization

**New Function:** Initialize timeline from campaign data

```typescript
// In ManualEditing.tsx
const initializeTimelineFromCampaign = (campaign: Campaign) => {
  const campaignJson = typeof campaign.campaign_json === 'string'
    ? JSON.parse(campaign.campaign_json)
    : campaign.campaign_json
  
  const scenes = campaignJson.scenes || []
  const musicUrl = campaignJson.audio_url || ''
  
  // Create video clips for each scene
  const videoClips: TimelineClip[] = scenes.map((scene, index) => ({
    id: `scene-${index}`,
    libraryId: `scene-${index}`,
    name: `Scene ${index + 1} - ${scene.role}`,
    trackType: 'video',
    duration: scene.duration,
    trimStart: 0,
    trimEnd: scene.duration,
    effectiveDuration: scene.duration,
    position: scenes.slice(0, index).reduce((sum, s) => sum + s.duration, 0),
    color: getRandomColor()
  }))
  
  // Create audio clip for music
  const audioClip: TimelineClip = {
    id: 'music-track',
    libraryId: 'music-track',
    name: 'Background Music',
    trackType: 'audio',
    duration: calculateTotalDuration(scenes),
    trimStart: 0,
    trimEnd: calculateTotalDuration(scenes),
    effectiveDuration: calculateTotalDuration(scenes),
    position: 0,
    color: undefined
  }
  
  // Initialize store
  useEditorStore.getState().setTimelineVideoClips(videoClips)
  useEditorStore.getState().setTimelineAudioClips([audioClip])
  
  // Set video sources (S3 URLs)
  scenes.forEach((scene, index) => {
    const videoUrl = getSceneS3Url(campaign, index)
    // Store in a clips map for PreviewPlayer to access
    useEditorStore.getState().setClipSource(`scene-${index}`, videoUrl)
  })
  
  useEditorStore.getState().setClipSource('music-track', musicUrl)
}
```

---

## Backend Implementation Tasks

### Task 1: Add Editing API Endpoints (3-4 hours)

**File:** `backend/app/api/editing.py` (UPDATE)

**New Endpoints:**

**Endpoint 1: GET /api/campaigns/{campaign_id}/editing/scenes**
- Load campaign from database
- **Check if `manual_editing_done = True`** - if so, return 400 error (scenes no longer exist)
- Extract scenes from campaign_json
- Construct S3 URLs for each scene video
- Return list of SceneInfo objects with S3 URLs

**Endpoint 2: GET /api/campaigns/{campaign_id}/editing/music**
- Load campaign from database
- **Check if `manual_editing_done = True`** - if so, return 400 error (music no longer exists)
- Extract audio_url from campaign_json
- Construct S3 URL for music
- Return MusicInfo object

**Endpoint 3: POST /api/campaigns/{campaign_id}/editing/export**
- Validate campaign exists and user owns it
- **Check if `manual_editing_done = True`** - if so, return 400 error (already finalized)
- Validate timeline state structure
- Enqueue export job via RQ
- Return job_id and estimated time
- **Note:** Export pipeline will:
  - Set `manual_editing_done = True`
  - Delete all draft files from S3 (scenes, music)
  - Keep only final_video.mp4

**Note:** No `/editing/start` endpoint needed. Flag is set only when user exports.

**Pydantic Schemas:**
```python
class SceneInfo(BaseModel):
    scene_index: int
    scene_id: int
    role: str
    duration: int
    video_url: str  # S3 URL
    background_prompt: str

class MusicInfo(BaseModel):
    audio_url: str  # S3 URL
    duration: float

class TimelineState(BaseModel):
    video_clips: List[TimelineClipState]
    audio_clips: List[TimelineClipState]
    total_duration: float

class TimelineClipState(BaseModel):
    id: str
    library_id: str
    name: str
    track_type: str
    duration: float
    trim_start: float
    trim_end: float
    effective_duration: float
    position: float

class ExportEditRequest(BaseModel):
    timeline_state: TimelineState
    export_settings: Optional[Dict[str, Any]] = None

class ExportEditResponse(BaseModel):
    job_id: str
    estimated_duration_seconds: int
    message: str
```

---

### Task 2: Create Manual Edit Export Pipeline (5-6 hours)

**File:** `backend/app/jobs/edit_pipeline.py` (UPDATE)

**New Class:** `ManualEditExportPipeline`

**Pipeline Steps:**

1. **Load Campaign Data**
   - Load campaign, perfume, brand from database
   - Parse campaign_json
   - Extract scene metadata

2. **Download Scene Videos from S3**
   - For each scene in timeline:
     - Download scene video from S3 to /tmp
     - Store local path for processing

3. **Download Music from S3**
   - Download music file from S3 to /tmp
   - Store local path

4. **Apply Timeline Edits**
   - For each video clip:
     - Apply trim (if trim_start > 0 or trim_end < duration)
     - Apply split (if clip was split)
   - Reorder clips according to timeline positions
   - Concatenate trimmed/reordered clips

5. **Apply Audio Edits**
   - Trim music to match video duration
   - Apply volume adjustments (if any)
   - Mix with video audio (if not muted)

6. **Render Final Video**
   - Use Renderer service to combine:
     - Edited video clips (concatenated)
     - Music track (trimmed/adjusted)
   - Output to /tmp/final_edited.mp4

7. **Upload to S3**
   - Upload final video to S3 (replaces old final_video.mp4)

8. **Cleanup S3 Draft Files**
   - Delete all scene videos from S3 (scene_1_bg.mp4, scene_2_bg.mp4, etc.)
   - Delete music file from S3 (music.mp3)
   - Keep only final_video.mp4 in S3
   - **Purpose:** Once manual editing is done, only final video remains

9. **Update Database**
   - Set `manual_editing_done = True`
   - Update campaign status to "completed"
   - Store edit history in campaign_json
   - **Note:** This locks the campaign - no more editing possible

**Key Implementation:**
```python
class ManualEditExportPipeline:
    def __init__(self, campaign_id: UUID, timeline_state: Dict[str, Any]):
        self.campaign_id = campaign_id
        self.timeline_state = timeline_state
        # ... initialization
    
    async def run(self) -> Dict[str, Any]:
        # Step 1: Load campaign
        campaign = get_campaign_by_id(self.db, self.campaign_id)
        campaign_json = self._parse_campaign_json(campaign)
        
        # Step 2: Download scenes
        scene_paths = []
        for clip in self.timeline_state['video_clips']:
            scene_index = self._extract_scene_index(clip['library_id'])
            s3_url = get_scene_s3_url(...)
            local_path = await self._download_from_s3(s3_url)
            scene_paths.append({
                'path': local_path,
                'trim_start': clip['trim_start'],
                'trim_end': clip['trim_end'],
                'position': clip['position']
            })
        
        # Step 3: Download music
        music_s3_url = campaign_json.get('audio_url')
        music_path = await self._download_from_s3(music_s3_url)
        
        # Step 4: Apply edits
        edited_scenes = []
        for scene in sorted(scene_paths, key=lambda x: x['position']):
            # Trim if needed
            if scene['trim_start'] > 0 or scene['trim_end'] < scene['duration']:
                trimmed = await self._trim_video(
                    scene['path'],
                    scene['trim_start'],
                    scene['trim_end']
                )
                edited_scenes.append(trimmed)
            else:
                edited_scenes.append(scene['path'])
        
        # Step 5: Concatenate scenes
        concatenated_video = await self._concatenate_videos(edited_scenes)
        
        # Step 6: Mix audio
        final_video = await self._mix_audio(concatenated_video, music_path)
        
        # Step 7: Upload to S3
        s3_result = await upload_final_video(...)
        
        # Step 8: Update database
        self._update_campaign_json(campaign, edit_metadata)
        
        return {
            'success': True,
            'new_video_url': s3_result['url'],
            'edit_id': str(uuid.uuid4())
        }
```

---

### Task 3: Add FFmpeg Helper Functions (2-3 hours)

**File:** `backend/app/services/video_processor.py` (NEW)

**Functions:**
- `trim_video(input_path, start_time, end_time, output_path)`
- `concatenate_videos(video_paths, output_path)`
- `mix_audio(video_path, audio_path, output_path, volume=1.0)`
- `get_video_duration(video_path)`

**Implementation:**
```python
import subprocess
import os

async def trim_video(
    input_path: str,
    start_time: float,
    end_time: float,
    output_path: str
) -> str:
    """Trim video using FFmpeg."""
    duration = end_time - start_time
    
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',  # Stream copy for speed
        output_path
    ]
    
    result = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    await result.wait()
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed: {result.stderr.decode()}")
    
    return output_path

async def concatenate_videos(
    video_paths: List[str],
    output_path: str
) -> str:
    """Concatenate multiple videos using FFmpeg."""
    # Create concat file
    concat_file = output_path.replace('.mp4', '_concat.txt')
    with open(concat_file, 'w') as f:
        for path in video_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")
    
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]
    
    result = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    await result.wait()
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {result.stderr.decode()}")
    
    os.unlink(concat_file)
    return output_path
```

---

## Frontend Implementation Tasks

### Task 4: Create ManualEditing Page (4-5 hours)

**File:** `frontend/src/pages/ManualEditing.tsx` (NEW)

**Requirements:**
- Load campaign data on mount
- **Check if `manual_editing_done = True`** - if so, redirect to VideoResults (editing not allowed)
- Initialize timeline with scenes and music (only if not done)
- Render PreviewPlayer and Timeline components
- Handle export button click
- Show loading state during export
- **Export sets `manual_editing_done = True` and cleans up S3**
- Redirect to VideoResults on success

**Component Structure:**
```typescript
export const ManualEditing: React.FC = () => {
  const { campaignId } = useParams<{ campaignId: string }>()
  const navigate = useNavigate()
  const { getCampaign } = useCampaigns()
  
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Initialize timeline from campaign
  useEffect(() => {
    const loadCampaign = async () => {
      try {
        const data = await getCampaign(campaignId!)
        setCampaign(data)
        
        // Check if manual editing is already done
        if (data.manual_editing_done) {
          // Redirect to results page - editing not allowed
          navigate(`/campaigns/${campaignId}/results`)
          return
        }
        
        // Initialize timeline with scenes and music
        initializeTimelineFromCampaign(data)
      } catch (err) {
        setError('Failed to load campaign')
      } finally {
        setIsLoading(false)
      }
    }
    
    if (campaignId) {
      loadCampaign()
    }
  }, [campaignId, navigate])
  
  const handleExport = async () => {
    setIsExporting(true)
    try {
      const timelineState = useEditorStore.getState().getTimelineState()
      const response = await api.post(
        `/api/campaigns/${campaignId}/editing/export`,
        { timeline_state: timelineState }
      )
      
      // Poll for completion
      await pollExportJob(response.data.job_id)
      
      // Redirect to results page
      navigate(`/campaigns/${campaignId}/results`)
    } catch (err) {
      setError('Export failed')
    } finally {
      setIsExporting(false)
    }
  }
  
  if (isLoading) {
    return <LoadingSpinner />
  }
  
  return (
    <div className="manual-editing-page h-screen flex flex-col">
      {/* Header */}
      <div className="header p-4 border-b">
        <h1>Manual Video Editor</h1>
        <div className="actions">
          <Button onClick={handleExport} disabled={isExporting}>
            {isExporting ? 'Exporting...' : 'Export to Campaign'}
          </Button>
          <Button onClick={() => navigate(-1)}>Cancel</Button>
        </div>
      </div>
      
      {/* Preview Player */}
      <div className="preview-section flex-1">
        <PreviewPlayer />
      </div>
      
      {/* Timeline */}
      <div className="timeline-section h-64">
        <Timeline />
      </div>
    </div>
  )
}
```

---

### Task 5: Adapt PreviewPlayer Component (2-3 hours)

**File:** `frontend/src/components/editing/PreviewPlayer.tsx` (NEW - adapted from editing/)

**Key Changes:**
1. Replace `getVideoSrc()` function (remove Electron protocol)
2. Update video source handling for S3 URLs
3. Remove Electron-specific imports
4. Update import paths to match frontend structure

**Adaptation:**
```typescript
// Remove Electron-specific function
// function getVideoSrc(filePath: string): string {
//   return `clipforge://${encodeURI(...)}`
// }

// Replace with web-compatible version
function getVideoSrc(filePath: string): string {
  // If it's already a URL, use directly
  if (filePath.startsWith('http') || filePath.startsWith('blob:')) {
    return filePath
  }
  // If it's an S3 URL, may need API proxy for CORS
  if (filePath.includes('amazonaws.com')) {
    // Use API proxy endpoint
    return `/api/video/proxy?url=${encodeURIComponent(filePath)}`
  }
  return filePath
}
```

---

### Task 6: Adapt Timeline Component (2-3 hours)

**File:** `frontend/src/components/editing/Timeline.tsx` (NEW - adapted from editing/)

**Key Changes:**
1. Update import paths
2. Ensure drag-and-drop works in web context
3. Update video source handling
4. Remove Electron-specific code

---

### Task 7: Adapt EditorStore (2-3 hours)

**File:** `frontend/src/stores/editorStore.ts` (NEW - adapted from editing/)

**Key Changes:**
1. Remove Electron IPC calls
2. Add web-compatible export function
3. Add timeline state getter for export
4. Update persistence (use localStorage instead of Electron storage)

**Export Function:**
```typescript
exportTimeline: async (campaignId: string) => {
  const state = get()
  const timelineState = {
    video_clips: state.timelineVideoClips.map(clip => ({
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
    audio_clips: state.timelineAudioClips.map(clip => ({
      // ... same structure
    })),
    total_duration: calculateTotalDuration(state.timelineVideoClips)
  }
  
  return timelineState
}
```

---

### Task 8: Add "Manual Edit" Button to VideoResults (1 hour)

**File:** `frontend/src/pages/VideoResults.tsx` (UPDATE)

**Add Button:**
```typescript
{/* Only show if manual editing not done */}
{isCampaign && !project?.manual_editing_done && (
  <Button
    variant="hero"
    onClick={() => navigate(`/campaigns/${id}/edit`)}
    className="gap-2"
  >
    <Edit className="w-4 h-4" />
    Manual Edit
  </Button>
)}
```

**Disable Prompt-Based Editing:**
```typescript
{/* RIGHT COLUMN: Scene Sidebar - Only show if manual editing not done */}
{isCampaign && !project?.manual_editing_done && (
  <div className="lg:col-span-4 flex flex-col h-full">
    <SceneSidebar
      campaignId={id}
      variationIndex={selectedVariationIndex}
      onVideoUpdate={handleVideoUpdate}
      onEditStart={handleEditStart}
      onEditError={handleEditError}
      className="h-full"
    />
  </div>
)}

{/* Show message if manual editing is done */}
{isCampaign && project?.manual_editing_done && (
  <div className="lg:col-span-4 flex flex-col h-full items-center justify-center p-8">
    <div className="text-center">
      <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-white mb-2">
        Manual Editing Complete
      </h3>
      <p className="text-gray-400 text-sm mb-4">
        This campaign has been finalized. Only the final video is available.
      </p>
      <p className="text-xs text-gray-500">
        Draft files have been removed. No further editing is possible.
      </p>
    </div>
  </div>
)}
```

**Placement:** Next to Download button in header actions. Hide SceneSidebar if `manual_editing_done` is true.

---

### Task 9: Add Route to App (15 minutes)

**File:** `frontend/src/App.tsx` (UPDATE)

**Add Route:**
```typescript
<Route
  path="/campaigns/:campaignId/edit"
  element={
    <ProtectedRoute>
      <ManualEditing />
    </ProtectedRoute>
  }
/>
```

---

### Task 10: Create API Client Methods (30 minutes)

**File:** `frontend/src/services/api.ts` (UPDATE)

**Add Methods:**
```typescript
export const editing = {
  getEditingScenes: (campaignId: string) =>
    api.get(`/api/campaigns/${campaignId}/editing/scenes`),
  
  getEditingMusic: (campaignId: string) =>
    api.get(`/api/campaigns/${campaignId}/editing/music`),
  
  exportEdit: (campaignId: string, timelineState: any) =>
    api.post(`/api/campaigns/${campaignId}/editing/export`, {
      timeline_state: timelineState
    })
}
```

---

## Implementation Phases

### Phase 1: Component Adaptation (8-10 hours)

**Goal:** Adapt editing components for web use

**Tasks:**
- [ ] Task 5: Adapt PreviewPlayer (2-3 hours)
- [ ] Task 6: Adapt Timeline (2-3 hours)
- [ ] Task 7: Adapt EditorStore (2-3 hours)
- [ ] Copy and adapt supporting components (TimelineClip, TrackHeader, etc.) (1-2 hours)

**Testing:**
- [ ] Components render without errors
- [ ] Video playback works with S3 URLs
- [ ] Timeline drag-and-drop works
- [ ] State management works correctly

---

### Phase 2: Backend API (8-10 hours)

**Goal:** Complete backend infrastructure

**Tasks:**
- [ ] Task 1: Add Editing API Endpoints (3-4 hours)
- [ ] Task 2: Create Manual Edit Export Pipeline (5-6 hours)

**Testing:**
- [ ] API endpoints return correct data
- [ ] Export pipeline processes correctly
- [ ] S3 upload/download works
- [ ] FFmpeg operations succeed

---

### Phase 3: Frontend Integration (6-8 hours)

**Goal:** Integrate adapted components into GenAds

**Tasks:**
- [ ] Task 4: Create ManualEditing Page (4-5 hours)
- [ ] Task 8: Add "Next" Button (1 hour)
- [ ] Task 9: Add Route (15 minutes)
- [ ] Task 10: Add API Client Methods (30 minutes)
- [ ] Create timeline initialization logic (1-2 hours)

**Testing:**
- [ ] Page loads correctly
- [ ] Timeline initializes with scenes
- [ ] Music loads automatically
- [ ] Export flow works end-to-end

---

### Phase 4: FFmpeg Integration (2-3 hours)

**Goal:** Complete video processing functions

**Tasks:**
- [ ] Task 3: Add FFmpeg Helper Functions (2-3 hours)

**Testing:**
- [ ] Video trimming works
- [ ] Video concatenation works
- [ ] Audio mixing works
- [ ] All operations complete successfully

---

### Phase 5: End-to-End Testing (4-5 hours)

**Goal:** Full integration testing

**Test Scenarios:**
1. **Happy Path:**
   - Navigate to editing page → Timeline loads → Edit video → Export → Redirect → Video updates

2. **Edit Operations:**
   - Trim scene start/end
   - Split scene
   - Reorder scenes
   - Mute/unmute tracks
   - Adjust volume

3. **Error Cases:**
   - Invalid campaign ID
   - Missing scenes
   - Export failure
   - Network errors

4. **Edge Cases:**
   - Very short videos
   - Very long videos
   - Multiple rapid edits
   - Export while editing

---

### Phase 6: Polish & Documentation (2-3 hours)

**Goal:** Final polish and documentation

**Tasks:**
- [ ] Code review and cleanup
- [ ] Add inline comments
- [ ] Update API documentation
- [ ] Create user guide
- [ ] Performance optimization

---

## Testing Strategy

### Unit Tests

**Backend:**
- Test FFmpeg helper functions
- Test export pipeline steps
- Test S3 operations

**Frontend:**
- Test timeline initialization
- Test state management
- Test component rendering

### Integration Tests

- Test API endpoints
- Test export job execution
- Test S3 upload/download

### End-to-End Tests

- Complete editing flow
- Export and verify video
- Check video quality

---

## Deployment Checklist

### Pre-Deployment

- [ ] All phases completed
- [ ] All tests passing
- [ ] Code reviewed
- [ ] TypeScript compiles
- [ ] No console errors

### Backend Deployment

- [ ] Deploy backend to Railway
- [ ] Verify FFmpeg available
- [ ] Test export pipeline
- [ ] Monitor worker logs

### Frontend Deployment

- [ ] Build frontend
- [ ] Deploy to Vercel
- [ ] Test production build
- [ ] Verify API connectivity

### Post-Deployment

- [ ] Test editing flow on production
- [ ] Verify S3 operations
- [ ] Check export quality
- [ ] Monitor performance

---

## Timeline Summary

| Phase | Duration | Tasks |
|-------|----------|-------|
| Phase 1: Component Adaptation | 8-10 hours | PreviewPlayer, Timeline, EditorStore |
| Phase 2: Backend API | 8-10 hours | API endpoints, Export pipeline |
| Phase 3: Frontend Integration | 6-8 hours | ManualEditing page, Routes, API client |
| Phase 4: FFmpeg Integration | 2-3 hours | Video processing functions |
| Phase 5: E2E Testing | 4-5 hours | Integration testing |
| Phase 6: Polish & Docs | 2-3 hours | Code review, documentation |
| **TOTAL** | **30-39 hours** | **~4-5 days** |

---

## Success Metrics

### Technical Metrics

- **Export Success Rate:** >95%
- **Export Time:** <5 minutes for typical video
- **Video Quality:** No degradation from edits
- **Error Rate:** <5% of exports fail

### User Experience Metrics

- **Time to Edit:** User completes edits in <5 minutes
- **Satisfaction:** Edited video matches expectations >80%
- **Usage:** 20%+ of campaigns use manual editing

---

---

## Critical Restriction: Manual Editing Finalization

### Overview
Once a user completes manual editing and exports, the campaign is **permanently finalized**. All draft files are removed from S3, and only the final video remains. No further editing is possible.

### Implementation

**Database Field:**
- `campaigns.manual_editing_done` (Boolean, default: false)
- Set to `true` when user exports from manual editing
- Once set, cannot be reverted (one-way flag)

**Backend Export Pipeline:**
- Sets `manual_editing_done = True` after successful export
- Deletes all scene videos from S3 (scene_1_bg.mp4, scene_2_bg.mp4, etc.)
- Deletes music file from S3 (music.mp3)
- Keeps only final_video.mp4 in S3

**Frontend Behavior:**
- **VideoResults Page:**
  - Hide "Manual Edit" button if `manual_editing_done = true`
  - Hide SceneSidebar (prompt-based editing) if flag is true
  - Show message: "Manual Editing Complete - Campaign finalized"
  - Only final video is available (no scenes for editing)

- **ManualEditing Page:**
  - Check if `manual_editing_done = true` on mount
  - If true, redirect to VideoResults (editing not allowed)
  - If false, allow editing and timeline initialization

### User Experience

**Before Manual Editing Export:**
- User can use prompt-based editing (SceneSidebar visible)
- User can enter/exit manual editing multiple times
- "Manual Edit" button visible
- All scene files available in S3

**After Manual Editing Export:**
- `manual_editing_done = True` set in database
- All draft files removed from S3 (scenes, music)
- Only final_video.mp4 remains in S3
- Prompt-based editing disabled (SceneSidebar hidden)
- "Manual Edit" button hidden
- Campaign is "finalized" - no more editing possible
- Only final video can be viewed/downloaded

### S3 Cleanup

**Before Export:**
```
brands/{id}/perfumes/{id}/campaigns/{id}/variations/0/
├── draft/
│   ├── scene_1_bg.mp4
│   ├── scene_2_bg.mp4
│   ├── scene_3_bg.mp4
│   ├── scene_4_bg.mp4
│   └── music.mp3
└── final_video.mp4
```

**After Export:**
```
brands/{id}/perfumes/{id}/campaigns/{id}/variations/0/
└── final_video.mp4  (only this remains)
```

**Rationale:**
- Prevents conflicts between editing modes
- Ensures video consistency
- Reduces S3 storage costs
- Clear workflow: prompt-based → manual → finalized (one-way)
- Once finalized, campaign is immutable

---

**This comprehensive plan provides everything needed to implement manual video editing. Each task has clear requirements and acceptance criteria. Ready to start implementation!** 🚀


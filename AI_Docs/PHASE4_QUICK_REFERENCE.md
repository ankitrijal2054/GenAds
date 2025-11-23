# Phase 4: Manual Editing - Quick Reference Guide

**Version:** 1.0  
**Purpose:** Quick reference for implementing manual video editing feature

---

## 🎯 Goal

Add manual timeline-based video editing after prompt-based editing. Users can trim, split, reorder scenes, and export back to campaign.

---

## 📋 Key Files to Create/Modify

### Backend
- `backend/app/api/editing.py` - Add 3 new endpoints
- `backend/app/jobs/edit_pipeline.py` - Add `ManualEditExportPipeline` class
- `backend/app/services/video_processor.py` - NEW: FFmpeg helper functions

### Frontend
- `frontend/src/pages/ManualEditing.tsx` - NEW: Main editing page
- `frontend/src/components/editing/PreviewPlayer.tsx` - NEW: Adapted from editing/
- `frontend/src/components/editing/Timeline.tsx` - NEW: Adapted from editing/
- `frontend/src/stores/editorStore.ts` - NEW: Adapted from editing/
- `frontend/src/pages/VideoResults.tsx` - Add "Manual Edit" button
- `frontend/src/App.tsx` - Add route `/campaigns/:campaignId/edit`

---

## 🔧 Critical Adaptations

### 1. Video Source (PreviewPlayer.tsx)

**Remove:**
```typescript
function getVideoSrc(filePath: string): string {
  return `clipforge://${encodeURI(...)}`
}
```

**Replace with:**
```typescript
function getVideoSrc(filePath: string): string {
  if (filePath.startsWith('http') || filePath.startsWith('blob:')) {
    return filePath
  }
  if (filePath.includes('amazonaws.com')) {
    return `/api/video/proxy?url=${encodeURIComponent(filePath)}`
  }
  return filePath
}
```

### 2. Export Function (editorStore.ts)

**Remove:**
```typescript
await window.api.trimExport({...})
```

**Replace with:**
```typescript
const response = await api.post(`/api/campaigns/${campaignId}/editing/export`, {
  timeline_state: timelineState
})
```

### 3. Timeline Initialization

```typescript
const initializeTimelineFromCampaign = (campaign: Campaign) => {
  const campaignJson = typeof campaign.campaign_json === 'string'
    ? JSON.parse(campaign.campaign_json)
    : campaign.campaign_json
  
  const scenes = campaignJson.scenes || []
  
  // Create video clips
  const videoClips = scenes.map((scene, index) => ({
    id: `scene-${index}`,
    libraryId: `scene-${index}`,
    name: `Scene ${index + 1} - ${scene.role}`,
    trackType: 'video',
    duration: scene.duration,
    trimStart: 0,
    trimEnd: scene.duration,
    effectiveDuration: scene.duration,
    position: scenes.slice(0, index).reduce((sum, s) => sum + s.duration, 0)
  }))
  
  // Create audio clip
  const audioClip = {
    id: 'music-track',
    libraryId: 'music-track',
    name: 'Background Music',
    trackType: 'audio',
    duration: calculateTotalDuration(scenes),
    trimStart: 0,
    trimEnd: calculateTotalDuration(scenes),
    effectiveDuration: calculateTotalDuration(scenes),
    position: 0
  }
  
  useEditorStore.getState().setTimelineVideoClips(videoClips)
  useEditorStore.getState().setTimelineAudioClips([audioClip])
}
```

---

## 🚀 Implementation Order

1. **Phase 1:** Adapt components (PreviewPlayer, Timeline, EditorStore)
2. **Phase 2:** Backend API endpoints
3. **Phase 3:** Export pipeline
4. **Phase 4:** Frontend integration
5. **Phase 5:** Testing

---

## 📡 API Endpoints

### GET /api/campaigns/{id}/editing/scenes
Returns scene data with S3 URLs

### GET /api/campaigns/{id}/editing/music
Returns music S3 URL

### POST /api/campaigns/{id}/editing/export
Exports edited video, sets `manual_editing_done = True`, cleans up S3 files

**Note:** Export sets `manual_editing_done = True` and removes all draft files from S3

---

## 🔄 Export Pipeline Flow

1. Download scenes from S3 → /tmp
2. Download music from S3 → /tmp
3. Apply edits (trim, split, reorder) via FFmpeg
4. Concatenate edited scenes
5. Mix audio
6. Upload final video to S3 (replaces old)
7. Update campaign_json

---

## ✅ Acceptance Criteria

- [ ] Timeline loads with all scenes from campaign
- [ ] Music loads automatically
- [ ] Can trim, split, reorder scenes
- [ ] Preview shows edited video
- [ ] Export replaces campaign video
- [ ] Redirects to VideoResults after export
- [ ] Video updates automatically on results page
- [ ] `manual_editing_done` flag set when exporting from manual editing
- [ ] Prompt-based editing disabled when flag is true
- [ ] SceneSidebar hidden when flag is true
- [ ] All draft files removed from S3 after export
- [ ] Only final_video.mp4 remains in S3
- [ ] Manual editing page redirects if flag is true

---

## 🐛 Common Issues

**Video won't load:**
- Check S3 URL format
- Verify CORS settings
- Use API proxy for S3 URLs

**Timeline not initializing:**
- Check campaign_json structure
- Verify scene data format
- Check store initialization

**Export fails:**
- Verify FFmpeg installed
- Check S3 permissions
- Review pipeline logs

---

## 📚 Full Documentation

See `PHASE4_MANUAL_EDITING_IMPLEMENTATION_PLAN.md` for complete details.


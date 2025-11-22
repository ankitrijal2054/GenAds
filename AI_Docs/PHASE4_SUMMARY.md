# Phase 4: Manual Video Editing - Executive Summary

**Feature:** Manual timeline-based video editing  
**Timeline:** 35-45 hours (4.5-5.5 days)  
**Status:** Planning Complete

---

## Overview

Add a manual video editing interface where users can edit generated videos using a timeline editor. This feature comes after prompt-based editing and allows fine-grained control over scene arrangement, trimming, and audio mixing.

---

## User Flow

1. User completes video generation → VideoResults page
2. User completes prompt-based editing (optional)
3. User clicks "Manual Edit" button
4. Navigate to Manual Editing page
5. Timeline automatically loads with:
   - All 4 scenes as video clips
   - Background music as audio clip
6. User edits:
   - Trim scene start/end points
   - Split scenes
   - Reorder scenes
   - Adjust volume/mute
7. User clicks "Export to Campaign"
8. Backend processes edits (2-5 min):
   - Applies timeline edits
   - Renders final video
   - Uploads to S3 (replaces final_video.mp4)
   - **Deletes all draft files from S3** (scenes, music)
   - **Sets `manual_editing_done = True`**
9. Redirect to VideoResults page
10. Video automatically updates with edited version
11. **Campaign is finalized:**
    - Prompt-based editing disabled (SceneSidebar hidden)
    - Manual editing disabled (redirects if accessed)
    - Only final_video.mp4 available
    - No further editing possible

---

## Technical Approach

### Component Reuse
- Adapt existing editing components from `editing/` folder
- Remove Electron-specific code
- Adapt for web (S3 URLs, API calls)

### Key Adaptations
1. **Video Source:** Replace `clipforge://` protocol with S3 URLs/API proxy
2. **Export:** Replace Electron IPC with REST API calls
3. **State:** Use Zustand store (already web-compatible)
4. **File Handling:** Load from campaign data, not file system

### Backend Processing
- Download scenes/music from S3
- Apply edits via FFmpeg (trim, split, concatenate)
- Mix audio with video
- Upload final video to S3
- Update campaign metadata

---

## Implementation Phases

1. **Component Adaptation (8-10h):** Adapt PreviewPlayer, Timeline, EditorStore
2. **Backend API (8-10h):** Endpoints + export pipeline
3. **Frontend Integration (6-8h):** ManualEditing page + routes
4. **FFmpeg Integration (2-3h):** Video processing functions
5. **Testing (4-5h):** End-to-end testing
6. **Polish (2-3h):** Documentation + cleanup

**Total: 30-39 hours**

---

## Key Files

### New Files
- `frontend/src/pages/ManualEditing.tsx`
- `frontend/src/components/editing/PreviewPlayer.tsx` (adapted)
- `frontend/src/components/editing/Timeline.tsx` (adapted)
- `frontend/src/stores/editorStore.ts` (adapted)
- `backend/app/services/video_processor.py`

### Modified Files
- `backend/app/api/editing.py` (add 3 endpoints)
- `backend/app/jobs/edit_pipeline.py` (add export pipeline)
- `frontend/src/pages/VideoResults.tsx` (add button)
- `frontend/src/App.tsx` (add route)

---

## Success Criteria

✅ Timeline loads with all scenes  
✅ Music loads automatically  
✅ Can trim, split, reorder scenes  
✅ Preview shows edited video  
✅ Export replaces campaign video  
✅ Video updates on results page  
✅ `manual_editing_done` flag prevents all editing when set  
✅ SceneSidebar hidden when flag is true  
✅ All draft files removed from S3 after export  
✅ Only final_video.mp4 remains  
✅ Campaign is immutable once finalized  

---

## Risks & Mitigations

**Risk:** FFmpeg operations may be slow  
**Mitigation:** Use stream copy for trimming, optimize concatenation

**Risk:** S3 CORS issues  
**Mitigation:** Use API proxy endpoint for video streaming

**Risk:** Large video files  
**Mitigation:** Process in chunks, show progress indicators

---

## Next Steps

1. Review implementation plan
2. Start Phase 1: Component adaptation
3. Test adapted components in isolation
4. Integrate with backend
5. End-to-end testing

---

**Ready for implementation!** 🚀


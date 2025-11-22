# Phase 4: Manual Editing Finalization Feature

**Purpose:** Finalize campaign after manual editing export. Remove all draft files and lock campaign from further editing.

---

## Overview

Once a user completes manual editing and exports, the campaign is **permanently finalized**:
- `manual_editing_done = True` set in database
- All draft files (scenes, music) removed from S3
- Only `final_video.mp4` remains
- No further editing possible (prompt-based or manual)

---

## Database Schema

### Migration: `010_add_manual_editing_done_flag.py`

```python
def upgrade():
    op.add_column(
        'campaigns',
        sa.Column('manual_editing_done', sa.Boolean(), nullable=False, server_default='false')
    )
    op.create_index(
        'idx_campaigns_manual_editing_done',
        'campaigns',
        ['manual_editing_done']
    )
```

### Model Update

```python
class Campaign(Base):
    # ... existing fields ...
    manual_editing_done = Column(Boolean, default=False, nullable=False)
    # If True: Campaign finalized, all draft files removed, no editing possible
```

---

## Backend Implementation

### Export Pipeline: S3 Cleanup

**File:** `backend/app/jobs/edit_pipeline.py`

**After uploading final video, cleanup S3:**

```python
# STEP 8: Cleanup S3 draft files (scenes, music)
import boto3
from app.config import settings

s3_client = boto3.client('s3')

# Delete all scene videos
for i in range(len(scenes)):
    scene_s3_key = (
        f"brands/{self.campaign.brand_id}/perfumes/{self.campaign.perfume_id}/"
        f"campaigns/{self.campaign_id}/variations/variation_{self.campaign.selected_variation_index or 0}/"
        f"draft/scene_{i+1}_bg.mp4"
    )
    try:
        s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=scene_s3_key)
        logger.info(f"✅ Deleted scene {i+1} from S3: {scene_s3_key}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete scene {i+1}: {e}")

# Delete music file
music_s3_key = (
    f"brands/{self.campaign.brand_id}/perfumes/{self.campaign.perfume_id}/"
    f"campaigns/{self.campaign_id}/variations/variation_{self.campaign.selected_variation_index or 0}/"
    f"draft/music.mp3"
)
try:
    s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=music_s3_key)
    logger.info(f"✅ Deleted music from S3: {music_s3_key}")
except Exception as e:
    logger.warning(f"⚠️ Failed to delete music: {e}")

# STEP 9: Update database
update_campaign(
    self.db,
    self.campaign_id,
    campaign_json=campaign_json,
    cost=float(self.campaign.cost) + total_cost,
    status="completed",
    manual_editing_done=True  # Lock campaign - no more editing
)
```

---

## Frontend Implementation

### 1. ManualEditing Page

**Check flag on mount - redirect if done:**
```typescript
useEffect(() => {
  const loadCampaign = async () => {
    const data = await getCampaign(campaignId!)
    
    // Check if manual editing is already done
    if (data.manual_editing_done) {
      // Redirect to results page - editing not allowed
      navigate(`/campaigns/${campaignId}/results`)
      return
    }
    
    // Initialize timeline with scenes and music
    initializeTimelineFromCampaign(data)
  }
  
  loadCampaign()
}, [campaignId, navigate])
```

**Note:** User can enter/exit manual editing multiple times before exporting. Flag is only set on export.

### 2. VideoResults Page

**Hide editing options when done:**
```typescript
{/* Hide SceneSidebar if manual editing done */}
{isCampaign && !project?.manual_editing_done && (
  <div className="lg:col-span-4">
    <SceneSidebar {...props} />
  </div>
)}

{/* Show finalized message */}
{isCampaign && project?.manual_editing_done && (
  <div className="lg:col-span-4 flex items-center justify-center">
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

{/* Hide Manual Edit button if done */}
{isCampaign && !project?.manual_editing_done && (
  <Button onClick={() => navigate(`/campaigns/${id}/edit`)}>
    Manual Edit
  </Button>
)}
```

---

## S3 Structure

### Before Export
```
brands/{id}/perfumes/{id}/campaigns/{id}/variations/0/
├── draft/
│   ├── scene_1_bg.mp4  (4 scenes)
│   ├── scene_2_bg.mp4
│   ├── scene_3_bg.mp4
│   ├── scene_4_bg.mp4
│   └── music.mp3
└── final_video.mp4
```

### After Export
```
brands/{id}/perfumes/{id}/campaigns/{id}/variations/0/
└── final_video.mp4  (only this remains)
```

**All draft files deleted:**
- ✅ scene_1_bg.mp4
- ✅ scene_2_bg.mp4
- ✅ scene_3_bg.mp4
- ✅ scene_4_bg.mp4
- ✅ music.mp3

---

## User Flow

### Before Export
1. User on VideoResults page
2. SceneSidebar visible (prompt-based editing available)
3. "Manual Edit" button visible
4. User can enter/exit manual editing multiple times
5. All scene files available in S3

### After Export
1. User clicks "Export to Campaign" in manual editing
2. Backend processes:
   - Applies timeline edits
   - Renders final video
   - Uploads to S3 (replaces final_video.mp4)
   - **Deletes all draft files from S3**
   - **Sets `manual_editing_done = True`**
3. Redirect to VideoResults page
4. **Campaign finalized:**
   - SceneSidebar hidden (prompt-based editing disabled)
   - "Manual Edit" button hidden
   - Message shown: "Manual Editing Complete"
   - Only final_video.mp4 available
   - No further editing possible

### Attempting to Edit After Finalization
1. User tries to access `/campaigns/{id}/edit`
2. ManualEditing page checks flag
3. **Redirects to VideoResults** (editing not allowed)

---

## Key Points

✅ **Flag set on export:** Only when user clicks "Export to Campaign"  
✅ **S3 cleanup:** All draft files removed after export  
✅ **One-way flag:** Once set to `true`, cannot be reverted  
✅ **Immutable campaign:** No editing possible after finalization  
✅ **Storage optimization:** Reduces S3 storage costs  
✅ **Clear UX:** Users understand campaign is finalized  

---

## Testing Checklist

- [ ] Flag is set when exporting from manual editing
- [ ] All scene files deleted from S3 after export
- [ ] Music file deleted from S3 after export
- [ ] Only final_video.mp4 remains in S3
- [ ] SceneSidebar is hidden when flag is true
- [ ] "Manual Edit" button is hidden when flag is true
- [ ] Message is shown when flag is true
- [ ] Manual editing page redirects if flag is true
- [ ] Flag persists after page refresh
- [ ] S3 cleanup happens even if some files fail to delete

---

## Migration Steps

1. Create migration: `010_add_manual_editing_done_flag.py`
2. Run migration: `alembic upgrade head`
3. Verify column exists: `psql` check
4. Update export pipeline: Add S3 cleanup logic
5. Update frontend: Add flag checks
6. Test export: Verify files are deleted
7. Test UI: Verify editing is disabled

---

## Error Handling

**If S3 deletion fails:**
- Log warning but continue
- Don't fail the export
- Flag is still set (campaign finalized)
- Manual cleanup can be done later

**If export fails:**
- Flag is NOT set
- Draft files remain in S3
- User can retry export

---

**This finalization ensures campaigns are immutable once exported, reducing storage costs and preventing conflicts!** 🔒

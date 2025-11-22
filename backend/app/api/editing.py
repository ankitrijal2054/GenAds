"""API endpoints for campaign editing."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel
import logging
import boto3
from io import BytesIO
from datetime import datetime

from app.database.connection import get_db
from app.database.crud import get_campaign_by_id, update_campaign
from app.api.auth import verify_campaign_ownership
from app.jobs.worker import create_worker
from app.config import settings
from app.utils.s3_utils import get_s3_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["editing"])

# Initialize worker config
try:
    worker_config = create_worker()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Failed to initialize worker config: {e}")
    worker_config = None


# ============================================================================
# Request/Response Schemas
# ============================================================================

class EditSceneRequest(BaseModel):
    """Request to edit a scene."""
    edit_prompt: str


class EditSceneResponse(BaseModel):
    """Response when edit job is enqueued."""
    job_id: str
    estimated_cost: float
    estimated_duration_seconds: int
    message: str


class SceneInfo(BaseModel):
    """Scene information for editing UI."""
    scene_index: int
    scene_id: int
    role: str
    duration: int
    background_prompt: str
    video_url: str
    thumbnail_url: Optional[str] = None
    edit_count: int = 0
    last_edited_at: Optional[str] = None


class EditHistoryRecord(BaseModel):
    """Single edit history record."""
    edit_id: str
    timestamp: str
    scene_index: int
    edit_prompt: str
    changes_summary: Optional[str] = None
    cost: float
    duration_seconds: int


# Phase 4: Manual Editing Schemas
class MusicInfo(BaseModel):
    """Music information for manual editing."""
    audio_url: str
    duration: float


class TimelineClipState(BaseModel):
    """Timeline clip state for export."""
    id: str
    library_id: str
    name: str
    track_type: str
    duration: float
    trim_start: float
    trim_end: float
    effective_duration: float
    position: float


class TimelineState(BaseModel):
    """Timeline state for export."""
    video_clips: List[TimelineClipState]
    audio_clips: List[TimelineClipState]
    total_duration: float


class ExportEditRequest(BaseModel):
    """Request to export edited video."""
    timeline_state: TimelineState
    export_settings: Optional[Dict[str, Any]] = None


class ExportEditResponse(BaseModel):
    """Response when export job is enqueued."""
    job_id: str
    estimated_duration_seconds: int
    message: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{campaign_id}/scenes", response_model=List[SceneInfo])
async def get_campaign_scenes(
    campaign_id: UUID,
    variation_index: int = 0,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Get all scenes for a campaign (for editing UI).
    
    Returns scene data with video URLs and thumbnails.
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    scenes = campaign_json.get('scenes', [])
    
    from app.utils.s3_utils import get_scene_s3_url
    
    scene_infos = []
    for i, scene in enumerate(scenes):
        # Construct S3 URL for scene video
        video_url = get_scene_s3_url(
            brand_id=str(campaign.brand_id),
            perfume_id=str(campaign.perfume_id),
            campaign_id=str(campaign_id),
            variation_index=variation_index,
            scene_index=i
        )
        
        scene_infos.append(SceneInfo(
            scene_index=i,
            scene_id=scene.get('scene_id', i),
            role=scene.get('role', 'unknown'),
            duration=scene.get('duration', 4),
            background_prompt=scene.get('background_prompt', ''),
            video_url=video_url,
            thumbnail_url=None,  # TODO: Generate thumbnails
            edit_count=scene.get('edit_count', 0),
            last_edited_at=scene.get('last_edited_at')
        ))
    
    return scene_infos


@router.post("/{campaign_id}/scenes/{scene_index}/edit", response_model=EditSceneResponse)
async def edit_scene(
    campaign_id: UUID,
    scene_index: int,
    request: EditSceneRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Edit a specific scene in a campaign.
    
    Enqueues an edit job and returns job ID for status polling.
    """
    if not worker_config:
        raise HTTPException(
            status_code=503,
            detail="Worker not available. Redis connection required."
        )
    
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    scenes = campaign_json.get('scenes', [])
    if scene_index >= len(scenes):
        raise HTTPException(status_code=400, detail=f"Scene index {scene_index} out of range")
    
    if not request.edit_prompt.strip():
        raise HTTPException(status_code=400, detail="Edit prompt cannot be empty")
    
    # Enqueue edit job
    job = worker_config.enqueue_edit_job(
        campaign_id=str(campaign_id),
        scene_index=scene_index,
        edit_instruction=request.edit_prompt
    )
    
    return EditSceneResponse(
        job_id=job.id,
        estimated_cost=0.21,  # $0.01 LLM + $0.20 video
        estimated_duration_seconds=180,  # ~3 minutes
        message=f"Edit job enqueued for scene {scene_index}"
    )


@router.get("/{campaign_id}/edit-history", response_model=List[EditHistoryRecord])
async def get_edit_history(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Get edit history for a campaign.
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    edit_history = campaign_json.get('edit_history', {})
    edits = edit_history.get('edits', [])
    
    return [EditHistoryRecord(**edit) for edit in edits]


@router.get("/{campaign_id}/scenes/{scene_index}/stream")
async def stream_scene_video(
    campaign_id: UUID,
    scene_index: int,
    variation_index: int = Query(0, description="Variation index (0, 1, 2)"),
    request: Request = None,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Stream a scene video file for playback in the browser (with CORS support).
    
    This endpoint streams the scene video file from S3 through the backend,
    adding proper CORS headers to allow frontend video players to access it.
    
    **Path Parameters:**
    - campaign_id: UUID of the campaign
    - scene_index: Scene index (0-based)
    
    **Query Parameters:**
    - variation_index: Variation index (0, 1, 2). Defaults to 0.
    
    **Headers:**
    - Authorization: Bearer {token} (optional in development)
    - Range: Optional byte range for video seeking (e.g., "bytes=0-1023")
    
    **Response:** 
    - Content-Type: video/mp4
    - Video file as binary stream with CORS headers
    
    **Errors:**
    - 404: Campaign not found or video not available
    - 403: Not authorized
    - 401: Missing or invalid authorization
    - 400: Invalid scene index
    """
    try:
        # Get campaign and verify ownership (done via dependency)
        campaign = get_campaign_by_id(db, campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Validate scene index
        campaign_json = campaign.campaign_json
        if isinstance(campaign_json, str):
            import json
            campaign_json = json.loads(campaign_json)
        
        scenes = campaign_json.get('scenes', [])
        if scene_index < 0 or scene_index >= len(scenes):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scene index: {scene_index}. Must be between 0 and {len(scenes) - 1}"
            )
        
        # Validate variation index
        if variation_index < 0:
            raise HTTPException(status_code=400, detail="Invalid variation index")
        
        # Construct S3 key for scene video
        # Format: brands/{brand_id}/perfumes/{perfume_id}/campaigns/{campaign_id}/variation_{i}/draft/scene_{scene_index+1}_bg.mp4
        s3_key = (
            f"brands/{str(campaign.brand_id)}/perfumes/{str(campaign.perfume_id)}/campaigns/{str(campaign_id)}/"
            f"variation_{variation_index}/draft/scene_{scene_index+1}_bg.mp4"
        )
        
        logger.info(f"🎬 Streaming scene video from S3: {s3_key} (scene {scene_index}, variation {variation_index})")
        
        if not settings.s3_bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket not configured")
        
        bucket_name = settings.s3_bucket_name
        
        # Download from S3 using configured credentials
        from app.utils.s3_utils import get_s3_client
        s3_client = get_s3_client()
        
        try:
            # Get object metadata first
            head_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            content_length = head_response['ContentLength']
            content_type = head_response.get('ContentType', 'video/mp4')
            etag = head_response.get('ETag', '').strip('"')
            
            # Handle range requests for video seeking
            range_header = None
            if request:
                range_header = request.headers.get('range')
            
            if range_header:
                # Parse range header (e.g., "bytes=0-1023")
                range_match = range_header.replace('bytes=', '').split('-')
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if range_match[1] else content_length - 1
                
                # Validate range
                if start < 0 or end >= content_length or start > end:
                    raise HTTPException(status_code=416, detail="Range Not Satisfiable")
                
                # Get partial content
                response = s3_client.get_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Range=f'bytes={start}-{end}'
                )
                video_data = response['Body'].read()
                actual_length = end - start + 1
                
                return StreamingResponse(
                    iter([video_data]),
                    status_code=206,  # Partial Content
                    media_type=content_type,
                    headers={
                        'Content-Range': f'bytes {start}-{end}/{content_length}',
                        'Accept-Ranges': 'bytes',
                        'Content-Length': str(actual_length),
                        'ETag': etag,
                        'Cache-Control': 'public, max-age=31536000',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                        'Access-Control-Allow-Headers': 'Range, Content-Type, Authorization',
                    }
                )
            else:
                # Get full content
                response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                video_data = response['Body'].read()
                
                return StreamingResponse(
                    iter([video_data]),
                    media_type=content_type,
                    headers={
                        'Content-Length': str(content_length),
                        'Accept-Ranges': 'bytes',
                        'ETag': etag,
                        'Cache-Control': 'public, max-age=31536000',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                        'Access-Control-Allow-Headers': 'Range, Content-Type, Authorization',
                    }
                )
                
        except s3_client.exceptions.NoSuchKey:
            logger.error(f"❌ Scene video not found in S3: {s3_key}")
            raise HTTPException(
                status_code=404,
                detail=f"Scene video not found (scene {scene_index}, variation {variation_index})"
            )
        except Exception as e:
            logger.error(f"❌ Error streaming scene video from S3: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stream scene video: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in stream_scene_video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Phase 4: Manual Editing Endpoints
# ============================================================================

@router.get("/{campaign_id}/editing/scenes", response_model=List[SceneInfo])
async def get_editing_scenes(
    campaign_id: UUID,
    variation_index: int = Query(0, description="Variation index (0, 1, 2)"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Get all scenes for manual editing.
    
    **Returns:** List of scenes with S3 URLs
    
    **Errors:**
    - 400: If manual_editing_done is True (scenes no longer exist)
    - 404: Campaign not found
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Check if manual editing is already done - scenes no longer exist
    if campaign.manual_editing_done:
        raise HTTPException(
            status_code=400,
            detail="Manual editing already completed. Scenes no longer available."
        )
    
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    scenes = campaign_json.get('scenes', [])
    
    from app.utils.s3_utils import get_scene_s3_url
    
    scene_infos = []
    for i, scene in enumerate(scenes):
        # Construct S3 URL for scene video
        video_url = get_scene_s3_url(
            brand_id=str(campaign.brand_id),
            perfume_id=str(campaign.perfume_id),
            campaign_id=str(campaign_id),
            variation_index=variation_index,
            scene_index=i
        )
        
        scene_infos.append(SceneInfo(
            scene_index=i,
            scene_id=scene.get('scene_id', i),
            role=scene.get('role', 'unknown'),
            duration=scene.get('duration', 4),
            background_prompt=scene.get('background_prompt', ''),
            video_url=video_url,
            thumbnail_url=None,
            edit_count=scene.get('edit_count', 0),
            last_edited_at=scene.get('last_edited_at')
        ))
    
    return scene_infos


@router.get("/{campaign_id}/editing/music", response_model=MusicInfo)
async def get_editing_music(
    campaign_id: UUID,
    variation_index: int = Query(0, description="Variation index (0, 1, 2)"),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Get music/audio file for manual editing.
    
    **Returns:** Music info with S3 URL and duration
    
    **Errors:**
    - 400: If manual_editing_done is True (music no longer exists)
    - 404: Campaign not found or music not available
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Check if manual editing is already done - music no longer exists
    if campaign.manual_editing_done:
        raise HTTPException(
            status_code=400,
            detail="Manual editing already completed. Music no longer available."
        )
    
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    # Get audio URL from campaign_json
    audio_url = campaign_json.get('audio_url', '')
    if not audio_url:
        # Construct S3 URL using utility function
        from app.utils.s3_utils import get_audio_s3_url
        audio_url = get_audio_s3_url(
            brand_id=str(campaign.brand_id),
            perfume_id=str(campaign.perfume_id),
            campaign_id=str(campaign_id),
            variation_index=variation_index
        )
    
    # Get duration from campaign_json or estimate from scenes
    audio_duration = campaign_json.get('audio_duration', 0.0)
    if not audio_duration:
        # Estimate from scenes
        scenes = campaign_json.get('scenes', [])
        audio_duration = sum(scene.get('duration', 4) for scene in scenes)
    
    return MusicInfo(
        audio_url=audio_url,
        duration=float(audio_duration)
    )


@router.post("/{campaign_id}/editing/export", response_model=ExportEditResponse)
async def export_manual_edit(
    campaign_id: UUID,
    request: ExportEditRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Export manually edited video (DEPRECATED - use /export-upload instead).
    
    This endpoint is kept for backward compatibility but should not be used.
    The new client-side export uses /export-upload endpoint.
    """
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use /export-upload with file upload instead."
    )


@router.post("/{campaign_id}/editing/export-upload")
async def export_manual_edit_upload(
    campaign_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_campaign_ownership)
):
    """
    Export manually edited video by uploading the final video file.
    
    **Request:**
    - file: Video file (WebM or MP4) from client-side recording
    
    **Returns:** Success message with final video URL
    
    **Errors:**
    - 400: If manual_editing_done is True (already finalized)
    - 404: Campaign not found
    - 500: Upload or processing failed
    """
    import tempfile
    import os
    from app.utils.s3_utils import upload_final_video, get_s3_client
    from app.services.video_processor import get_video_duration
    
    campaign = get_campaign_by_id(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Check if manual editing is already done - cannot export again
    if campaign.manual_editing_done:
        raise HTTPException(
            status_code=400,
            detail="Manual editing already completed. Campaign is finalized."
        )
    
    variation_index = campaign.selected_variation_index or 0
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        try:
            # Read uploaded file
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
            
            logger.info(f"📤 Received video file: {len(content)} bytes for campaign {campaign_id}")
            
            # Upload to S3
            final_result = await upload_final_video(
                brand_id=str(campaign.brand_id),
                perfume_id=str(campaign.perfume_id),
                campaign_id=str(campaign_id),
                variation_index=variation_index,
                file_path=tmp_path
            )
            new_final_video_url = final_result['url']
            
            logger.info(f"✅ Uploaded final video to S3: {new_final_video_url}")
            
            # Cleanup S3 draft files (scenes, music)
            logger.info("Cleaning up S3 draft files...")
            await _cleanup_s3_draft_files(
                campaign=campaign,
                variation_index=variation_index
            )
            
            # Update database
            campaign_json = campaign.campaign_json
            if isinstance(campaign_json, str):
                import json
                campaign_json = json.loads(campaign_json)
            
            # Update variationPaths with new final video URL
            if 'variationPaths' not in campaign_json:
                campaign_json['variationPaths'] = {}
            if f'variation_{variation_index}' not in campaign_json['variationPaths']:
                campaign_json['variationPaths'][f'variation_{variation_index}'] = {
                    'aspectExports': {}
                }
            campaign_json['variationPaths'][f'variation_{variation_index}']['aspectExports']['9:16'] = new_final_video_url
            
            # Add edit history record
            if 'edit_history' not in campaign_json:
                campaign_json['edit_history'] = {
                    'edits': [],
                    'total_edit_cost': 0.0,
                    'edit_count': 0
                }
            
            edit_record = {
                'edit_id': str(uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'edit_type': 'manual_edit_export_upload',
                'cost': 0.0,
                'duration_seconds': 0
            }
            campaign_json['edit_history']['edits'].append(edit_record)
            campaign_json['edit_history']['edit_count'] += 1
            
            # Update campaign - SET manual_editing_done = True
            logger.info(f"🔒 Setting manual_editing_done=True for campaign {campaign_id}")
            updated_campaign = update_campaign(
                db,
                campaign_id,
                campaign_json=campaign_json,
                status="completed",
                manual_editing_done=True  # Lock campaign - no more editing
            )
            if updated_campaign:
                logger.info(f"✅ Successfully updated campaign {campaign_id}: manual_editing_done={updated_campaign.manual_editing_done}")
            else:
                logger.error(f"❌ Failed to update campaign {campaign_id} - update_campaign returned None")
            
            return {
                "success": True,
                "message": "Video exported successfully",
                "video_url": new_final_video_url,
                "campaign_id": str(campaign_id)
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")


async def _cleanup_s3_draft_files(campaign, variation_index: int):
    """Helper function to cleanup S3 draft files."""
    import asyncio
    from app.config import settings
    
    def delete_s3_object(bucket: str, key: str, client):
        try:
            client.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete S3 object {key}: {e}")
            return False
    
    loop = asyncio.get_event_loop()
    campaign_json = campaign.campaign_json
    if isinstance(campaign_json, str):
        import json
        campaign_json = json.loads(campaign_json)
    
    scenes = campaign_json.get('scenes', [])
    s3_client = get_s3_client()
    bucket_name = settings.s3_bucket_name
    
    # Delete all scene videos
    for i in range(len(scenes)):
        scene_s3_key = (
            f"brands/{str(campaign.brand_id)}/perfumes/{str(campaign.perfume_id)}/campaigns/{str(campaign.campaign_id)}/"
            f"variation_{variation_index}/draft/scene_{i+1}_bg.mp4"
        )
        try:
            success = await loop.run_in_executor(
                None,
                delete_s3_object,
                bucket_name,
                scene_s3_key,
                s3_client
            )
            if success:
                logger.info(f"✅ Deleted scene {i+1} from S3: {scene_s3_key}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to delete scene {i+1}: {e}")
    
    # Delete music file
    music_s3_key = (
        f"brands/{str(campaign.brand_id)}/perfumes/{str(campaign.perfume_id)}/campaigns/{str(campaign.campaign_id)}/"
        f"variation_{variation_index}/draft/music.mp3"
    )
    try:
        success = await loop.run_in_executor(
            None,
            delete_s3_object,
            bucket_name,
            music_s3_key,
            s3_client
        )
        if success:
            logger.info(f"✅ Deleted music from S3: {music_s3_key}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to delete music: {e}")


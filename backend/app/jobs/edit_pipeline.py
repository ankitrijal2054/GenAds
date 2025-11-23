"""Scene editing pipeline job."""

import asyncio
import logging
import time
import os
import tempfile
import aiohttp
import boto3
from uuid import UUID, uuid4
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.database.connection import init_db
from app.database import connection as db_connection
from app.database.crud import get_campaign_by_id, update_campaign
from app.services.edit_service import EditService
from app.services.video_generator import VideoGenerator
from app.services.renderer import Renderer
from app.utils.s3_utils import (
    upload_draft_video,
    upload_final_video,
    get_scene_s3_url,
    get_final_video_s3_url,
    get_audio_s3_url,
    parse_s3_url,
    download_from_s3,
    get_s3_client
)
from app.services.video_processor import (
    trim_video,
    concatenate_videos,
    mix_audio,
    get_video_duration,
    create_black_video
)
from app.config import settings

logger = logging.getLogger(__name__)


class SceneEditPipeline:
    """Pipeline for editing a single scene in a campaign."""
    
    def __init__(
        self,
        campaign_id: UUID,
        scene_index: int,
        edit_instruction: str
    ):
        """Initialize edit pipeline."""
        self.campaign_id = campaign_id
        self.scene_index = scene_index
        self.edit_instruction = edit_instruction
        self.db = None  # Will be initialized in run()
        
        logger.info(f"Initialized edit pipeline for campaign {campaign_id}, scene {scene_index}")
    
    async def run(self) -> Dict[str, Any]:
        """Execute scene edit pipeline."""
        start_time = time.time()
        total_cost = 0.0
        
        # Initialize DB session
        self.db = db_connection.SessionLocal()
        
        try:
            logger.info(f"Starting scene edit: Campaign {self.campaign_id}, Scene {self.scene_index}")
            
            # Load campaign
            self.campaign = get_campaign_by_id(self.db, self.campaign_id)
            if not self.campaign:
                raise ValueError(f"Campaign {self.campaign_id} not found")
            
            # Update status
            update_campaign(self.db, self.campaign_id, status="processing")
            
            campaign_json = self.campaign.campaign_json
            if isinstance(campaign_json, str):
                import json
                campaign_json = json.loads(campaign_json)
            
            # STEP 1: Get scene data
            scenes = campaign_json.get('scenes', [])
            if self.scene_index >= len(scenes):
                raise ValueError(f"Scene index {self.scene_index} out of range")
            
            scene = scenes[self.scene_index]
            original_prompt = scene.get('background_prompt', '')
            scene_role = scene.get('role', 'unknown')
            scene_duration = scene.get('duration', 4)
            
            style_spec = campaign_json.get('style_spec', {})
            perfume_name = campaign_json.get('perfume_name', 'Perfume')
            
            logger.info(f"Scene {self.scene_index}: role={scene_role}, duration={scene_duration}s")
            
            # STEP 2: Modify prompt via LLM
            edit_service = EditService(openai_api_key=settings.openai_api_key)
            
            result = await edit_service.modify_scene_prompt(
                original_prompt=original_prompt,
                edit_instruction=self.edit_instruction,
                style_spec=style_spec,
                scene_role=scene_role,
                perfume_name=perfume_name
            )
            
            modified_prompt = result['modified_prompt']
            changes_summary = result['changes_summary']
            total_cost += 0.01  # GPT-4o-mini cost
            
            logger.info(f"Prompt modified. Changes: {changes_summary}")
            
            # STEP 3: Regenerate scene video
            video_generator = VideoGenerator(
                api_token=settings.replicate_api_token,
                model=getattr(settings, 'video_model', 'veo-3.1')
            )
            
            new_video_url = await video_generator.generate_scene_background(
                prompt=modified_prompt,
                style_spec_dict=style_spec,
                duration=float(scene_duration)
            )
            total_cost += 0.20  # ByteDance cost
            
            logger.info(f"New scene video generated: {new_video_url}")
            
            # STEP 4: Download and upload to S3 (replace old scene)
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                tmp_path = tmp.name
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(new_video_url) as resp:
                        if resp.status != 200:
                            raise RuntimeError(f"Failed to download video: HTTP {resp.status}")
                        content = await resp.read()
                        tmp.write(content)
            
            # Upload to S3 (replaces old scene video)
            s3_result = await upload_draft_video(
                brand_id=str(self.campaign.brand_id),
                perfume_id=str(self.campaign.perfume_id),
                campaign_id=str(self.campaign_id),
                variation_index=self.campaign.selected_variation_index or 0,
                scene_index=self.scene_index + 1,  # 1-based
                file_path=tmp_path
            )
            new_scene_s3_url = s3_result['url']
            
            os.unlink(tmp_path)
            logger.info(f"Scene uploaded to S3: {new_scene_s3_url}")
            
            # STEP 5: Download ALL scenes for re-rendering
            all_scene_urls = []
            for i, s in enumerate(scenes):
                if i == self.scene_index:
                    # Use new scene
                    all_scene_urls.append(new_scene_s3_url)
                else:
                    # Use existing scene from S3
                    scene_s3_url = get_scene_s3_url(
                        brand_id=str(self.campaign.brand_id),
                        perfume_id=str(self.campaign.perfume_id),
                        campaign_id=str(self.campaign_id),
                        variation_index=self.campaign.selected_variation_index or 0,
                        scene_index=i
                    )
                    all_scene_urls.append(scene_s3_url)
            
            # Download scenes temporarily
            scene_temps = []
            for url in all_scene_urls:
                temp = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
                temp_path = temp.name
                # Download from S3 using boto3
                bucket_name, s3_key = parse_s3_url(url)
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
                s3_client.download_file(bucket_name, s3_key, temp_path)
                scene_temps.append(temp_path)
            
            # STEP 6: Re-render final video
            renderer = Renderer(
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                s3_bucket_name=settings.s3_bucket_name,
                aws_region=settings.aws_region
            )
            
            # Get audio URL - try from campaign_json first, otherwise construct S3 URL
            audio_url = campaign_json.get('audio_url', '')
            if not audio_url:
                # Construct S3 URL for audio file
                from app.utils.s3_utils import get_audio_s3_url
                audio_url = get_audio_s3_url(
                    brand_id=str(self.campaign.brand_id),
                    perfume_id=str(self.campaign.perfume_id),
                    campaign_id=str(self.campaign_id),
                    variation_index=self.campaign.selected_variation_index or 0
                )
                logger.info(f"Constructed audio S3 URL: {audio_url}")
            
            if not audio_url:
                raise ValueError("Audio URL not found in campaign_json and could not be constructed")
            
            final_video_path = await renderer.render_final_video(
                scene_video_urls=scene_temps,
                audio_url=audio_url,
                project_id=str(self.campaign_id),
                variation_index=self.campaign.selected_variation_index or 0
            )
            
            # STEP 7: Upload new final video (replaces old)
            final_result = await upload_final_video(
                brand_id=str(self.campaign.brand_id),
                perfume_id=str(self.campaign.perfume_id),
                campaign_id=str(self.campaign_id),
                variation_index=self.campaign.selected_variation_index or 0,
                file_path=final_video_path
            )
            
            # STEP 8: Update campaign database
            # Update scene prompt
            scenes[self.scene_index]['background_prompt'] = modified_prompt
            scenes[self.scene_index]['edit_count'] = scenes[self.scene_index].get('edit_count', 0) + 1
            scenes[self.scene_index]['last_edited_at'] = datetime.utcnow().isoformat() + "Z"
            
            # Update variationPaths with new final video URL
            # This ensures frontend gets the updated video URL
            variation_index = self.campaign.selected_variation_index or 0
            new_final_video_url = final_result['url']  # New presigned URL
            
            if 'variationPaths' not in campaign_json:
                campaign_json['variationPaths'] = {}
            
            if f'variation_{variation_index}' not in campaign_json['variationPaths']:
                campaign_json['variationPaths'][f'variation_{variation_index}'] = {
                    'aspectExports': {}
                }
            
            # Update the 9:16 aspect export with new URL
            campaign_json['variationPaths'][f'variation_{variation_index}']['aspectExports']['9:16'] = new_final_video_url
            
            logger.info(f"✅ Updated variationPaths with new final video URL for variation_{variation_index}")
            
            # Add to edit history
            if 'edit_history' not in campaign_json:
                campaign_json['edit_history'] = {
                    'edits': [],
                    'total_edit_cost': 0.0,
                    'edit_count': 0
                }
            
            edit_record = edit_service.create_edit_record(
                scene_index=self.scene_index,
                edit_prompt=self.edit_instruction,
                original_prompt=original_prompt,
                modified_prompt=modified_prompt,
                changes_summary=changes_summary,
                cost=total_cost,
                duration_seconds=int(time.time() - start_time)
            )
            
            campaign_json['edit_history']['edits'].append(edit_record)
            campaign_json['edit_history']['total_edit_cost'] += total_cost
            campaign_json['edit_history']['edit_count'] += 1
            
            # Update campaign
            update_campaign(
                self.db,
                self.campaign_id,
                campaign_json=campaign_json,
                cost=float(self.campaign.cost) + total_cost,
                status="completed"
            )
            
            # STEP 9: Cleanup temps
            for temp in scene_temps + [final_video_path]:
                if os.path.exists(temp):
                    try:
                        os.unlink(temp)
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {temp}: {e}")
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Scene edit complete! Time: {elapsed:.1f}s, Cost: ${total_cost:.2f}")
            
            return {
                "success": True,
                "campaign_id": str(self.campaign_id),
                "scene_index": self.scene_index,
                "cost": total_cost,
                "duration_seconds": int(elapsed),
                "changes_summary": changes_summary,
                "new_video_url": final_result['url']
            }
            
        except Exception as e:
            logger.error(f"❌ Scene edit failed: {e}", exc_info=True)
            update_campaign(self.db, self.campaign_id, status="failed", error_message=str(e))
            raise
        
        finally:
            self.db.close()


# Job entry point for RQ
def edit_scene_job(campaign_id: str, scene_index: int, edit_instruction: str) -> Dict[str, Any]:
    """
    RQ job function for scene editing.
    
    This is the entry point called by RQ worker.
    Runs in a forked child process on macOS.
    
    Args:
        campaign_id: String UUID of campaign
        scene_index: Scene index to edit (0-based)
        edit_instruction: User's edit instruction/prompt
        
    Returns:
        Dict with edit result
    """
    try:
        # Ensure environment variable is set (should be set by shell script)
        import os
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
        
        # Reinitialize database connection in child process
        from app.database.connection import init_db
        init_db()
        
        logger.info(f"Starting edit pipeline for campaign {campaign_id}, scene {scene_index}")
        pipeline = SceneEditPipeline(
            campaign_id=UUID(campaign_id),
            scene_index=scene_index,
            edit_instruction=edit_instruction
        )
        
        # Handle event loop properly for RQ
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(pipeline.run())
        return result
    except KeyboardInterrupt:
        logger.warning(f"Edit interrupted for campaign {campaign_id}, scene {scene_index}")
        raise
    except Exception as e:
        logger.error(f"RQ edit job failed for campaign {campaign_id}, scene {scene_index}: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "scene_index": scene_index,
            "error": str(e),
        }


# Phase 4: Manual Edit Export Pipeline

class ManualEditExportPipeline:
    """Pipeline for exporting manually edited video."""
    
    def __init__(
        self,
        campaign_id: UUID,
        timeline_state: Dict[str, Any],
        export_settings: Optional[Dict[str, Any]] = None
    ):
        """Initialize manual edit export pipeline."""
        self.campaign_id = campaign_id
        self.timeline_state = timeline_state
        self.export_settings = export_settings or {}
        self.db = None  # Will be initialized in run()
        
        logger.info(f"Initialized manual edit export pipeline for campaign {campaign_id}")
    
    async def run(self) -> Dict[str, Any]:
        """Execute manual edit export pipeline."""
        start_time = time.time()
        
        # Initialize DB session
        self.db = db_connection.SessionLocal()
        
        try:
            logger.info(f"Starting manual edit export for campaign {self.campaign_id}")
            
            # Load campaign
            self.campaign = get_campaign_by_id(self.db, self.campaign_id)
            if not self.campaign:
                raise ValueError(f"Campaign {self.campaign_id} not found")
            
            # Check if manual editing is already done
            if self.campaign.manual_editing_done:
                raise ValueError("Manual editing already completed. Campaign is finalized.")
            
            # Update status
            update_campaign(self.db, self.campaign_id, status="processing")
            
            campaign_json = self.campaign.campaign_json
            if isinstance(campaign_json, str):
                import json
                campaign_json = json.loads(campaign_json)
            
            variation_index = self.campaign.selected_variation_index or 0
            
            # Use temp directory for all operations
            with tempfile.TemporaryDirectory() as tmpdir:
                # STEP 1: Download scenes from S3, apply edits, and build timeline segments
                logger.info("Step 1: Downloading scenes, applying timeline edits, and building timeline...")
                timeline_segments = await self._download_and_edit_scenes(
                    campaign_json=campaign_json,
                    variation_index=variation_index,
                    tmpdir=tmpdir
                )
                
                if not timeline_segments:
                    raise ValueError("No timeline segments created")
                
                # STEP 2: Concatenate timeline segments in order
                logger.info(f"Step 2: Concatenating {len(timeline_segments)} timeline segments...")
                concat_path = os.path.join(tmpdir, "concatenated.mp4")
                await concatenate_videos(timeline_segments, concat_path)
                
                # STEP 3: Download and mix audio
                logger.info("Step 3: Downloading and mixing audio...")
                audio_url = campaign_json.get('audio_url', '')
                if not audio_url:
                    audio_url = get_audio_s3_url(
                        brand_id=str(self.campaign.brand_id),
                        perfume_id=str(self.campaign.perfume_id),
                        campaign_id=str(self.campaign_id),
                        variation_index=variation_index
                    )
                
                final_video_path = concat_path
                if audio_url:
                    # Download audio
                    audio_path = os.path.join(tmpdir, "audio.mp3")
                    bucket_name, s3_key = parse_s3_url(audio_url)
                    s3_client = get_s3_client()
                    s3_client.download_file(bucket_name, s3_key, audio_path)
                    
                    # Mix audio with video
                    mixed_path = os.path.join(tmpdir, "final_with_audio.mp4")
                    await mix_audio(concat_path, audio_path, mixed_path)
                    final_video_path = mixed_path
                
                # STEP 4: Upload final video to S3 (replaces old)
                logger.info("Step 4: Uploading final video to S3...")
                final_result = await upload_final_video(
                    brand_id=str(self.campaign.brand_id),
                    perfume_id=str(self.campaign.perfume_id),
                    campaign_id=str(self.campaign_id),
                    variation_index=variation_index,
                    file_path=final_video_path
                )
                new_final_video_url = final_result['url']
                
                # STEP 5: Cleanup S3 draft files (scenes, music)
                logger.info("Step 5: Cleaning up S3 draft files...")
                await self._cleanup_s3_draft_files(variation_index)
                
                # STEP 6: Update database
                logger.info("Step 6: Updating database...")
                
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
                    'edit_type': 'manual_edit_export',
                    'timeline_state': self.timeline_state,
                    'cost': 0.0,
                    'duration_seconds': int(time.time() - start_time)
                }
                campaign_json['edit_history']['edits'].append(edit_record)
                campaign_json['edit_history']['edit_count'] += 1
                
                # Update campaign - SET manual_editing_done = True
                logger.info(f"🔒 Setting manual_editing_done=True for campaign {self.campaign_id}")
                updated_campaign = update_campaign(
                    self.db,
                    self.campaign_id,
                    campaign_json=campaign_json,
                    status="completed",
                    manual_editing_done=True  # Lock campaign - no more editing
                )
                if updated_campaign:
                    logger.info(f"✅ Successfully updated campaign {self.campaign_id}: manual_editing_done={updated_campaign.manual_editing_done}")
                else:
                    logger.error(f"❌ Failed to update campaign {self.campaign_id} - update_campaign returned None")
                
                elapsed = time.time() - start_time
                logger.info(f"✅ Manual edit export complete! Time: {elapsed:.1f}s")
                
                return {
                    "success": True,
                    "campaign_id": str(self.campaign_id),
                    "new_video_url": new_final_video_url,
                    "duration_seconds": int(elapsed),
                    "edit_id": edit_record['edit_id']
                }
                
        except Exception as e:
            logger.error(f"❌ Manual edit export failed: {e}", exc_info=True)
            update_campaign(self.db, self.campaign_id, status="failed", error_message=str(e))
            raise
        
        finally:
            self.db.close()
    
    async def _download_and_edit_scenes(
        self,
        campaign_json: Dict[str, Any],
        variation_index: int,
        tmpdir: str
    ) -> List[str]:
        """
        Download scenes from S3, apply timeline edits (trim), and build timeline segments.
        
        Returns list of video file paths in timeline order (including gap fills).
        """
        video_clips = self.timeline_state.get('video_clips', [])
        total_duration = self.timeline_state.get('total_duration', 0)
        
        if not video_clips:
            raise ValueError("No video clips in timeline state")
        
        if total_duration <= 0:
            raise ValueError(f"Invalid total duration: {total_duration}")
        
        # Sort clips by position in timeline
        sorted_clips = sorted(video_clips, key=lambda c: c.get('position', 0))
        
        # Build timeline segments (clips + gaps)
        timeline_segments = []
        current_time = 0.0
        
        for clip in sorted_clips:
            clip_position = clip.get('position', 0)
            clip_effective_duration = clip.get('effective_duration', 0)
            clip_end = clip_position + clip_effective_duration
            
            # Fill gap before this clip (if any)
            if clip_position > current_time:
                gap_duration = clip_position - current_time
                if gap_duration > 0.1:  # Only create gap if > 0.1s
                    gap_path = os.path.join(tmpdir, f"gap_{len(timeline_segments)}.mp4")
                    await create_black_video(gap_duration, gap_path)
                    timeline_segments.append(gap_path)
                    logger.info(f"Created gap segment: {gap_duration}s")
                current_time = clip_position
            
            # Extract scene index from library_id (format: "scene-{index}")
            library_id = clip.get('library_id', '')
            if not library_id.startswith('scene-'):
                logger.warning(f"Invalid library_id format: {library_id}, skipping")
                # Create black video for missing clip
                missing_path = os.path.join(tmpdir, f"missing_{len(timeline_segments)}.mp4")
                await create_black_video(clip_effective_duration, missing_path)
                timeline_segments.append(missing_path)
                current_time = clip_end
                continue
            
            scene_index = int(library_id.replace('scene-', ''))
            
            # Get S3 URL for scene
            scene_s3_url = get_scene_s3_url(
                brand_id=str(self.campaign.brand_id),
                perfume_id=str(self.campaign.perfume_id),
                campaign_id=str(self.campaign_id),
                variation_index=variation_index,
                scene_index=scene_index
            )
            
            # Download scene from S3
            scene_path = os.path.join(tmpdir, f"scene_{scene_index}_raw.mp4")
            bucket_name, s3_key = parse_s3_url(scene_s3_url)
            s3_client = get_s3_client()
            s3_client.download_file(bucket_name, s3_key, scene_path)
            
            # Get actual video duration
            actual_duration = await get_video_duration(scene_path)
            
            # Apply trim based on clip settings
            trim_start = clip.get('trim_start', 0)
            trim_end = clip.get('trim_end', clip.get('duration', actual_duration))
            
            # Ensure trim_end doesn't exceed actual duration
            trim_end = min(trim_end, actual_duration)
            trim_duration = trim_end - trim_start
            
            # Ensure we don't exceed effective duration
            if trim_duration > clip_effective_duration:
                trim_duration = clip_effective_duration
                trim_end = trim_start + trim_duration
            
            if trim_duration <= 0:
                logger.warning(f"Invalid trim duration for scene {scene_index}, skipping")
                # Create black video for invalid clip
                missing_path = os.path.join(tmpdir, f"invalid_{len(timeline_segments)}.mp4")
                await create_black_video(clip_effective_duration, missing_path)
                timeline_segments.append(missing_path)
                current_time = clip_end
                continue
            
            # Trim the video
            trimmed_path = os.path.join(tmpdir, f"scene_{scene_index}_trimmed.mp4")
            await trim_video(scene_path, trim_start, trim_end, trimmed_path)
            
            # If trimmed duration doesn't match effective duration, pad or trim further
            trimmed_duration = await get_video_duration(trimmed_path)
            if abs(trimmed_duration - clip_effective_duration) > 0.1:
                # Duration mismatch - need to adjust
                if trimmed_duration < clip_effective_duration:
                    # Pad with black frames at the end
                    padded_path = os.path.join(tmpdir, f"scene_{scene_index}_padded.mp4")
                    pad_duration = clip_effective_duration - trimmed_duration
                    # Use FFmpeg to pad
                    from app.services.video_processor import concatenate_videos
                    gap_path = os.path.join(tmpdir, f"scene_{scene_index}_pad_gap.mp4")
                    await create_black_video(pad_duration, gap_path)
                    await concatenate_videos([trimmed_path, gap_path], padded_path)
                    timeline_segments.append(padded_path)
                    # Cleanup
                    if os.path.exists(gap_path):
                        os.unlink(gap_path)
                else:
                    # Trim further to match effective duration
                    final_path = os.path.join(tmpdir, f"scene_{scene_index}_final.mp4")
                    await trim_video(trimmed_path, 0, clip_effective_duration, final_path)
                    timeline_segments.append(final_path)
            else:
                timeline_segments.append(trimmed_path)
            
            # Clean up original
            if os.path.exists(scene_path):
                os.unlink(scene_path)
            
            current_time = clip_end
            logger.info(f"Processed scene {scene_index}: position={clip_position}s, duration={clip_effective_duration}s, trim={trim_start}s-{trim_end}s")
        
        # Fill gap at the end (if any)
        if current_time < total_duration:
            gap_duration = total_duration - current_time
            if gap_duration > 0.1:
                gap_path = os.path.join(tmpdir, f"gap_end_{len(timeline_segments)}.mp4")
                await create_black_video(gap_duration, gap_path)
                timeline_segments.append(gap_path)
                logger.info(f"Created end gap segment: {gap_duration}s")
        
        logger.info(f"✅ Built timeline with {len(timeline_segments)} segments (total: {total_duration}s)")
        return timeline_segments
    
    async def _cleanup_s3_draft_files(self, variation_index: int):
        """Delete all draft files from S3 (scenes, music)."""
        # Helper function for deleting S3 objects
        def delete_s3_object(bucket: str, key: str, client):
            try:
                client.delete_object(Bucket=bucket, Key=key)
                return True
            except Exception as e:
                logger.warning(f"Failed to delete S3 object {key}: {e}")
                return False
        
        # Run S3 operations in thread pool since boto3 is synchronous
        loop = asyncio.get_event_loop()
        
        campaign_json = self.campaign.campaign_json
        if isinstance(campaign_json, str):
            import json
            campaign_json = json.loads(campaign_json)
        
        scenes = campaign_json.get('scenes', [])
        
        s3_client = get_s3_client()
        bucket_name = settings.s3_bucket_name
        
        # Delete all scene videos
        for i in range(len(scenes)):
            scene_s3_key = (
                f"brands/{str(self.campaign.brand_id)}/perfumes/{str(self.campaign.perfume_id)}/campaigns/{str(self.campaign_id)}/"
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
            f"brands/{str(self.campaign.brand_id)}/perfumes/{str(self.campaign.perfume_id)}/campaigns/{str(self.campaign_id)}/"
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


# Job entry point for RQ
def export_manual_edit_job(campaign_id: str, timeline_state: dict, export_settings: dict) -> Dict[str, Any]:
    """
    RQ job function for manual edit export.
    
    This is the entry point called by RQ worker.
    Runs in a forked child process on macOS.
    
    Args:
        campaign_id: String UUID of campaign
        timeline_state: Timeline state dict with video/audio clips
        export_settings: Export settings dict
        
    Returns:
        Dict with export result
    """
    try:
        # Ensure environment variable is set (should be set by shell script)
        import os
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
        
        # Reinitialize database connection in child process
        from app.database.connection import init_db
        init_db()
        
        logger.info(f"Starting manual edit export pipeline for campaign {campaign_id}")
        pipeline = ManualEditExportPipeline(
            campaign_id=UUID(campaign_id),
            timeline_state=timeline_state,
            export_settings=export_settings
        )
        
        # Handle event loop properly for RQ
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(pipeline.run())
        return result
        
    except KeyboardInterrupt:
        logger.warning(f"Manual edit export interrupted for campaign {campaign_id}")
        raise
    except Exception as e:
        logger.error(f"RQ manual edit export job failed for campaign {campaign_id}: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e),
        }


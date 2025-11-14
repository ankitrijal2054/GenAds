"""API endpoints for generation control."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.database.connection import get_db, init_db
from app.database.crud import get_project_by_user, update_project_status
from app.models.schemas import GenerationProgressResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def get_current_user_id() -> UUID:
    """Get current user ID from authentication."""
    # TODO: Integrate with Supabase Auth
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Test user
    return user_id


# ============================================================================
# Generation Endpoints
# ============================================================================

@router.post("/projects/{project_id}/generate")
async def trigger_generation(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Trigger video generation for a project.
    
    **Path Parameters:**
    - project_id: UUID of the project to generate
    
    **Response:** 
    ```json
    {
        "status": "queued",
        "job_id": "...",
        "message": "Generation job enqueued"
    }
    ```
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized
    - 409: Generation already in progress
    - 500: Failed to enqueue job
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Get project and verify ownership
        project = get_project_by_user(db, project_id, user_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if already generating
        if project.status != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"Project already in state: {project.status}"
            )
        
        # TODO: Enqueue job with RQ
        # For now, just mark as queued
        update_project_status(
            db,
            project_id,
            "EXTRACTING_PRODUCT",
            progress=5
        )
        
        logger.info(f"✅ Enqueued generation for project {project_id}")
        
        return {
            "status": "queued",
            "job_id": str(project_id),  # TODO: Return actual job ID from RQ
            "message": "Generation job enqueued",
            "project_id": str(project_id)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to trigger generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger generation: {str(e)}")


@router.get("/projects/{project_id}/progress", response_model=GenerationProgressResponse)
async def get_generation_progress(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get current generation progress for a project.
    
    **Path Parameters:**
    - project_id: UUID of the project
    
    **Response:** GenerationProgressResponse with current status
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Get project and verify ownership
        project = get_project_by_user(db, project_id, user_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Map status to readable step
        step_map = {
            "PENDING": "Pending",
            "EXTRACTING_PRODUCT": "Extracting Product",
            "PLANNING": "Planning Scenes",
            "GENERATING_SCENES": "Generating Video Scenes",
            "COMPOSITING": "Compositing Product",
            "ADDING_OVERLAYS": "Adding Text Overlays",
            "GENERATING_AUDIO": "Generating Background Music",
            "RENDERING": "Rendering Final Video",
            "COMPLETED": "Completed",
            "FAILED": "Failed"
        }
        
        return GenerationProgressResponse(
            project_id=project.id,
            status=project.status,
            progress=project.progress,
            current_step=step_map.get(project.status, project.status),
            cost_so_far=float(project.cost),
            error_message=project.error_message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get progress for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")


@router.post("/projects/{project_id}/cancel")
async def cancel_generation(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Cancel an in-progress generation (if possible).
    
    **Path Parameters:**
    - project_id: UUID of the project
    
    **Response:**
    ```json
    {
        "status": "cancelled",
        "project_id": "...",
        "message": "Generation cancelled"
    }
    ```
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized
    - 409: Cannot cancel (not in progress)
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Get project and verify ownership
        project = get_project_by_user(db, project_id, user_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if generation is in progress
        if project.status == "COMPLETED":
            raise HTTPException(status_code=409, detail="Cannot cancel completed project")
        
        if project.status == "FAILED":
            raise HTTPException(status_code=409, detail="Cannot cancel failed project")
        
        if project.status == "PENDING":
            raise HTTPException(status_code=409, detail="Generation not started")
        
        # TODO: Cancel RQ job
        # For now, just mark as failed
        update_project_status(
            db,
            project_id,
            "FAILED",
            error_message="Cancelled by user"
        )
        
        logger.info(f"✅ Cancelled generation for project {project_id}")
        
        return {
            "status": "cancelled",
            "project_id": str(project_id),
            "message": "Generation cancelled"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to cancel generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel generation: {str(e)}")



"""API endpoints for project management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.database.connection import get_db, init_db
from app.database.crud import (
    create_project,
    get_project,
    get_project_by_user,
    get_user_projects,
    update_project,
    update_project_status,
    delete_project,
    get_generation_stats
)
from app.models.schemas import (
    CreateProjectRequest,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListResponse,
    ErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def get_current_user_id() -> UUID:
    """
    Get current user ID from authentication.
    TODO: Integrate with Supabase Auth
    For now, accepts X-User-ID header for testing.
    """
    # In production, this would extract from JWT token
    # For Phase 1, we'll use a header for testing
    # This will be replaced with proper Supabase Auth
    user_id = UUID("00000000-0000-0000-0000-000000000001")  # Test user
    return user_id


# ============================================================================
# CREATE Endpoints
# ============================================================================

@router.post("/", response_model=ProjectResponse)
async def create_new_project(
    request: CreateProjectRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new ad generation project.
    
    **Request Body:**
    - title: Project title
    - brief: Product brief/description
    - duration: Video duration (15-120 seconds)
    - mood: Video mood (uplifting, dramatic, energetic, calm)
    - brand_name: Brand name
    - primary_color: Primary brand color (hex)
    - secondary_color: (optional) Secondary brand color (hex)
    
    **Response:** ProjectResponse with newly created project
    
    **Errors:**
    - 400: Invalid input
    - 500: Database error
    """
    try:
        # Initialize database if needed
        init_db()
        
        # Get current user (TODO: from Auth)
        user_id = get_current_user_id()
        
        # Create brand config
        brand_config = {
            "name": request.brand_name,
            "primary_color": request.primary_color,
            "secondary_color": request.secondary_color or "",
            "font_family": "Inter"
        }
        
        # Create initial ad_project_json
        ad_project_json = {
            "version": "1.0",
            "brief": request.brief,
            "duration": request.duration,
            "mood": request.mood,
            "brand": brand_config,
            "product_asset": None,
            "style_spec": None,
            "scenes": [],
            "video_settings": {
                "aspect_ratios": ["9:16", "1:1", "16:9"],
                "resolution": "1080p",
                "fps": 30,
                "codec": "h264"
            },
            "audio_settings": {
                "include_music": True,
                "music_volume": -6.0,
                "enable_voiceover": False
            },
            "render_status": None
        }
        
        # Create project in database
        project = create_project(
            db=db,
            user_id=user_id,
            title=request.title,
            brief=request.brief,
            ad_project_json=ad_project_json,
            mood=request.mood,
            duration=request.duration
        )
        
        logger.info(f"✅ Created project {project.id} for user {user_id}")
        
        return ProjectResponse.from_orm(project)
    
    except Exception as e:
        logger.error(f"❌ Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


# ============================================================================
# READ Endpoints
# ============================================================================

@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project_details(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific project.
    
    **Path Parameters:**
    - project_id: UUID of the project
    
    **Response:** ProjectDetailResponse with full configuration
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized to view this project
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Get project and verify ownership
        project = get_project_by_user(db, project_id, user_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectDetailResponse.from_orm(project)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.get("/", response_model=ProjectListResponse)
async def list_user_projects(
    limit: int = Query(50, ge=1, le=100, description="Max projects to return"),
    offset: int = Query(0, ge=0, description="Number of projects to skip"),
    status: str = Query(None, description="Filter by status (optional)"),
    db: Session = Depends(get_db)
):
    """
    List all projects for the current user.
    
    **Query Parameters:**
    - limit: Maximum number of projects (1-100, default 50)
    - offset: Number of projects to skip (default 0)
    - status: (optional) Filter by status (e.g., "COMPLETED", "FAILED")
    
    **Response:** ProjectListResponse with list of projects
    
    **Errors:**
    - 400: Invalid query parameters
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Get projects
        projects = get_user_projects(
            db=db,
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=status
        )
        
        # Count total (for pagination info)
        total = len(projects)  # In production, use a separate count query
        
        response_projects = [ProjectResponse.from_orm(p) for p in projects]
        
        return ProjectListResponse(
            total=total,
            limit=limit,
            offset=offset,
            projects=response_projects
        )
    
    except Exception as e:
        logger.error(f"❌ Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.get("/stats/summary", response_model=dict)
async def get_user_stats(
    db: Session = Depends(get_db)
):
    """
    Get generation statistics for the current user.
    
    **Response:**
    - total_projects: Total projects created
    - completed: Completed projects
    - failed: Failed projects
    - in_progress: Currently generating
    - total_cost: Total spending in USD
    - success_rate: Success percentage
    
    **Errors:**
    - 500: Database error
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        stats = get_generation_stats(db, user_id)
        
        return stats
    
    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# ============================================================================
# UPDATE Endpoints
# ============================================================================

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project_details(
    project_id: UUID,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Update project details (title, brief, etc).
    
    **Path Parameters:**
    - project_id: UUID of the project
    
    **Request Body:**
    - Flexible: any project fields to update
    
    **Response:** Updated ProjectResponse
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Verify ownership
        project = get_project_by_user(db, project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update project
        updated = update_project(db, project_id, **request)
        
        if not updated:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return ProjectResponse.from_orm(updated)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


# ============================================================================
# DELETE Endpoints
# ============================================================================

@router.delete("/{project_id}")
async def delete_project_endpoint(
    project_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Delete a project (only if owned by current user).
    
    **Path Parameters:**
    - project_id: UUID of the project to delete
    
    **Response:** {"status": "deleted", "project_id": "..."}
    
    **Errors:**
    - 404: Project not found
    - 403: Not authorized
    """
    try:
        init_db()
        
        user_id = get_current_user_id()
        
        # Delete project
        success = delete_project(db, project_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Project not found or not authorized")
        
        return {"status": "deleted", "project_id": str(project_id)}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")




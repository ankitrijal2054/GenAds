"""Video Generator Service - Scene background video generation using Google Veo 3.1.

VEO 3.1 FEATURES:
- Reference image support (product/logo integration via reference_images array)
- Enhanced prompts with reference image usage instructions
- Natural product/text integration
- 720p/1080p resolution, 24 fps, 16:9 aspect ratio (horizontal/landscape)
- Duration options: 4, 6, or 8 seconds per scene
- MP4 format with H.264/H.265 encoding

Uses HTTP API directly for better compatibility and control.

VEO 3.1 API PARAMETERS:
- prompt: Text description with reference image usage instructions
- duration: 4, 6, or 8 seconds (mapped from scene duration)
- resolution: "720p" or "1080p"
- aspect_ratio: "16:9" (horizontal/landscape)
- fps: 24 (cinematic frame rate)
- generate_audio: False (we generate audio separately)
- reference_images: Array of image URLs (http/https) for product/logo integration
"""

import logging
import time
import os
import requests
import asyncio
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from app.config import settings
from app.services.style_manager import StyleManager

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Replicate API configuration
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Veo 3.1 API endpoint
VEO_31_API_URL = "https://api.replicate.com/v1/models/google/veo-3.1/predictions"


class VideoGenerator:
    """Generates background videos using Google Veo 3.1 with reference image support.
    
    Uses HTTP API directly (no SDK) for better compatibility and control.
    """

    def __init__(self, api_token: Optional[str] = None):
        """Initialize with Replicate API token.
        
        Args:
            api_token: Replicate API token. If None, uses REPLICATE_API_TOKEN env var.
        """
        self.api_token = api_token or REPLICATE_API_TOKEN
        if not self.api_token:
            raise ValueError(
                "Replicate API token not provided. "
                "Set REPLICATE_API_TOKEN environment variable or pass api_token parameter."
            )
        
        self.api_url = VEO_31_API_URL
        logger.info(f"🎬 VideoGenerator initialized with Veo 3.1")

    async def generate_scene_background(
        self,
        prompt: str,
        style_spec_dict: dict,
        duration: float = 5.0,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
        use_product: bool = False,
        use_logo: bool = False,
    ) -> str:
        """
        Generate background video for a scene using Veo 3.1 (horizontal 16:9).
        
        When reference images are provided, the prompt is enhanced to describe how
        they should be integrated into the scene.

        Args:
            prompt: Scene description prompt from ScenePlanner
            style_spec_dict: Style specification dict with visual guidelines
            duration: Video duration in seconds (mapped to 4, 6, or 8 seconds)
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection (one of the perfume styles)
            product_image_url: URL of product image (passed as reference image when use_product=True)
            logo_image_url: URL of logo image (passed as reference image when use_logo=True)
            use_product: Whether to use product image as reference
            use_logo: Whether to use logo image as reference

        Returns:
            URL of generated video from Replicate
        """
        logger.info(f"Generating horizontal video with Veo 3.1: {prompt[:60]}...")
        if use_product and product_image_url:
            logger.info(f"📦 Product image available for integration: {product_image_url[:80]}...")
        if use_logo and logo_image_url:
            logger.info(f"🏷️ Logo image available for integration: {logo_image_url[:80]}...")

        try:
            # Enhance prompt with style and reference image usage instructions
            enhanced_prompt = self._enhance_prompt_with_references(
                prompt=prompt,
                style_spec_dict=style_spec_dict,
                extracted_style=extracted_style,
                style_override=style_override,
                use_product=use_product,
                use_logo=use_logo,
            )

            # Create prediction via HTTP API (hardcoded 16:9 for horizontal)
            prediction_data = await self._create_prediction(
                enhanced_prompt, 
                int(duration), 
                "16:9",
                product_image_url=product_image_url if use_product else None,
                logo_image_url=logo_image_url if use_logo else None,
            )
            
            # With "Prefer: wait", the prediction should already be complete
            status = prediction_data.get("status")
            logger.info(f"Prediction status: {status}")
            
            # Check if prediction failed immediately
            if status == "failed":
                error_msg = prediction_data.get("error") or "Unknown error"
                error_detail = prediction_data.get("error") if isinstance(prediction_data.get("error"), dict) else {}
                logger.error(f"❌ Prediction failed immediately: {error_msg}")
                if error_detail:
                    logger.error(f"Error details: {error_detail}")
                raise RuntimeError(f"Prediction failed: {error_msg}")
            
            # Check if prediction is already complete (from "Prefer: wait")
            if status in ["succeeded", "completed"]:
                result = prediction_data
            elif status == "starting" or status == "processing":
                # Fallback: poll if not complete yet (shouldn't happen with "Prefer: wait" but can happen)
                prediction_id = prediction_data.get("id")
                logger.warning(f"Prediction not complete (status: {status}), polling: {prediction_id}")
                result = await self._poll_prediction(prediction_id)
                
                if not result:
                    raise RuntimeError("Prediction failed or timed out")
            else:
                # Unknown status
                error_msg = f"Unexpected prediction status: {status}"
                logger.error(f"❌ {error_msg}")
                error_detail = prediction_data.get("error") or prediction_data.get("logs") or {}
                if error_detail:
                    logger.error(f"Error details: {error_detail}")
                raise RuntimeError(error_msg)
            
            # Extract video URL
            output = result.get("output")
            if isinstance(output, list) and len(output) > 0:
                video_url = output[0]
            else:
                video_url = str(output)

            logger.info(f"Generated video: {video_url}")
            return video_url

        except Exception as e:
            logger.error(f"Error generating video: {e}")
            raise

    def _enhance_prompt_with_references(
        self,
        prompt: str,
        style_spec_dict: dict,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
        use_product: bool = False,
        use_logo: bool = False,
    ) -> str:
        """
        Enhance prompt with style specifications and reference image usage instructions.
        
        When reference images are provided (use_product or use_logo), the prompt is enhanced
        to describe how they should be integrated into the scene. This helps Veo 3.1 understand
        the intended placement, scale, and interaction of reference images.
        
        Args:
            prompt: Original scene description prompt
            style_spec_dict: Style specification dict with visual guidelines
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection
            use_product: Whether product image is being used as reference
            use_logo: Whether logo image is being used as reference
            
        Returns:
            Enhanced prompt with style and reference image usage instructions
        """
        style_parts = []

        # Add style override keywords if provided
        if style_override:
            logger.debug(f"Adding style override '{style_override}' to prompt")
            try:
                style_config = StyleManager.get_style_config(style_override)
                if style_config and "keywords" in style_config:
                    keywords = style_config["keywords"]
                    style_parts.append(f"Visual Style: {', '.join(keywords)}")
            except Exception as e:
                logger.warning(f"Failed to apply style override: {e}")

        # Add base style specifications
        if "lighting_direction" in style_spec_dict and style_spec_dict.get("lighting_direction"):
            style_parts.append(f"Lighting: {style_spec_dict['lighting_direction']}")

        if "camera_style" in style_spec_dict and style_spec_dict.get("camera_style"):
            style_parts.append(f"Camera: {style_spec_dict['camera_style']}")

        if "mood_atmosphere" in style_spec_dict and style_spec_dict.get("mood_atmosphere"):
            style_parts.append(f"Mood: {style_spec_dict['mood_atmosphere']}")

        if "grade_postprocessing" in style_spec_dict and style_spec_dict.get("grade_postprocessing"):
            style_parts.append(f"Grade: {style_spec_dict['grade_postprocessing']}")

        # Add extracted reference style if available
        if extracted_style:
            logger.debug("Applying extracted reference style to video prompt")
            
            colors = extracted_style.get("colors", [])
            if colors:
                style_parts.append(f"Color Palette: {', '.join(colors)}")
            
            if extracted_style.get("lighting"):
                style_parts.append(f"Reference Lighting: {extracted_style['lighting']}")
            
            if extracted_style.get("camera"):
                style_parts.append(f"Reference Camera: {extracted_style['camera']}")
            
            if extracted_style.get("mood"):
                style_parts.append(f"Reference Mood: {extracted_style['mood']}")

        # NOTE: Reference image usage instructions are NOT added here.
        # The master prompt from scene_planner.py already contains detailed instructions
        # about how to use reference images (hero shot, logo host, blended/interacting, etc.).
        # We trust the scene planner's prompt to guide Veo 3.1 on reference image usage.

        # Combine style parts (if any)
        style_string = ". ".join(style_parts) if style_parts else ""
        
        # Build final enhanced prompt
        # The prompt from scene_planner already contains all reference image usage instructions
        enhanced = prompt
        if style_string:
            enhanced = f"{enhanced}. {style_string}"
        enhanced = f"{enhanced}. Modern cinematic product commercial."

        logger.info(f"📝 Enhanced prompt sent to Veo 3.1: {enhanced[:200]}...")
        return enhanced


    async def _create_prediction(
        self, 
        prompt: str, 
        duration: int, 
        aspect_ratio: str = "16:9",
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
    ) -> dict:
        """
        Create a prediction via HTTP API using Veo 3.1.
        
        Args:
            prompt: Text prompt with reference image usage instructions
            duration: Video duration in seconds (mapped to 4, 6, or 8)
            aspect_ratio: Video aspect ratio (16:9 for horizontal)
            product_image_url: URL of product image (for reference image integration)
            logo_image_url: URL of logo image (for reference image integration)
            
        Returns:
            Prediction data from API
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait"  # Wait for the result instead of polling
        }
        
        # Map duration to Veo 3.1 supported values (4, 6, or 8 seconds)
        veo_duration = min(duration, 8)
        if veo_duration <= 4:
            veo_duration = 4
        elif veo_duration <= 6:
            veo_duration = 6
        else:
            veo_duration = 8
        
        payload = {
            "input": {
                "prompt": prompt,
                "duration": veo_duration,
                "resolution": "720p",  # Veo 3.1 supports 720p and 1080p
                "aspect_ratio": "16:9",  # Hardcoded horizontal
                "fps": 24,  # Cinematic frame rate
                "generate_audio": False,  # We generate audio separately via MusicGen
            }
        }
        
        # Add reference images (array of HTTP/HTTPS URLs)
        reference_images = []
        
        def validate_and_add_url(url: str, url_type: str) -> bool:
            """Validate URL format and add to reference_images if valid."""
            if not url:
                return False
            
            url_str = str(url).strip()
            
            if not url_str.startswith(('http://', 'https://')):
                logger.warning(f"⚠️ Invalid {url_type} URL format: {url_str[:100]}...")
                return False
            
            logger.info(f"📎 Adding {url_type} as reference: {url_str[:100]}...")
            reference_images.append(url_str)
            return True
        
        if product_image_url:
            validate_and_add_url(product_image_url, "product image")
        if logo_image_url:
            validate_and_add_url(logo_image_url, "logo image")
        
        if reference_images:
            payload["input"]["reference_images"] = reference_images
            logger.info(f"🎬 Veo 3.1: Using {len(reference_images)} reference image(s) with duration {veo_duration}s")
            for i, url in enumerate(reference_images):
                logger.info(f"   Reference image {i+1}: {url[:150]}...")
        else:
            logger.debug("No reference images provided")
        
        try:
            logger.info(f"🎬 Creating Veo 3.1 prediction at {self.api_url}")
            if reference_images:
                logger.info(f"📎 Sending {len(reference_images)} reference image(s)")
            logger.debug(f"Payload: {payload}")
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=180  # Increased timeout for Veo 3.1
            )
            response.raise_for_status()
            prediction_data = response.json()
            logger.info(f"✅ Prediction created: {prediction_data.get('id', 'unknown')} - Status: {prediction_data.get('status', 'unknown')}")
            return prediction_data
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error creating Veo 3.1 prediction: {e}")
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                    logger.error(f"Error response ({status_code}): {error_data}")
                    
                    if status_code == 404:
                        logger.error(f"⚠️ Model endpoint not found: {self.api_url}")
                        logger.error(f"   Check available models at: https://replicate.com/google")
                    elif status_code == 422:
                        logger.error(f"⚠️ Invalid request parameters. Verify payload structure matches Veo 3.1 API.")
                        logger.error(f"   Payload: {payload}")
                except:
                    logger.error(f"Error response (text): {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error creating Veo 3.1 prediction: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    async def _poll_prediction(self, prediction_id: str, max_wait: int = 1200) -> Optional[dict]:
        """Poll prediction until it completes.

        Args:
            prediction_id: Replicate prediction ID
            max_wait: Maximum wait time in seconds (default 1200s = 20 minutes for Veo 3.1)
        """
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        start_time = time.time()
        check_count = 0
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                logger.error(f"Prediction timeout after {max_wait}s")
                return None
            
            try:
                # Polling uses base predictions URL, not model-specific URL
                poll_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
                response = requests.get(
                    poll_url,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                prediction = response.json()
                
                status = prediction.get("status")
                check_count += 1
                
                if status == "processing":
                    logger.debug(f"  [{check_count}] Processing ({elapsed:.0f}s)")
                    await asyncio.sleep(5)
                elif status == "succeeded":
                    logger.debug(f"  Succeeded ({elapsed:.0f}s)")
                    return prediction
                elif status == "failed":
                    error_msg = prediction.get('error')
                    if isinstance(error_msg, dict):
                        error_detail = error_msg.get('detail') or error_msg.get('message') or str(error_msg)
                    else:
                        error_detail = error_msg or "Unknown error"
                    logger.error(f"❌ Prediction failed during polling: {error_detail}")
                    # Log full error details if available
                    if isinstance(error_msg, dict):
                        logger.error(f"Full error details: {error_msg}")
                    return None
                else:
                    logger.debug(f"  Status: {status}")
                    await asyncio.sleep(5)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Error polling prediction: {e}")
                raise

    async def generate_scene_batch(
        self,
        prompts: list,
        style_spec_dict: dict,
        durations: list,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
        scenes_data: Optional[List[Dict[str, Any]]] = None,
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
    ) -> list:
        """
        Generate multiple scene videos concurrently using Veo 3.1 (horizontal 16:9).

        Args:
            prompts: List of scene prompts
            style_spec_dict: Global style specification
            durations: Duration for each scene
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection
            scenes_data: Optional list of scene dictionaries with use_product/use_logo flags
            product_image_url: URL of product image (passed as reference when use_product=True)
            logo_image_url: URL of logo image (passed as reference when use_logo=True)

        Returns:
            List of video URLs
        """
        logger.info(f"Generating {len(prompts)} horizontal scene videos in parallel...")

        try:
            tasks = []
            for i in range(len(prompts)):
                # Extract use_product/use_logo from scenes_data if available
                use_product = False
                use_logo = False
                if scenes_data and i < len(scenes_data):
                    use_product = scenes_data[i].get("use_product", False)
                    use_logo = scenes_data[i].get("use_logo", False)
                
                task = self.generate_scene_background(
                    prompt=prompts[i],
                    style_spec_dict=style_spec_dict,
                    duration=durations[i],
                    extracted_style=extracted_style,
                    style_override=style_override,
                    product_image_url=product_image_url if use_product else None,
                    logo_image_url=logo_image_url if use_logo else None,
                    use_product=use_product,
                    use_logo=use_logo,
                )
                tasks.append(task)

            videos = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for errors
            errors = [v for v in videos if isinstance(v, Exception)]
            if errors:
                logger.warning(f"{len(errors)} generation(s) failed")

            successful = [v for v in videos if not isinstance(v, Exception)]
            logger.info(f"Generated {len(successful)}/{len(prompts)} videos")

            return videos

        except Exception as e:
            logger.error(f"Error in batch generation: {e}")
            raise

    async def generate_scene_videos_batch(
        self,
        scenes: List[Dict[str, Any]],
        num_variations: int,
        style_spec_dict: dict,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
    ) -> List[List[str]]:
        """
        Generate N variations of videos for scenes.
        
        For each variation, applies variation-specific style modifiers while maintaining consistency.
        
        Args:
            scenes: List of scene dictionaries with prompts and durations
            num_variations: Number of variations to generate (1-3)
            style_spec_dict: Global style specification
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection
            
        Returns:
            List of video URL lists: [[urls_v1], [urls_v2], [urls_v3]]
        """
        logger.info(f"Generating {num_variations} video variations for {len(scenes)} scenes...")
        
        variation_videos = []
        
        for var_idx in range(num_variations):
            logger.info(f"Generating variation {var_idx + 1}/{num_variations}...")
            
            # Extract prompts and durations from scenes
            prompts = [scene.get("background_prompt", "") for scene in scenes]
            durations = [float(scene.get("duration", 5.0)) for scene in scenes]
            
            # Apply variation-specific style suffix
            variation_style_override = self._add_variation_suffix(style_override, var_idx)
            
            # Generate videos for this variation
            videos = await self.generate_scene_batch(
                prompts=prompts,
                style_spec_dict=style_spec_dict,
                durations=durations,
                extracted_style=extracted_style,
                style_override=variation_style_override,
            )
            
            variation_videos.append(videos)
            logger.info(f"Variation {var_idx + 1} complete: {len(videos)} videos")
        
        logger.info(f"Generated {len(variation_videos)} video variations")
        return variation_videos

    def _add_variation_suffix(self, style_override: Optional[str], var_idx: int) -> Optional[str]:
        """
        Add variation-specific modifiers to style override.
        
        Args:
            style_override: Original style override (e.g., "cinematic")
            var_idx: Variation index (0-based)
            
        Returns:
            Enhanced style override with variation suffix
        """
        suffixes = [
            ", dramatic cinematic lighting, high contrast",
            ", minimal clean aesthetic, soft diffused lighting",
            ", warm atmospheric lighting, lifestyle narrative",
        ]
        
        suffix = suffixes[var_idx % len(suffixes)]
        
        if style_override:
            return f"{style_override}{suffix}"
        return None


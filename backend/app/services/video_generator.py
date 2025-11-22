"""Video Generator Service - Scene background video generation.

SUPPORTS MULTIPLE MODELS (November 2025):
- Google Veo 3.1 (image-to-video with reference image support) - DEFAULT
- ByteDance SeedAnce-1-Pro (text-to-video) - FALLBACK

Uses HTTP API directly for:
- Better compatibility (works with all Python versions)
- No SDK version conflicts
- Simpler error handling
- Direct control over parameters

Model Selection:
- Set VIDEO_MODEL env var to "veo-3.1" or "seedance-1-pro"
- Default: "veo-3.1"

VEO 3.1 FEATURES:
- Reference image support (product/logo integration)
- Enhanced prompts from ScenePlanner (user-first + cinematography)
- Support for style overrides
- Natural product/text integration
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

# Model URLs
VEO_31_API_URL = "https://api.replicate.com/v1/models/google/veo-3.1/predictions"
SEEDANCE_API_URL = "https://api.replicate.com/v1/models/bytedance/seedance-1-pro/predictions"


class VideoGenerator:
    """Generates background videos using Veo 3.1 or SeedAnce-1-Pro models.
    
    Supports model switching via VIDEO_MODEL config:
    - "veo-3.1" (default): Google Veo 3.1 with reference image support
    - "seedance-1-pro": ByteDance SeedAnce-1-Pro (text-to-video only)
    
    Uses HTTP API directly (no SDK) for better compatibility and control.
    """

    def __init__(self, api_token: Optional[str] = None, model: Optional[str] = None):
        """Initialize with Replicate API token and model selection.
        
        Args:
            api_token: Replicate API token. If None, uses REPLICATE_API_TOKEN env var.
            model: Model to use ("veo-3.1" or "seedance-1-pro"). If None, uses VIDEO_MODEL config.
        """
        self.api_token = api_token or REPLICATE_API_TOKEN
        if not self.api_token:
            raise ValueError(
                "Replicate API token not provided. "
                "Set REPLICATE_API_TOKEN environment variable or pass api_token parameter."
            )
        
        # Get model from config or parameter
        self.model = model or getattr(settings, 'video_model', 'seedance-1-pro')
        if self.model not in ['veo-3.1', 'seedance-1-pro']:
            logger.warning(f"Unknown model '{self.model}', defaulting to 'seedance-1-pro'")
            self.model = 'seedance-1-pro'
        
        # Set API URL based on model
        if self.model == 'veo-3.1':
            self.api_url = VEO_31_API_URL
        else:
            self.api_url = SEEDANCE_API_URL
        
        logger.info(f"🎬 VideoGenerator initialized with model: {self.model}")

    async def generate_scene_background(
        self,
        prompt: str,
        style_spec_dict: dict,
        duration: float = 5.0,
        seed: Optional[int] = None,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
        use_product: bool = False,
        use_logo: bool = False,
    ) -> str:
        """
        Generate background video for a scene via HTTP API (TikTok vertical 9:16).
        
        VEO 3.1 READY:
        This method is prepared for Veo 3.1 image-to-video model which accepts reference images.
        Currently uses ByteDance SeedAnce-1-Pro as temporary solution.
        
        When Veo 3.1 is integrated:
        - product_image_url will be passed to Veo 3.1 as reference image when use_product=True
        - logo_image_url will be passed to Veo 3.1 as reference image when use_logo=True
        - Veo 3.1 will integrate these images naturally into the generated video

        Args:
            prompt: Enhanced scene description prompt (from ScenePlanner with Veo 3.1 optimizations)
            style_spec_dict: Style specification dict with visual guidelines
            duration: Video duration in seconds (typical: 2-5 seconds)
            seed: Random seed for reproducibility (optional, not used by SeedAnce)
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection (one of the 3 perfume styles)
            product_image_url: URL of product image (for Veo 3.1 reference image integration)
            logo_image_url: URL of logo image (for Veo 3.1 reference image integration)
            use_product: Whether to use product image as reference (Veo 3.1 will integrate it)
            use_logo: Whether to use logo image as reference (Veo 3.1 will integrate it)

        Returns:
            URL of generated video from Replicate
            
        Current Implementation:
            - ByteDance SeedAnce-1-Pro (text-to-video only, reference images ignored)
            
        Future Veo 3.1 Integration:
            - Will accept product_image_url for natural product integration
            - Will accept logo_image_url for brand moments
            - Will enhance prompt based on reference images
        """
        logger.info(f"Generating TikTok vertical background video with {self.model}: {prompt[:60]}...")
        if use_product and product_image_url:
            logger.info(f"📦 Product image available for {self.model} integration: {product_image_url[:80]}...")
        if use_logo and logo_image_url:
            logger.info(f"🏷️ Logo image available for {self.model} integration: {logo_image_url[:80]}...")

        try:
            # Enhance prompt with style and reference image context
            if self.model == 'veo-3.1':
                # Veo 3.1: Pass reference images directly, minimal prompt enhancement
                enhanced_prompt = self._enhance_prompt_with_style(
                    prompt=prompt,
                    style_spec_dict=style_spec_dict,
                    extracted_style=extracted_style,
                    style_override=style_override,
                )
            else:
                # SeedAnce: Enhance prompt with product/logo descriptions (no reference image support)
                enhanced_prompt = self._enhance_prompt_for_veo31(
                    prompt=prompt,
                    style_spec_dict=style_spec_dict,
                    extracted_style=extracted_style,
                    style_override=style_override,
                    use_product=use_product,
                    use_logo=use_logo,
                    product_image_url=product_image_url,
                    logo_image_url=logo_image_url,
                )

            # Create prediction via HTTP API (hardcoded 9:16 for TikTok vertical)
            prediction_data = await self._create_prediction(
                enhanced_prompt, 
                int(duration), 
                "9:16",
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

    def _enhance_prompt_with_style(self, prompt: str, style_spec_dict: dict, extracted_style: Optional[dict] = None, style_override: Optional[str] = None) -> str:
        """Enhance prompt with global style specifications, optional reference style, and style override."""
        style_parts = []

        # If style_override provided, use style keywords
        if style_override:
            logger.info(f"Adding style override '{style_override}' to prompt")
            try:
                style_config = StyleManager.get_style_config(style_override)
                if style_config and "keywords" in style_config:
                    keywords = style_config["keywords"]
                    style_parts.append(f"Visual Style Keywords: {', '.join(keywords)}")
                    logger.debug(f"Added style keywords: {keywords}")
            except Exception as e:
                logger.warning(f"Failed to apply style override: {e}")

        # Add base style specifications
        if "lighting_direction" in style_spec_dict:
            style_parts.append(f"Lighting: {style_spec_dict['lighting_direction']}")

        if "camera_style" in style_spec_dict:
            style_parts.append(f"Camera: {style_spec_dict['camera_style']}")

        if "mood_atmosphere" in style_spec_dict:
            style_parts.append(f"Mood: {style_spec_dict['mood_atmosphere']}")

        if "grade_postprocessing" in style_spec_dict:
            style_parts.append(f"Grade: {style_spec_dict['grade_postprocessing']}")

        # Add reference style if available (overrides/enhances base style)
        if extracted_style:
            logger.debug("Applying extracted reference style to video prompt")
            
            colors = extracted_style.get("colors", [])
            if colors:
                colors_str = ", ".join(colors)
                style_parts.append(f"Colors: {colors_str}")
            
            if extracted_style.get("lighting"):
                style_parts.append(f"Reference Lighting: {extracted_style['lighting']}")
            
            if extracted_style.get("camera"):
                style_parts.append(f"Reference Camera: {extracted_style['camera']}")
            
            if extracted_style.get("mood"):
                style_parts.append(f"Reference Mood: {extracted_style['mood']}")
            
            if extracted_style.get("atmosphere"):
                style_parts.append(f"Reference Atmosphere: {extracted_style['atmosphere']}")
            
            if extracted_style.get("texture"):
                style_parts.append(f"Reference Texture: {extracted_style['texture']}")

        # Combine original prompt with style
        style_string = ". ".join(style_parts)
        enhanced = f"{prompt}. {style_string}. Modern cinematic product commercial."

        logger.info(f"📝 Enhanced script sent to video generator: {enhanced}")
        return enhanced

    def _enhance_prompt_for_veo31(
        self,
        prompt: str,
        style_spec_dict: dict,
        extracted_style: Optional[dict] = None,
        style_override: Optional[str] = None,
        use_product: bool = False,
        use_logo: bool = False,
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
    ) -> str:
        """
        Enhance prompt for Veo 3.1 with reference image context.
        
        When Veo 3.1 is fully integrated, this method will:
        1. Pass product_image_url/logo_image_url directly to Veo 3.1 API
        2. Enhance prompt to describe how product/logo should appear in the scene
        
        For now (ByteDance SeedAnce-1-Pro), we enhance the text prompt to describe product/logo presence.
        
        Args:
            prompt: Original scene prompt
            style_spec_dict: Style specification
            extracted_style: Optional extracted style
            style_override: Optional style override
            use_product: Whether product should appear in scene
            use_logo: Whether logo should appear in scene
            product_image_url: URL of product image (for Veo 3.1)
            logo_image_url: URL of logo image (for Veo 3.1)
            
        Returns:
            Enhanced prompt with product/logo context
        """
        # First apply standard style enhancements
        enhanced = self._enhance_prompt_with_style(prompt, style_spec_dict, extracted_style, style_override)
        
        # VEO 3.1 READY: Add reference image context to prompt
        # When Veo 3.1 is integrated, these will be passed as actual reference images
        reference_parts = []
        
        if use_product and product_image_url:
            # Enhance prompt to describe product presence
            # Veo 3.1 will use product_image_url as reference to integrate naturally
            reference_parts.append("The luxury perfume bottle is naturally integrated into the scene as the hero element, appearing organically within the composition with proper lighting and depth.")
            logger.debug("Added product integration context to prompt for Veo 3.1")
        
        if use_logo and logo_image_url:
            # Enhance prompt to describe logo presence
            # Veo 3.1 will use logo_image_url as reference for brand moments
            reference_parts.append("The brand logo appears subtly integrated into the scene, complementing the composition without overwhelming it.")
            logger.debug("Added logo integration context to prompt for Veo 3.1")
        
        if reference_parts:
            reference_context = " ".join(reference_parts)
            enhanced = f"{enhanced} {reference_context}"
        
        return enhanced


    async def _create_prediction(
        self, 
        prompt: str, 
        duration: int, 
        aspect_ratio: str = "9:16",
        product_image_url: Optional[str] = None,
        logo_image_url: Optional[str] = None,
    ) -> dict:
        """
        Create a prediction via HTTP API using Veo 3.1 or SeedAnce-1-Pro model.
        
        Args:
            prompt: Text prompt for video generation
            duration: Video duration in seconds
            aspect_ratio: Video aspect ratio (9:16 for TikTok vertical)
            product_image_url: URL of product image (for Veo 3.1 reference image integration)
            logo_image_url: URL of logo image (for Veo 3.1 reference image integration)
            
        Returns:
            Prediction data from API
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait"  # Wait for the result instead of polling
        }
        
        if self.model == 'veo-3.1':
            # VEO 3.1 API Format
            # Duration must be one of: 4, 6, 8
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
                    "duration": veo_duration,  # Must be 4, 6, or 8
                    "resolution": "1080p",  # Veo 3.1 supports 1080p
                    "aspect_ratio": "9:16",  # Hardcoded TikTok vertical
                    "generate_audio": False,  # We generate audio separately
                }
            }
            
            # Add reference images for Veo 3.1
            # Format: array of strings (valid HTTP/HTTPS URLs), not objects
            reference_images = []
            
            def validate_and_add_url(url: str, url_type: str) -> bool:
                """Validate URL format and add to reference_images if valid."""
                if not url:
                    return False
                
                # Ensure URL is a string
                url_str = str(url).strip()
                
                # Check if URL is valid (starts with http:// or https://)
                if not url_str.startswith(('http://', 'https://')):
                    logger.warning(f"⚠️ Invalid {url_type} URL format (must start with http:// or https://): {url_str[:100]}...")
                    return False
                
                # Log the URL being added
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
                # Log full URLs for debugging (truncate for privacy)
                for i, url in enumerate(reference_images):
                    logger.info(f"   Reference image {i+1}: {url[:150]}...")
            else:
                logger.warning("⚠️ No valid reference images to add (product/logo URLs were invalid or missing)")
        else:
            # SEEDANCE-1-PRO API Format (text-to-video only, no reference images)
            payload = {
                "input": {
                    "fps": 24,
                    "prompt": prompt,
                    "duration": min(duration, 8),  # Cap at 8s (max scene duration for optimal quality)
                    "resolution": "480p",  # 480p for faster generation, good quality
                    "aspect_ratio": "9:16",  # Hardcoded TikTok vertical
                    "camera_fixed": False
                }
            }
            
            if product_image_url or logo_image_url:
                logger.warning(
                    f"⚠️ SeedAnce-1-Pro doesn't support reference images. "
                    f"Product/logo URLs will be ignored: product={product_image_url is not None}, logo={logo_image_url is not None}"
                )
        
        try:
            logger.info(f"🎬 Creating prediction with {self.model} at {self.api_url}")
            # Log reference images if present (for debugging URI format issues)
            if 'reference_images' in payload.get('input', {}):
                logger.info(f"📎 Reference images being sent: {len(payload['input']['reference_images'])} URLs")
                for i, url in enumerate(payload['input']['reference_images']):
                    logger.info(f"   URL {i+1}: {url[:200]}...")  # Log first 200 chars
            logger.debug(f"Full payload: {payload}")
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=180  # Increased timeout for Veo 3.1 (can take longer)
            )
            response.raise_for_status()
            prediction_data = response.json()
            logger.info(f"✅ Prediction created: {prediction_data.get('id', 'unknown')} - Status: {prediction_data.get('status', 'unknown')}")
            return prediction_data
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error creating prediction with {self.model}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"Error response: {error_data}")
                except:
                    logger.error(f"Error response (text): {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error creating prediction with {self.model}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    async def _poll_prediction(self, prediction_id: str, max_wait: int = 300) -> Optional[dict]:
        """Poll prediction until it completes."""
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
        Generate multiple scene videos concurrently (TikTok vertical 9:16).
        
        VEO 3.1 READY: Supports passing product/logo images as reference images.

        Args:
            prompts: List of scene prompts
            style_spec_dict: Global style specification
            durations: Duration for each scene
            extracted_style: Optional extracted style from reference image
            style_override: Override style selection
            scenes_data: Optional list of scene dictionaries with use_product/use_logo flags
            product_image_url: URL of product image (for Veo 3.1)
            logo_image_url: URL of logo image (for Veo 3.1)

        Returns:
            List of video URLs
        """
        logger.info(f"Generating {len(prompts)} TikTok vertical scene videos in parallel...")

        try:
            # Generate all scenes concurrently (all 9:16)
            # VEO 3.1 READY: Pass product/logo images based on scene flags
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
        
        For each variation:
        - Uses different seed for Replicate model (1000 + variation_index)
        - Applies variation-specific prompt suffix
        - Maintains style consistency
        
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
        # Define variation suffixes
        suffixes = [
            ", dramatic cinematic lighting, high contrast",
            ", minimal clean aesthetic, soft diffused lighting",
            ", warm atmospheric lighting, lifestyle narrative",
        ]
        
        suffix = suffixes[var_idx % len(suffixes)]
        
        if style_override:
            return f"{style_override}{suffix}"
        else:
            # If no style override, just return the suffix (will be applied to prompt)
            return None


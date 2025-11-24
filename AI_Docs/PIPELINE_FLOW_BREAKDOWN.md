# Video Generation Pipeline Flow Breakdown

## Overview

The GenAds pipeline transforms a user's creative prompt into a luxury perfume advertisement video through 5 sequential steps, with multi-variation support for parallel processing.

---

## Pipeline Flow

### **Input: User's Creative Prompt**
```
{
  creative_prompt: "Romantic Paris evening with Eiffel Tower",
  perfume_id: UUID,
  selected_style: "gold_luxe",
  target_duration: 30,
  num_variations: 2
}
```

---

### **STEP 1 Scene Planning** (LLM-Based)

The pipeline uses GPT-5.1 to generate a structured scene plan from the user's creative prompt, following a USER-FIRST philosophy where the user's creative vision is the primary driver. If brand guidelines are available, the system first extracts color palette, tone of voice, and dos/don'ts using GPT-4, then merges these into the brand colors. The scene planner generates 3-9 scenes (based on target duration) with a mandatory structure: all scenes except the second-to-last and last directly implement the user's creative prompt (e.g., "midnight garden" becomes an actual midnight garden scene) with product appearing naturally in the story when appropriate, each lasting 4-8 seconds with complex cinematography like dolly shots, crane movements, tracking, and rack focus. The second-to-last scene is a mandatory hero shot (4-6 seconds) that must include the product at center stage with an animated text overlay if needed displaying the perfume name and brand name (using fade_in or slide animation, never static), enhanced with volumetric lighting, shallow depth of field, and slow dolly-in cinematography. The last scene is a mandatory logo outro (2-4 seconds, short and elegant) that must include only the logo animation (no product, no text overlay) with slow_zoom_out camera movement and fade transition for a smooth ending. The system also generates a global StyleSpec (lighting, camera, mood, color palette, grade) to ensure visual consistency across all scenes, validates the scene plan against perfume shot grammar rules with up to 3 retries if validation fails, and if multiple variations are requested, generates N different scene plan variations (Cinematic, Minimal, Lifestyle approaches) for parallel processing. This step typically takes 10-15 seconds to complete.

---

### **STEP 2: Video Generation** (Veo 3.1)

The pipeline generates background videos for each scene using Google Veo 3.1, processing all scenes in parallel for efficiency. For each scene, the system first enhances the base prompt from the scene planner (which already contains detailed scene descriptions and reference image integration instructions) by appending style specifications including lighting direction, camera style, mood atmosphere, and grade postprocessing in the format: `{base_prompt}. Lighting: {lighting}. Camera: {camera}. Mood: {mood}. Grade: {grade}. Modern cinematic product commercial.` The enhanced prompt is then sent to the Veo 3.1 API via Replicate along with duration (4, 6, or 8 seconds mapped from scene duration), aspect ratio (16:9 horizontal, hardcoded), resolution (1080p), and reference images (product_url and/or logo_url when `use_product` or `use_logo` flags are true). Veo 3.1 generates the video by naturally integrating the product and logo when provided as reference images, embedding text overlays directly into the scene when specified in the prompt, and returns a video URL from Replicate. When multiple variations are requested, all variations are processed in parallel using `asyncio.gather()`, with each variation generating its own complete set of scene videos simultaneously. This step typically takes 6-8 minutes to complete for all scenes, regardless of the number of variations due to parallel processing.

---

### **STEP 3: Audio Generation** (MusicGen)

The pipeline generates luxury background music for the video using MusicGen, calculating the total duration by summing all scene durations or using the target duration from the campaign. The system creates a perfume-specific music prompt with gender-aware descriptors (masculine: "deep, confident, powerful, sophisticated"; feminine: "elegant, delicate, romantic, flowing"; unisex: "sophisticated, elegant, modern, refined"), combined with "luxury ambient cinematic" style and "slow to moderate" tempo. This prompt is sent to the MusicGen model (`meta/musicgen:671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb`) via Replicate with the total video duration, which generates an MP3 file that serves as the background music for the entire video. Audio generation happens once per variation and is shared across all scenes within that variation, typically taking 30-60 seconds to complete.

---

### **STEP 4: Final Rendering** (FFmpeg)

The pipeline combines all scene videos with the background audio and renders the final video using FFmpeg. The system first downloads all scene videos in sequential order along with the audio file, then uses FFmpeg to concatenate all scenes into a single video file. The audio is mixed with the concatenated video, with the audio looping if it's shorter than the video duration (the video duration determines the final length). Finally, the system applies the 16:9 aspect ratio (1920x1080 horizontal format) using padding if needed to avoid cropping, producing the final MP4 output file. When multiple variations are requested, each variation gets its own final video rendered independently, with all variations processed in parallel for efficiency. This step typically takes 1-2 minutes to complete per variation.

---

## Prompt Editing

After the initial video generation is complete, users can edit individual scenes by providing edit instructions (e.g., "make the lighting warmer" or "add more fog to the background"). The system takes the user's edit instruction and the original scene's context, then uses the scene planner to regenerate an updated `background_prompt` that incorporates the requested changes while maintaining consistency with the original scene's role, duration, and style specifications. The updated prompt is then sent to Veo 3.1 to regenerate only that specific scene, with the new video replacing the original scene in the final composition. This allows users to refine specific scenes without regenerating the entire video, significantly reducing processing time and cost while maintaining the overall narrative flow and visual consistency of the advertisement.

---

## Multi-Variation Flow

When `num_variations > 1`, the pipeline generates N different scene plan variations during Step 2 (each with different visual approaches: Variation 0 uses cinematic + dramatic lighting, Variation 1 uses minimal + clean + macro, Variation 2 uses lifestyle + real-world), then processes all variations concurrently using `asyncio.gather()` through Steps 3-5 with each variation generating its own complete set of scene videos, audio, and final rendered output simultaneously.

---

## Output

**Final Result:**
```
{
  status: "COMPLETED",
  campaign_id: UUID,
  video_urls: [url_1, url_2, ...],  // One per variation
  num_variations: 2,
  timing_seconds: 450.5
}
```

**Video Structure:**
- Scene 1-N-2: Story scenes (user's creative prompt)
- Scene N-1: Hero shot (product + animated text)
- Scene N: Logo outro (logo animation only)
- Total duration: Matches target duration (±10% tolerance)
- Aspect ratio: 16:9 horizontal (1920x1080)
- Format: MP4 with H.264 encoding

---

## Key Principles

1. **USER-FIRST:** User's creative prompt drives story scenes (not grammar templates)
2. **MANDATORY STRUCTURE:** Hero shot (second-to-last) and logo outro (last) ensure brand consistency
3. **PROMPT ENHANCEMENT:** Each scene prompt enhanced with style specs before Veo 3.1
4. **PARALLEL PROCESSING:** Scenes and variations processed concurrently for speed
5. **NARRATIVE FLOW:** All scenes connect as one cohesive story

---




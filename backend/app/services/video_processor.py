"""Video processing service with FFmpeg helper functions.

This service provides FFmpeg operations for manual video editing:
- Trim videos
- Concatenate videos
- Mix audio with video
- Get video duration
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# FFmpeg Helper Functions
# ============================================================================

async def trim_video(
    input_path: str,
    start_time: float,
    end_time: float,
    output_path: str
) -> str:
    """
    Trim video using FFmpeg.
    
    Args:
        input_path: Path to input video file
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Path to output video file
        
    Returns:
        Output path string
        
    Raises:
        RuntimeError: If FFmpeg operation fails
    """
    duration = end_time - start_time
    
    if duration <= 0:
        raise ValueError(f"Invalid duration: {duration}. End time must be greater than start time.")
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', str(input_path),
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',  # Stream copy for speed (no re-encoding)
        '-avoid_negative_ts', 'make_zero',  # Handle timestamp issues
        str(output_path)
    ]
    
    logger.info(f"Trimming video: {input_path} (start: {start_time}s, end: {end_time}s, duration: {duration}s)")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg trim failed: {error_msg}")
            raise RuntimeError(f"FFmpeg trim failed: {error_msg}")
        
        logger.info(f"✅ Video trimmed successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error trimming video: {e}", exc_info=True)
        raise RuntimeError(f"Failed to trim video: {str(e)}")


async def concatenate_videos(
    video_paths: List[str],
    output_path: str
) -> str:
    """
    Concatenate multiple videos using FFmpeg.
    
    Args:
        video_paths: List of video file paths (in order)
        output_path: Path to output video file
        
    Returns:
        Output path string
        
    Raises:
        RuntimeError: If FFmpeg operation fails
    """
    if not video_paths:
        raise ValueError("No video paths provided for concatenation")
    
    # Create concat file for FFmpeg
    concat_file = str(Path(output_path).with_suffix('.concat.txt'))
    
    try:
        # Write concat file with absolute paths
        with open(concat_file, 'w') as f:
            for path in video_paths:
                abs_path = Path(path).absolute()
                # Escape single quotes in path for FFmpeg
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        logger.info(f"Concatenating {len(video_paths)} videos into {output_path}")
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-f', 'concat',
            '-safe', '0',  # Allow absolute paths
            '-i', concat_file,
            '-c', 'copy',  # Stream copy for speed
            str(output_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg concat failed: {error_msg}")
            raise RuntimeError(f"FFmpeg concat failed: {error_msg}")
        
        logger.info(f"✅ Videos concatenated successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error concatenating videos: {e}", exc_info=True)
        raise RuntimeError(f"Failed to concatenate videos: {str(e)}")
        
    finally:
        # Clean up concat file
        try:
            if Path(concat_file).exists():
                Path(concat_file).unlink()
        except Exception as e:
            logger.warning(f"Failed to delete concat file {concat_file}: {e}")


async def mix_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    audio_volume: float = 1.0
) -> str:
    """
    Mix audio with video using FFmpeg.
    
    Args:
        video_path: Path to input video file
        audio_path: Path to input audio file
        output_path: Path to output video file
        audio_volume: Audio volume multiplier (1.0 = normal, 0.5 = half, 2.0 = double)
        
    Returns:
        Output path string
        
    Raises:
        RuntimeError: If FFmpeg operation fails
    """
    logger.info(f"Mixing audio with video: {video_path} + {audio_path} (volume: {audio_volume}x)")
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', str(video_path),
        '-i', str(audio_path),
        '-filter_complex', f'[1:a]volume={audio_volume}[a]',
        '-map', '0:v:0',  # Map video from first input
        '-map', '[a]',  # Map processed audio
        '-c:v', 'copy',  # Copy video stream (no re-encoding)
        '-c:a', 'aac',  # Encode audio as AAC
        '-shortest',  # Finish encoding when shortest input stream ends
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg audio mix failed: {error_msg}")
            raise RuntimeError(f"FFmpeg audio mix failed: {error_msg}")
        
        logger.info(f"✅ Audio mixed successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error mixing audio: {e}", exc_info=True)
        raise RuntimeError(f"Failed to mix audio: {str(e)}")


async def get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using FFprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Duration in seconds
        
    Raises:
        RuntimeError: If FFprobe operation fails
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFprobe failed: {error_msg}")
            raise RuntimeError(f"FFprobe failed: {error_msg}")
        
        duration_str = stdout.decode().strip()
        if not duration_str:
            raise RuntimeError(f"FFprobe returned empty duration for {video_path}")
        
        duration = float(duration_str)
        logger.debug(f"Video duration: {duration}s ({video_path})")
        return duration
        
    except ValueError as e:
        logger.error(f"Failed to parse duration: {e}")
        raise RuntimeError(f"Failed to parse video duration: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting video duration: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get video duration: {str(e)}")


async def extract_audio_from_video(
    video_path: str,
    output_path: str,
    audio_codec: str = 'mp3'
) -> str:
    """
    Extract audio track from video file.
    
    Args:
        video_path: Path to input video file
        output_path: Path to output audio file
        audio_codec: Audio codec (mp3, aac, etc.)
        
    Returns:
        Output path string
        
    Raises:
        RuntimeError: If FFmpeg operation fails
    """
    logger.info(f"Extracting audio from video: {video_path}")
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', str(video_path),
        '-vn',  # No video
        '-acodec', audio_codec,
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg audio extraction failed: {error_msg}")
            raise RuntimeError(f"FFmpeg audio extraction failed: {error_msg}")
        
        logger.info(f"✅ Audio extracted successfully: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error extracting audio: {e}", exc_info=True)
        raise RuntimeError(f"Failed to extract audio: {str(e)}")


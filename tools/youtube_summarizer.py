"""
JARVIS YouTube Summarizer Module
Summarize YouTube videos using yt-dlp + Whisper

Author: Rashi AI
Built for: Akshay
"""

import os
import tempfile
import requests
from typing import Dict, Any

# Try to import yt-dlp
try:
    import yt_dlp
    YTDL_AVAILABLE = True
except ImportError:
    YTDL_AVAILABLE = False


def get_video_info(url: str) -> Dict[str, Any]:
    """
    Get YouTube video information
    
    Args:
        url: YouTube video URL
        
    Returns:
        Dict with video info
    """
    if not YTDL_AVAILABLE:
        return {'success': False, 'error': 'yt-dlp not installed'}
    
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        return {
            'success': True,
            'title': info.get('title'),
            'duration': info.get('duration'),
            'description': info.get('description', '')[:500],
            'uploader': info.get('uploader'),
            'views': info.get('view_count'),
            'url': url
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def download_audio(url: str, save_path: str = None) -> Dict[str, Any]:
    """
    Download audio from YouTube video
    
    Args:
        url: YouTube video URL
        save_path: Path to save audio file
        
    Returns:
        Dict with download status
    """
    if not YTDL_AVAILABLE:
        return {'success': False, 'error': 'yt-dlp not installed'}
    
    try:
        if save_path is None:
            save_path = tempfile.mktemp(suffix='.mp3')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': save_path.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return {
            'success': True,
            'path': save_path,
            'message': 'Audio downloaded'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def summarize_video(url: str) -> Dict[str, Any]:
    """
    Summarize a YouTube video (gets info + description)
    
    Args:
        url: YouTube video URL
        
    Returns:
        Dict with summary
    """
    if not YTDL_AVAILABLE:
        return {'success': False, 'error': 'yt-dlp not installed'}
    
    try:
        # Get video info
        info = get_video_info(url)
        
        if not info.get('success'):
            return info
        
        # Get transcript if available
        transcript = None
        try:
            # Try to get transcript via YouTube API or scrape
            pass
        except:
            pass
        
        return {
            'success': True,
            'title': info.get('title'),
            'duration': f"{info.get('duration', 0) // 60} minutes",
            'description': info.get('description', ''),
            'uploader': info.get('uploader'),
            'views': info.get('views', 0),
            'url': url,
            'note': 'For full transcription, audio download + Whisper needed'
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_transcript(url: str) -> Dict[str, Any]:
    """
    Get video transcript (basic implementation)
    
    Args:
        url: YouTube video URL
        
    Returns:
        Dict with transcript
    """
    # Note: Full implementation would use youtube-transcript-api
    return {
        'success': False,
        'error': 'Transcript API not configured. Install youtube-transcript-api for full support.',
        'url': url
    }

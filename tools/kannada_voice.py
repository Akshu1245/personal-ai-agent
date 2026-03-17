"""
JARVIS Kannada Voice Input Module
Kannada speech-to-text using Sarvam AI

Author: Rashi AI
Built for: Akshay
"""

import os
import requests
from typing import Dict, Any, Optional

# Sarvam AI API (requires API key)
SARVAM_API_KEY = os.environ.get('SARVAM_API_KEY', '')
SARVAM_API_URL = 'https://api.sarvam.ai/speech-to-text'


def transcribe_kannada(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe Kannada audio to text
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Dict with transcription
    """
    if not SARVAM_API_KEY:
        return {
            'success': False,
            'error': 'SARVAM_API_KEY not set in .env'
        }
    
    try:
        # Prepare request
        headers = {
            'api-subscription-key': SARVAM_API_KEY
        }
        
        with open(audio_path, 'rb') as f:
            files = {'file': f}
            data = {
                'language_code': 'kn-IN',  # Kannada
                'model': 'saarika:v2'
            }
            
            response = requests.post(
                SARVAM_API_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'text': result.get('text', ''),
                'language': 'Kannada'
            }
        else:
            return {
                'success': False,
                'error': f'API error: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def transcribe_multilingual(audio_path: str, language: str = 'auto') -> Dict[str, Any]:
    """
    Transcribe audio with automatic language detection
    
    Args:
        audio_path: Path to audio file
        language: Language code or 'auto'
        
    Returns:
        Dict with transcription
    """
    if not SARVAM_API_KEY:
        return {
            'success': False,
            'error': 'SARVAM_API_KEY not set'
        }
    
    try:
        headers = {'api-subscription-key': SARVAM_API_KEY}
        
        language_map = {
            'kannada': 'kn-IN',
            'english': 'en-IN',
            'hindi': 'hi-IN',
            'tamil': 'ta-IN',
            'telugu': 'te-IN',
            'malayalam': 'ml-IN',
            'auto': 'saarika:v2'
        }
        
        lang_code = language_map.get(language.lower(), 'saarika:v2')
        
        with open(audio_path, 'rb') as f:
            files = {'file': f}
            data = {
                'language_code': lang_code,
                'model': 'saarika:v2'
            }
            
            response = requests.post(
                SARVAM_API_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'text': result.get('text', ''),
                'detected_language': result.get('language_code', language)
            }
        else:
            return {
                'success': False,
                'error': f'API error: {response.status_code}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# Fallback to Google Speech Recognition for Kannada
def transcribe_kannada_google(audio_path: str) -> Dict[str, Any]:
    """
    Fallback: Transcribe using Google Speech Recognition
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Dict with transcription
    """
    try:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
        
        # Try Kannada
        try:
            text = recognizer.recognize_google(audio, language='kn-IN')
            return {
                'success': True,
                'text': text,
                'language': 'Kannada'
            }
        except:
            pass
        
        # Fallback to English
        try:
            text = recognizer.recognize_google(audio)
            return {
                'success': True,
                'text': text,
                'language': 'English (fallback)'
            }
        except:
            pass
            
        return {
            'success': False,
            'error': 'Could not recognize speech'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

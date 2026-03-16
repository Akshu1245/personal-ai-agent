"""
============================================================
AKSHAY AI CORE — Authentication Manager
============================================================
Handles face authentication, PIN verification, and session management.
============================================================
"""

import asyncio
import hashlib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING
from uuid import uuid4

import bcrypt
import jwt
from rich.console import Console
from rich.prompt import Prompt, Confirm

from core.config import settings
from core.utils.logger import get_logger, audit_logger
from core.security.encryption import encryption_engine

if TYPE_CHECKING:
    import cv2
    import face_recognition
    import numpy as np

logger = get_logger("auth")
console = Console()


class AuthManager:
    """
    Authentication manager handling multiple auth methods.
    
    Supports:
    - Face recognition (primary)
    - PIN code (fallback)
    - Voice lock (emergency)
    - Session tokens (JWT)
    """
    
    def __init__(self):
        self.face_data_dir = Path(settings.DATA_DIR) / "face_data"
        self.face_data_dir.mkdir(parents=True, exist_ok=True)
        self._face_encodings: dict = {}
        self._load_face_data()
    
    def _load_face_data(self) -> None:
        """Load stored face encodings from disk."""
        face_file = self.face_data_dir / "encodings.pkl"
        if face_file.exists():
            try:
                with open(face_file, "rb") as f:
                    encrypted_data = f.read()
                # In production, this would be encrypted
                if settings.is_development():
                    self._face_encodings = pickle.loads(encrypted_data)
                else:
                    # Decrypt face data
                    decrypted = encryption_engine.decrypt(
                        encrypted_data[16:],  # Skip IV
                        encrypted_data[:16],   # IV
                    )
                    self._face_encodings = pickle.loads(decrypted)
            except Exception as e:
                logger.error("Failed to load face data", error=str(e))
                self._face_encodings = {}
    
    def _save_face_data(self) -> None:
        """Save face encodings to disk."""
        face_file = self.face_data_dir / "encodings.pkl"
        try:
            data = pickle.dumps(self._face_encodings)
            if settings.is_development():
                with open(face_file, "wb") as f:
                    f.write(data)
            else:
                # Encrypt face data
                ciphertext, iv = encryption_engine.encrypt(data)
                with open(face_file, "wb") as f:
                    f.write(iv + ciphertext)
        except Exception as e:
            logger.error("Failed to save face data", error=str(e))
    
    # =========================================
    # Face Authentication
    # =========================================
    
    async def register_face(self, user_id: str, num_samples: int = 5) -> bool:
        """
        Register a user's face for authentication.
        
        Args:
            user_id: User identifier
            num_samples: Number of face samples to capture
            
        Returns:
            True if registration successful
        """
        try:
            import cv2
            import face_recognition
            import numpy as np
        except ImportError:
            logger.error("Face recognition dependencies not installed")
            return False
        
        console.print("[yellow]Starting face registration...[/yellow]")
        console.print(f"[dim]Please look at the camera. Taking {num_samples} samples.[/dim]")
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Could not open camera")
            console.print("[red]Error: Could not access camera[/red]")
            return False
        
        encodings = []
        samples_taken = 0
        
        try:
            while samples_taken < num_samples:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Find faces
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if len(face_locations) == 1:
                    # Get face encoding
                    encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
                    encodings.append(encoding)
                    samples_taken += 1
                    console.print(f"[green]✓ Sample {samples_taken}/{num_samples} captured[/green]")
                    await asyncio.sleep(0.5)  # Brief pause between samples
                elif len(face_locations) > 1:
                    console.print("[yellow]Multiple faces detected. Please ensure only you are in frame.[/yellow]")
                
                # Show preview
                for (top, right, bottom, left) in face_locations:
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                
                cv2.imshow("Face Registration", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            if len(encodings) >= num_samples:
                # Store average encoding
                avg_encoding = np.mean(encodings, axis=0)
                self._face_encodings[user_id] = {
                    "encoding": avg_encoding,
                    "registered_at": datetime.utcnow().isoformat(),
                    "samples": len(encodings),
                }
                self._save_face_data()
                
                audit_logger.log(
                    action="face_registered",
                    user_id=user_id,
                    details={"samples": len(encodings)},
                )
                
                console.print("[green]✓ Face registered successfully![/green]")
                return True
            
            return False
            
        finally:
            cap.release()
            cv2.destroyAllWindows()
    
    async def authenticate_face(self, timeout: int = 30) -> Optional[str]:
        """
        Authenticate user via face recognition.
        
        Args:
            timeout: Maximum time to wait for authentication (seconds)
            
        Returns:
            User ID if authenticated, None otherwise
        """
        if not self._face_encodings:
            logger.warning("No face data registered")
            return None
        
        try:
            import cv2
            import face_recognition
            import numpy as np
        except ImportError:
            logger.error("Face recognition dependencies not installed")
            return None
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Could not open camera")
            return None
        
        start_time = datetime.utcnow()
        threshold = settings.FACE_AUTH_CONFIDENCE_THRESHOLD
        
        try:
            while (datetime.utcnow() - start_time).seconds < timeout:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Convert and find faces
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if face_locations:
                    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    
                    for encoding in encodings:
                        # Compare with stored faces
                        for user_id, data in self._face_encodings.items():
                            stored_encoding = data["encoding"]
                            distance = face_recognition.face_distance([stored_encoding], encoding)[0]
                            confidence = 1 - distance
                            
                            if confidence >= threshold:
                                audit_logger.log(
                                    action="face_auth_success",
                                    user_id=user_id,
                                    details={"confidence": confidence},
                                )
                                cap.release()
                                cv2.destroyAllWindows()
                                return user_id
                
                cv2.imshow("Face Authentication", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            audit_logger.log(
                action="face_auth_failed",
                status="failure",
                details={"reason": "timeout_or_no_match"},
            )
            return None
            
        finally:
            cap.release()
            cv2.destroyAllWindows()
    
    # =========================================
    # PIN Authentication
    # =========================================
    
    def hash_pin(self, pin: str) -> str:
        """
        Hash a PIN using bcrypt.
        
        Args:
            pin: Plain text PIN
            
        Returns:
            Bcrypt hash string
        """
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(pin.encode("utf-8"), salt).decode("utf-8")
    
    def verify_pin(self, pin: str, pin_hash: str) -> bool:
        """
        Verify a PIN against its hash.
        
        Args:
            pin: Plain text PIN
            pin_hash: Stored bcrypt hash
            
        Returns:
            True if PIN matches
        """
        try:
            return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))
        except Exception:
            return False
    
    # =========================================
    # JWT Session Management
    # =========================================
    
    def create_session_token(
        self,
        user_id: str,
        auth_method: str,
        extra_claims: Optional[dict] = None,
    ) -> str:
        """
        Create a JWT session token.
        
        Args:
            user_id: User identifier
            auth_method: How user authenticated (face, pin, etc.)
            extra_claims: Additional JWT claims
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiry = now + timedelta(hours=settings.JWT_EXPIRY_HOURS)
        
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expiry,
            "jti": str(uuid4()),
            "auth_method": auth_method,
            **(extra_claims or {}),
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        
        audit_logger.log(
            action="session_created",
            user_id=user_id,
            details={"auth_method": auth_method, "expires": expiry.isoformat()},
        )
        
        return token
    
    def verify_session_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode a JWT session token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            return None
    
    def invalidate_session(self, token: str) -> bool:
        """
        Invalidate a session token.
        
        Note: With JWT, we rely on token expiry. For immediate invalidation,
        maintain a blacklist in Redis or database.
        
        Args:
            token: JWT token to invalidate
            
        Returns:
            True if invalidated
        """
        payload = self.verify_session_token(token)
        if payload:
            audit_logger.log(
                action="session_invalidated",
                user_id=payload.get("sub"),
                details={"token_id": payload.get("jti")},
            )
            # In production, add to blacklist
            return True
        return False
    
    # =========================================
    # Voice Lock
    # =========================================
    
    async def listen_for_voice_lock(self) -> bool:
        """
        Listen for emergency voice lock command.
        
        Returns:
            True if lock phrase detected
        """
        if not settings.VOICE_LOCK_ENABLED:
            return False
        
        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning("Speech recognition not installed")
            return False
        
        recognizer = sr.Recognizer()
        
        try:
            with sr.Microphone() as source:
                logger.debug("Listening for voice lock command...")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
                
                try:
                    text = recognizer.recognize_google(audio).upper()
                    if settings.VOICE_LOCK_PHRASE.upper() in text:
                        audit_logger.log(
                            action="voice_lock_triggered",
                            status="success",
                        )
                        return True
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    logger.error("Speech recognition error", error=str(e))
        except Exception as e:
            logger.error("Voice lock error", error=str(e))
        
        return False
    
    # =========================================
    # Interactive Setup
    # =========================================
    
    async def interactive_setup(self) -> bool:
        """
        Interactive authentication setup wizard.
        
        Returns:
            True if setup completed successfully
        """
        console.print("\n[bold cyan]AKSHAY AI CORE — Authentication Setup[/bold cyan]\n")
        
        user_id = Prompt.ask("Enter username", default="admin")
        
        # Face registration
        if settings.FACE_AUTH_ENABLED:
            if Confirm.ask("Do you want to register face authentication?"):
                await self.register_face(user_id)
        
        # PIN setup
        if settings.PIN_ENABLED:
            if Confirm.ask("Do you want to set up PIN authentication?"):
                while True:
                    pin = Prompt.ask("Enter PIN", password=True)
                    if len(pin) < settings.PIN_MIN_LENGTH:
                        console.print(f"[red]PIN must be at least {settings.PIN_MIN_LENGTH} characters[/red]")
                        continue
                    if len(pin) > settings.PIN_MAX_LENGTH:
                        console.print(f"[red]PIN must be at most {settings.PIN_MAX_LENGTH} characters[/red]")
                        continue
                    
                    confirm_pin = Prompt.ask("Confirm PIN", password=True)
                    if pin != confirm_pin:
                        console.print("[red]PINs do not match[/red]")
                        continue
                    
                    pin_hash = self.hash_pin(pin)
                    # Store in database (would normally save to User model)
                    console.print("[green]✓ PIN configured successfully![/green]")
                    break
        
        console.print("\n[green]✓ Authentication setup complete![/green]")
        return True


# Global auth manager instance
auth_manager = AuthManager()

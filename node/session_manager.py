"""
Session Management for Multi-Turn Conversations

This module provides stateful session handling to support multi-turn conversations.
Sessions maintain context windows, TTL, and node affinity.

Key Features:
- Automatic session expiration and cleanup
- Node affinity for consistent processing
- Context window management with token limits
- Thread-safe operations
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from threading import Lock

from node.models import Message


@dataclass
class Session:
    """
    Represents a conversation session with context management.
    
    Sessions are pinned to a specific node for context consistency
    and automatically expire after TTL.
    """
    session_id: str
    client_id: str  # Hash of client public key for privacy
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl_seconds: int = 3600  # 1 hour default
    
    # Context window
    context_window: List[Message] = field(default_factory=list)
    max_context_messages: int = 20  # Keep last N messages
    max_context_tokens: int = 4096  # Approximate token limit
    
    # Node affinity
    node_affinity: Optional[str] = None  # Pin to specific node ID
    
    # Metadata
    total_messages: int = 0
    total_tokens_processed: int = 0  # Approximate
    
    def is_expired(self) -> bool:
        """Check if session has exceeded TTL."""
        return (time.time() - self.last_accessed) > self.ttl_seconds
    
    def touch(self):
        """Update last accessed time."""
        self.last_accessed = time.time()
    
    def add_message(self, message: Message, estimated_tokens: int = 0):
        """
        Add a message to the context window.
        
        Automatically truncates oldest messages if limits exceeded.
        """
        self.context_window.append(message)
        self.total_messages += 1
        self.total_tokens_processed += estimated_tokens
        self.touch()
        
        # Truncate if needed
        self._truncate_context()
    
    def _truncate_context(self):
        """Truncate context window if it exceeds limits."""
        # Keep only last N messages
        if len(self.context_window) > self.max_context_messages:
            self.context_window = self.context_window[-self.max_context_messages:]
        
        # Estimate tokens (rough approximation: 1 token ≈ 4 chars)
        total_chars = sum(len(msg.content) for msg in self.context_window)
        estimated_tokens = total_chars // 4
        
        # If still over limit, remove oldest messages
        while estimated_tokens > self.max_context_tokens and len(self.context_window) > 1:
            removed = self.context_window.pop(0)
            total_chars -= len(removed.content)
            estimated_tokens = total_chars // 4
    
    def get_context_for_inference(self) -> List[Message]:
        """Get the current context window for passing to LLM."""
        return self.context_window.copy()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at,
            'last_accessed': self.last_accessed,
            'ttl_seconds': self.ttl_seconds,
            'context_size': len(self.context_window),
            'total_messages': self.total_messages,
            'node_affinity': self.node_affinity,
        }


class SessionManager:
    """
    Manages conversation sessions for the node.
    
    Provides thread-safe session storage, retrieval, and automatic cleanup.
    """
    
    def __init__(
        self,
        default_ttl: int = 3600,
        cleanup_interval: int = 300,  # Run cleanup every 5 minutes
        max_sessions: int = 1000  # Prevent memory exhaustion
    ):
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self.max_sessions = max_sessions
        
        self._sessions: Dict[str, Session] = {}
        self._lock = Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def create_session(
        self,
        client_id: str,
        ttl_seconds: Optional[int] = None,
        node_affinity: Optional[str] = None
    ) -> Session:
        """
        Create a new session.
        
        Args:
            client_id: Client identifier (hashed public key)
            ttl_seconds: Custom TTL, or None for default
            node_affinity: Pin to specific node ID
            
        Returns:
            New Session object
            
        Raises:
            RuntimeError: If max sessions limit reached
        """
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                # Try cleanup first
                self._cleanup_expired()
                
                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError(f"Max sessions limit ({self.max_sessions}) reached")
            
            session_id = str(uuid.uuid4())
            session = Session(
                session_id=session_id,
                client_id=client_id,
                ttl_seconds=ttl_seconds or self.default_ttl,
                node_affinity=node_affinity
            )
            
            self._sessions[session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.
        
        Returns None if session doesn't exist or has expired.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            
            if session is None:
                return None
            
            if session.is_expired():
                del self._sessions[session_id]
                return None
            
            session.touch()
            return session
    
    def get_or_create_session(
        self,
        session_id: Optional[str],
        client_id: str,
        node_affinity: Optional[str] = None
    ) -> Session:
        """
        Get existing session or create new one.
        
        Useful for handling both new and continuing conversations.
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        # Create new session
        return self.create_session(client_id, node_affinity=node_affinity)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Returns True if session was deleted, False if not found.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def list_sessions(self, client_id: Optional[str] = None) -> List[Session]:
        """
        List all active sessions, optionally filtered by client.
        """
        with self._lock:
            sessions = list(self._sessions.values())
            
            if client_id:
                sessions = [s for s in sessions if s.client_id == client_id]
            
            return sessions

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions and return the count removed.
        """
        with self._lock:
            return self._cleanup_expired()
    
    def get_stats(self) -> dict:
        """Get session statistics."""
        with self._lock:
            return {
                'total_sessions': len(self._sessions),
                'max_sessions': self.max_sessions,
                'default_ttl': self.default_ttl,
            }
    
    def _cleanup_expired(self):
        """Remove expired sessions (internal, assumes lock held)."""
        expired_ids = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        
        for sid in expired_ids:
            del self._sessions[sid]
        
        return len(expired_ids)
    
    async def start_cleanup_task(self):
        """Start background task to clean up expired sessions."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _cleanup_loop(self):
        """Background task that periodically cleans up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                with self._lock:
                    removed = self._cleanup_expired()
                    if removed > 0:
                        # Logger will be available in server context
                        pass  # logger.debug(f"Cleaned up {removed} expired sessions")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Logger will be available in server context
                pass  # logger.error(f"Error in session cleanup: {e}")


# Singleton instance (initialized in server startup)
session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global session_manager
    if session_manager is None:
        session_manager = SessionManager()
    return session_manager

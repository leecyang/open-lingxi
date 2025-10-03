import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from open_webui.socket.main import sio, SESSION_POOL, USER_POOL
from open_webui.models.users import Users
from open_webui.utils.auth import decode_token
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


@dataclass
class ConversationSession:
    """Represents an active multi-agent conversation session"""
    conv_id: str
    user_id: str
    session_ids: Set[str]
    agent_uids: List[str]
    created_at: float
    last_activity: float


class MultiAgentWebSocketManager:
    """Manages WebSocket connections for multi-agent conversations"""
    
    def __init__(self):
        # Dictionary to store active conversation sessions
        # Key: conv_id, Value: ConversationSession
        self.active_conversations: Dict[str, ConversationSession] = {}
        
        # Dictionary to map session IDs to conversation IDs
        # Key: session_id, Value: conv_id
        self.session_to_conv: Dict[str, str] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def join_conversation(self, conv_id: str, user_id: str, session_id: str, agent_uids: List[str]) -> bool:
        """
        Add a user session to a conversation
        
        Args:
            conv_id: Conversation ID
            user_id: User ID
            session_id: WebSocket session ID
            agent_uids: List of agent UIDs for this conversation
            
        Returns:
            True if successfully joined, False otherwise
        """
        async with self._lock:
            try:
                current_time = time.time()
                
                if conv_id in self.active_conversations:
                    # Add to existing conversation
                    conversation = self.active_conversations[conv_id]
                    conversation.session_ids.add(session_id)
                    conversation.last_activity = current_time
                    
                    # Update agent_uids if provided
                    if agent_uids:
                        conversation.agent_uids = agent_uids
                else:
                    # Create new conversation
                    conversation = ConversationSession(
                        conv_id=conv_id,
                        user_id=user_id,
                        session_ids={session_id},
                        agent_uids=agent_uids or [],
                        created_at=current_time,
                        last_activity=current_time
                    )
                    self.active_conversations[conv_id] = conversation
                
                # Map session to conversation
                self.session_to_conv[session_id] = conv_id
                
                # Join the WebSocket room
                await sio.enter_room(session_id, f"conv_{conv_id}")
                
                log.info(f"User {user_id} joined conversation {conv_id} with session {session_id}")
                return True
                
            except Exception as e:
                log.error(f"Error joining conversation {conv_id}: {e}")
                return False
    
    async def leave_conversation(self, session_id: str) -> bool:
        """
        Remove a user session from a conversation
        
        Args:
            session_id: WebSocket session ID
            
        Returns:
            True if successfully left, False otherwise
        """
        async with self._lock:
            try:
                if session_id not in self.session_to_conv:
                    return False
                
                conv_id = self.session_to_conv[session_id]
                
                if conv_id in self.active_conversations:
                    conversation = self.active_conversations[conv_id]
                    conversation.session_ids.discard(session_id)
                    conversation.last_activity = time.time()
                    
                    # If no more sessions, remove the conversation
                    if not conversation.session_ids:
                        del self.active_conversations[conv_id]
                        log.info(f"Conversation {conv_id} ended - no more active sessions")
                
                # Remove session mapping
                del self.session_to_conv[session_id]
                
                # Leave the WebSocket room
                await sio.leave_room(session_id, f"conv_{conv_id}")
                
                log.info(f"Session {session_id} left conversation {conv_id}")
                return True
                
            except Exception as e:
                log.error(f"Error leaving conversation for session {session_id}: {e}")
                return False
    
    async def send_agent_message(self, conv_id: str, agent_id: str, message_data: dict) -> bool:
        """
        Send a message from an agent to all participants in a conversation
        
        Args:
            conv_id: Conversation ID
            agent_id: Agent ID that sent the message
            message_data: Message data to send
            
        Returns:
            True if message was sent, False otherwise
        """
        try:
            if conv_id not in self.active_conversations:
                log.warning(f"Conversation {conv_id} not found")
                return False
            
            conversation = self.active_conversations[conv_id]
            conversation.last_activity = time.time()
            
            # Prepare the message payload
            payload = {
                "conv_id": conv_id,
                "agent_id": agent_id,
                "timestamp": int(time.time() * 1000),  # milliseconds
                "data": message_data
            }
            
            # Send to all participants in the conversation room
            await sio.emit(
                "multi-agent-message",
                payload,
                room=f"conv_{conv_id}"
            )
            
            log.debug(f"Sent message from agent {agent_id} to conversation {conv_id}")
            return True
            
        except Exception as e:
            log.error(f"Error sending agent message: {e}")
            return False
    
    async def send_system_message(self, conv_id: str, message_type: str, data: dict) -> bool:
        """
        Send a system message to all participants in a conversation
        
        Args:
            conv_id: Conversation ID
            message_type: Type of system message (e.g., 'status', 'error', 'complete')
            data: Message data
            
        Returns:
            True if message was sent, False otherwise
        """
        try:
            if conv_id not in self.active_conversations:
                log.warning(f"Conversation {conv_id} not found")
                return False
            
            conversation = self.active_conversations[conv_id]
            conversation.last_activity = time.time()
            
            # Prepare the system message payload
            payload = {
                "conv_id": conv_id,
                "type": "system",
                "message_type": message_type,
                "timestamp": int(time.time() * 1000),
                "data": data
            }
            
            # Send to all participants in the conversation room
            await sio.emit(
                "multi-agent-system",
                payload,
                room=f"conv_{conv_id}"
            )
            
            log.debug(f"Sent system message '{message_type}' to conversation {conv_id}")
            return True
            
        except Exception as e:
            log.error(f"Error sending system message: {e}")
            return False
    
    async def get_conversation_info(self, conv_id: str) -> Optional[ConversationSession]:
        """
        Get information about a conversation
        
        Args:
            conv_id: Conversation ID
            
        Returns:
            ConversationSession if found, None otherwise
        """
        return self.active_conversations.get(conv_id)
    
    async def get_active_conversations(self) -> List[ConversationSession]:
        """
        Get all active conversations
        
        Returns:
            List of active ConversationSession objects
        """
        return list(self.active_conversations.values())
    
    async def cleanup_inactive_conversations(self, timeout_seconds: int = 3600) -> int:
        """
        Clean up conversations that have been inactive for too long
        
        Args:
            timeout_seconds: Timeout in seconds (default: 1 hour)
            
        Returns:
            Number of conversations cleaned up
        """
        async with self._lock:
            current_time = time.time()
            inactive_convs = []
            
            for conv_id, conversation in self.active_conversations.items():
                if current_time - conversation.last_activity > timeout_seconds:
                    inactive_convs.append(conv_id)
            
            # Remove inactive conversations
            for conv_id in inactive_convs:
                conversation = self.active_conversations[conv_id]
                
                # Remove session mappings
                for session_id in conversation.session_ids:
                    if session_id in self.session_to_conv:
                        del self.session_to_conv[session_id]
                
                # Remove conversation
                del self.active_conversations[conv_id]
                
                log.info(f"Cleaned up inactive conversation {conv_id}")
            
            return len(inactive_convs)


# Global instance
multi_agent_manager = MultiAgentWebSocketManager()


# WebSocket event handlers for multi-agent functionality

@sio.on("multi-agent-join")
async def handle_multi_agent_join(sid, data):
    """Handle user joining a multi-agent conversation"""
    try:
        # Verify authentication
        auth = data.get("auth")
        if not auth or "token" not in auth:
            await sio.emit("multi-agent-error", {"error": "Authentication required"}, room=sid)
            return
        
        token_data = decode_token(auth["token"])
        if not token_data or "id" not in token_data:
            await sio.emit("multi-agent-error", {"error": "Invalid token"}, room=sid)
            return
        
        user_id = token_data["id"]
        conv_id = data.get("conv_id")
        agent_uids = data.get("agent_uids", [])
        
        if not conv_id:
            await sio.emit("multi-agent-error", {"error": "Conversation ID required"}, room=sid)
            return
        
        # Join the conversation
        success = await multi_agent_manager.join_conversation(conv_id, user_id, sid, agent_uids)
        
        if success:
            await sio.emit("multi-agent-joined", {
                "conv_id": conv_id,
                "agent_uids": agent_uids
            }, room=sid)
        else:
            await sio.emit("multi-agent-error", {"error": "Failed to join conversation"}, room=sid)
    
    except Exception as e:
        log.error(f"Error in multi-agent-join: {e}")
        await sio.emit("multi-agent-error", {"error": "Internal server error"}, room=sid)


@sio.on("multi-agent-leave")
async def handle_multi_agent_leave(sid, data):
    """Handle user leaving a multi-agent conversation"""
    try:
        conv_id = data.get("conv_id")
        success = await multi_agent_manager.leave_conversation(sid)
        
        if success:
            await sio.emit("multi-agent-left", {"conv_id": conv_id}, room=sid)
        else:
            await sio.emit("multi-agent-error", {"error": "Failed to leave conversation"}, room=sid)
    
    except Exception as e:
        log.error(f"Error in multi-agent-leave: {e}")
        await sio.emit("multi-agent-error", {"error": "Internal server error"}, room=sid)


# Cleanup task
async def periodic_conversation_cleanup():
    """Periodic task to clean up inactive conversations"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            cleaned_count = await multi_agent_manager.cleanup_inactive_conversations()
            if cleaned_count > 0:
                log.info(f"Cleaned up {cleaned_count} inactive conversations")
        except Exception as e:
            log.error(f"Error in conversation cleanup: {e}")


# Start the cleanup task
asyncio.create_task(periodic_conversation_cleanup())
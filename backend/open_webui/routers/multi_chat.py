import asyncio
import json
import logging
import os
import time
import uuid
from typing import List, Dict, Any, Optional
import aiohttp
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from pydantic import BaseModel
from contextlib import asynccontextmanager

from open_webui.models.agents import Agents, AgentModel
from open_webui.models.users import Users
from open_webui.utils.auth import get_verified_user
from open_webui.utils.jiutian_jwt import generate_jwt_from_apikey, validate_apikey_format
from open_webui.socket.multi_agent import multi_agent_manager
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

# Semaphore to limit concurrent requests
MAX_CONCURRENT_REQUESTS = 10
request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


class MultiChatRequest(BaseModel):
    conv_id: str
    user_id: str
    message: str
    agent_uids: List[str]
    history: Optional[List[List[str]]] = []


class MultiChatResponse(BaseModel):
    conv_id: str
    status: str = "accepted"
    message: str = "Request accepted and processing"


class JiutianStreamParser:
    """Parser for Jiutian API text/event-stream responses"""
    
    @staticmethod
    def parse_sse_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse a single SSE line"""
        line = line.strip()
        if not line or line.startswith(':'):
            return None
        
        if line.startswith('data:'):
            data_content = line[5:].strip()
            if not data_content:
                return None
            
            try:
                return json.loads(data_content)
            except json.JSONDecodeError:
                log.warning(f"Failed to parse JSON: {data_content}")
                return None
        
        return None
    
    @staticmethod
    def is_stream_complete(data: Dict[str, Any]) -> bool:
        """Check if the stream is complete"""
        return (
            data.get("finished") == "Stop" or
            data.get("delta") == "[EOS]" or
            "Usage" in data
        )


async def call_jiutian_api(
    agent: AgentModel,
    message: str,
    history: List[List[str]],
    conv_id: str
) -> None:
    """
    Call Jiutian API for a single agent and stream responses via WebSocket
    
    Args:
        agent: Agent model with configuration
        message: User message
        history: Conversation history
        conv_id: Conversation ID for WebSocket routing
    """
    async with request_semaphore:
        agent_id = agent.agent_uid
        
        try:
            # Get decrypted API key for the agent
            api_key = Agents.get_decrypted_api_key(agent.agent_uid)
            if not api_key:
                error_msg = f"API key not found or invalid for agent {agent.name}"
                log.error(error_msg)
                await multi_agent_manager.send_agent_message(
                    conv_id, agent_id, {
                        "type": "error",
                        "content": error_msg,
                        "finished": True
                    }
                )
                return
            
            # Validate API key format
            if not validate_apikey_format(api_key):
                error_msg = f"Invalid API key format for agent {agent.name}"
                log.error(error_msg)
                await multi_agent_manager.send_agent_message(
                    conv_id, agent_id, {
                        "type": "error",
                        "content": error_msg,
                        "finished": True
                    }
                )
                return
            
            # Generate JWT token
            jwt_token = generate_jwt_from_apikey(api_key, 3600)  # 1 hour expiry
            
            # Prepare request payload
            config = agent.config or {}
            payload = {
                "modelId": config.get("modelId", "jiutian-lan"),
                "prompt": message,
                "history": history,
                "stream": True,
                "params": config.get("params", {
                    "temperature": 0.8,
                    "top_p": 0.95
                })
            }
            
            # Add klAssistId if configured
            if config.get("klAssistId"):
                payload["klAssistId"] = config["klAssistId"]
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token}"
            }
            
            # Build API URL
            api_url = f"{agent.api_host.rstrip('/')}/largemodel/api/v1/completions"
            
            # Send initial status
            await multi_agent_manager.send_agent_message(
                conv_id, agent_id, {
                    "type": "status",
                    "content": f"Agent {agent.name} is thinking...",
                    "agent_name": agent.name
                }
            )
            
            timeout = aiohttp.ClientTimeout(total=config.get("timeout", 30))
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_msg = f"API request failed with status {response.status}"
                        log.error(f"Agent {agent_id}: {error_msg}")
                        await multi_agent_manager.send_agent_message(
                            conv_id, agent_id, {
                                "type": "error",
                                "content": error_msg,
                                "finished": True
                            }
                        )
                        return
                    
                    # Process streaming response
                    accumulated_response = ""
                    parser = JiutianStreamParser()
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if not line_str:
                            continue
                        
                        # Parse SSE data
                        data = parser.parse_sse_line(line_str)
                        if not data:
                            continue
                        
                        # Handle different types of data
                        if "response" in data:
                            current_response = data["response"]
                            delta = data.get("delta", "")
                            
                            # Send delta if available
                            if delta and delta != "[EOS]":
                                await multi_agent_manager.send_agent_message(
                                    conv_id, agent_id, {
                                        "type": "delta",
                                        "content": delta,
                                        "agent_name": agent.name,
                                        "accumulated": current_response
                                    }
                                )
                            
                            accumulated_response = current_response
                        
                        # Check if stream is complete
                        if parser.is_stream_complete(data):
                            # Send final response
                            final_data = {
                                "type": "complete",
                                "content": accumulated_response,
                                "agent_name": agent.name,
                                "finished": True
                            }
                            
                            # Include usage information if available
                            if "Usage" in data:
                                final_data["usage"] = data["Usage"]
                            
                            # Include reference documents if available
                            if "relevant" in data:
                                final_data["references"] = data["relevant"]
                            
                            await multi_agent_manager.send_agent_message(
                                conv_id, agent_id, final_data
                            )
                            break
        
        except asyncio.TimeoutError:
            error_msg = f"Request timeout for agent {agent.name}"
            log.error(error_msg)
            await multi_agent_manager.send_agent_message(
                conv_id, agent_id, {
                    "type": "error",
                    "content": error_msg,
                    "finished": True
                }
            )
        
        except Exception as e:
            error_msg = f"Error calling API for agent {agent.name}: {str(e)}"
            log.error(error_msg)
            await multi_agent_manager.send_agent_message(
                conv_id, agent_id, {
                    "type": "error",
                    "content": error_msg,
                    "finished": True
                }
            )


async def process_multi_chat_request(
    conv_id: str,
    user_id: str,
    message: str,
    agent_uids: List[str],
    history: List[List[str]]
) -> None:
    """
    Process multi-chat request by calling multiple agents concurrently
    
    Args:
        conv_id: Conversation ID
        user_id: User ID
        message: User message
        agent_uids: List of agent UIDs to call
        history: Conversation history
    """
    try:
        # Get enabled agents
        agents = Agents.get_enabled_agents_by_uids(agent_uids)
        
        if not agents:
            await multi_agent_manager.send_system_message(
                conv_id, "error", {
                    "message": "No enabled agents found for the provided UIDs"
                }
            )
            return
        
        # Send system message about starting the conversation
        await multi_agent_manager.send_system_message(
            conv_id, "start", {
                "message": f"Starting conversation with {len(agents)} agents",
                "agent_count": len(agents),
                "agent_names": [agent.name for agent in agents]
            }
        )
        
        # Create tasks for concurrent API calls
        tasks = []
        for agent in agents:
            task = asyncio.create_task(
                call_jiutian_api(agent, message, history, conv_id)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Send completion message
        await multi_agent_manager.send_system_message(
            conv_id, "complete", {
                "message": "All agents have completed their responses",
                "agent_count": len(agents)
            }
        )
    
    except Exception as e:
        log.error(f"Error processing multi-chat request: {e}")
        await multi_agent_manager.send_system_message(
            conv_id, "error", {
                "message": f"Error processing request: {str(e)}"
            }
        )


@router.post("/multi-chat", response_model=MultiChatResponse)
async def multi_chat(
    request: MultiChatRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_verified_user)
):
    """
    Multi-agent chat endpoint
    
    Accepts a chat request and fans out to multiple agents concurrently.
    Returns immediately with 202 status and processes agents in background.
    Results are streamed via WebSocket.
    """
    try:
        # Validate request
        if not request.agent_uids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one agent UID is required"
            )
        
        if not request.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )
        
        # Verify user has access to the agents (students can use any enabled agent)
        if user.role not in ["student", "teacher", "admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
        
        # Generate conversation ID if not provided
        conv_id = request.conv_id or str(uuid.uuid4())
        
        # Add background task to process the request
        background_tasks.add_task(
            process_multi_chat_request,
            conv_id,
            request.user_id,
            request.message,
            request.agent_uids,
            request.history or []
        )
        
        return MultiChatResponse(
            conv_id=conv_id,
            status="accepted",
            message=f"Request accepted. Processing {len(request.agent_uids)} agents."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error in multi-chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT()
        )


@router.get("/conversations/{conv_id}/status")
async def get_conversation_status(
    conv_id: str,
    user=Depends(get_verified_user)
):
    """
    Get the status of a conversation
    
    Args:
        conv_id: Conversation ID
        user: Authenticated user
    
    Returns:
        Conversation status information
    """
    try:
        conversation = await multi_agent_manager.get_conversation_info(conv_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Check if user has access to this conversation
        if user.role not in ["admin", "superadmin"] and conversation.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )
        
        return {
            "conv_id": conversation.conv_id,
            "user_id": conversation.user_id,
            "agent_uids": conversation.agent_uids,
            "active_sessions": len(conversation.session_ids),
            "created_at": conversation.created_at,
            "last_activity": conversation.last_activity
        }
    
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting conversation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT()
        )


@router.get("/conversations/active")
async def get_active_conversations(
    user=Depends(get_verified_user)
):
    """
    Get all active conversations (admin only)
    
    Args:
        user: Authenticated user (must be admin)
    
    Returns:
        List of active conversations
    """
    if user.role not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )
    
    try:
        conversations = await multi_agent_manager.get_active_conversations()
        
        return {
            "conversations": [
                {
                    "conv_id": conv.conv_id,
                    "user_id": conv.user_id,
                    "agent_uids": conv.agent_uids,
                    "active_sessions": len(conv.session_ids),
                    "created_at": conv.created_at,
                    "last_activity": conv.last_activity
                }
                for conv in conversations
            ],
            "total": len(conversations)
        }
    
    except Exception as e:
        log.error(f"Error getting active conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT()
        )
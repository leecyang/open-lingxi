import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from open_webui.models.agents import (
    AgentForm,
    AgentModel,
    AgentResponse,
    AgentUpdateForm,
    AgentToggleForm,
    Agents,
)
from open_webui.models.users import Users
from open_webui.constants import ERROR_MESSAGES
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


def get_teacher_user(user=Depends(get_verified_user)):
    """Dependency to ensure user has teacher or admin role"""
    if user.role not in ["teacher", "admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


def get_superadmin_user(user=Depends(get_verified_user)):
    """Dependency to ensure user has superadmin role"""
    if user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


############################
# GetAgents
############################


@router.get("/", response_model=List[AgentResponse])
async def get_agents(user=Depends(get_verified_user)):
    """
    Get agents based on user role:
    - superadmin: all agents
    - teacher: only their own agents
    - student: no access (will be handled by chat endpoint)
    """
    if user.role == "superadmin":
        return Agents.get_all_agents()
    elif user.role == "teacher":
        return Agents.get_agents_by_user_id(user.id)
    else:
        # Students can't access agent management
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


############################
# CreateAgent
############################


@router.post("/", response_model=AgentResponse)
async def create_agent(
    form_data: AgentForm,
    user=Depends(get_teacher_user),
):
    """
    Create a new agent.
    Only teachers and admins can create agents.
    """
    try:
        agent = Agents.insert_new_agent(form_data, user.id)
        if agent:
            # Get the full response with owner info
            agents = Agents.get_agents_by_user_id(user.id)
            created_agent = next((a for a in agents if a.id == agent.id), None)
            if created_agent:
                return created_agent
            else:
                return AgentResponse(**agent.model_dump())
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(),
            )
    except Exception as e:
        log.error(f"Error creating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


############################
# GetAgentById
############################


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent_by_id(agent_id: str, user=Depends(get_verified_user)):
    """
    Get agent by ID.
    Users can only access agents they own or if they're superadmin.
    """
    agent = Agents.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    
    # Check access permissions
    if user.role == "superadmin" or agent.owner_user_id == user.id:
        # Get owner info for response
        owner = Users.get_user_by_id(agent.owner_user_id)
        return AgentResponse(
            **agent.model_dump(),
            owner=owner
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )


############################
# UpdateAgent
############################


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent_by_id(
    agent_id: str,
    form_data: AgentUpdateForm,
    user=Depends(get_teacher_user),
):
    """
    Update agent by ID.
    Users can only update agents they own or if they're superadmin.
    """
    try:
        agent = Agents.update_agent_by_id(agent_id, form_data, user.id)
        if agent:
            # Get the full response with owner info
            owner = Users.get_user_by_id(agent.owner_user_id)
            return AgentResponse(
                **agent.model_dump(),
                owner=owner
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error updating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


############################
# ToggleAgent
############################


@router.post("/{agent_id}/toggle", response_model=AgentResponse)
async def toggle_agent_by_id(
    agent_id: str,
    user=Depends(get_teacher_user),
):
    """
    Toggle agent enabled/disabled status.
    Users can only toggle agents they own or if they're superadmin.
    """
    try:
        agent = Agents.toggle_agent_by_id(agent_id, user.id)
        if agent:
            # Get the full response with owner info
            owner = Users.get_user_by_id(agent.owner_user_id)
            return AgentResponse(
                **agent.model_dump(),
                owner=owner
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error toggling agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


############################
# DeleteAgent
############################


@router.delete("/{agent_id}", response_model=bool)
async def delete_agent_by_id(
    agent_id: str,
    user=Depends(get_teacher_user),
):
    """
    Delete agent by ID.
    Users can only delete agents they own or if they're superadmin.
    """
    try:
        result = Agents.delete_agent_by_id(agent_id, user.id)
        if result:
            return True
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error deleting agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


############################
# GetEnabledAgents (for chat interface)
############################


@router.get("/enabled/list", response_model=List[AgentResponse])
async def get_enabled_agents(user=Depends(get_verified_user)):
    """
    Get all enabled agents for chat interface.
    All users (including students) can access this to see available agents for chat.
    """
    if user.role == "superadmin":
        # Superadmin can see all enabled agents
        all_agents = Agents.get_all_agents()
        return [agent for agent in all_agents if agent.enabled]
    elif user.role == "teacher":
        # Teachers can see their own enabled agents
        user_agents = Agents.get_agents_by_user_id(user.id)
        return [agent for agent in user_agents if agent.enabled]
    else:
        # Students can see all enabled agents for chat
        all_agents = Agents.get_all_agents()
        return [agent for agent in all_agents if agent.enabled]
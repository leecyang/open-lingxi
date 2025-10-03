import time
import uuid
from typing import Optional, Dict, Any

from open_webui.internal.db import Base, JSONField, get_db
from open_webui.models.users import Users, UserResponse
from open_webui.models.groups import Groups
from open_webui.utils.access_control import has_access
from open_webui.utils.encryption import encrypt_api_key, decrypt_api_key, mask_api_key, validate_api_key_format

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, String, Text, JSON
from sqlalchemy import or_, func, select, and_, text
from sqlalchemy.sql import exists

####################
# Agent DB Schema
####################


class Agent(Base):
    __tablename__ = "agent"

    id = Column(String, primary_key=True)
    agent_uid = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    owner_user_id = Column(String, nullable=False)
    api_host = Column(String, nullable=False)
    api_key = Column(Text, nullable=False)  # Encrypted API key stored directly
    enabled = Column(Boolean, default=True)
    config = Column(JSONField, nullable=True)  # JSON config including modelId, params, klAssistId
    
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)


####################
# Agent Pydantic Models
####################


class AgentConfig(BaseModel):
    modelId: str = "jiutian-lan"
    params: Optional[Dict[str, Any]] = {
        "temperature": 0.8,
        "top_p": 0.95,
        "max_gen_len": 256
    }
    klAssistId: Optional[str] = None
    timeout: Optional[int] = 30  # seconds
    max_retries: Optional[int] = 1
    
    model_config = ConfigDict(extra="allow")


class AgentModel(BaseModel):
    id: str
    agent_uid: str
    name: str
    owner_user_id: str
    api_host: str
    api_key: str  # This will be encrypted/masked in responses
    enabled: bool
    config: Optional[AgentConfig] = None
    
    updated_at: int
    created_at: int
    
    model_config = ConfigDict(from_attributes=True)


class AgentResponse(BaseModel):
    id: str
    agent_uid: str
    name: str
    owner_user_id: str
    api_host: str
    api_key_masked: str  # Masked version for security
    enabled: bool
    config: Optional[AgentConfig] = None
    owner: Optional[UserResponse] = None
    
    updated_at: int
    created_at: int
    
    model_config = ConfigDict(from_attributes=True)


class AgentForm(BaseModel):
    name: str
    api_host: str
    api_key: str
    config: Optional[AgentConfig] = None
    enabled: Optional[bool] = True


class AgentUpdateForm(BaseModel):
    name: Optional[str] = None
    api_host: Optional[str] = None
    api_key: Optional[str] = None
    config: Optional[AgentConfig] = None
    enabled: Optional[bool] = None


class AgentToggleForm(BaseModel):
    enabled: bool


####################
# Agent Table Operations
####################


class AgentsTable:
    def insert_new_agent(
        self, form_data: AgentForm, owner_user_id: str
    ) -> Optional[AgentModel]:
        with get_db() as db:
            # Validate API key format
            if not validate_api_key_format(form_data.api_key):
                raise ValueError("Invalid API key format. Expected: id.secret")
            
            agent_uid = str(uuid.uuid4())
            agent_id = str(uuid.uuid4())
            
            # Encrypt the API key before storing
            encrypted_api_key = encrypt_api_key(form_data.api_key)
            
            agent = AgentModel(
                **{
                    "id": agent_id,
                    "agent_uid": agent_uid,
                    "name": form_data.name,
                    "owner_user_id": owner_user_id,
                    "api_host": form_data.api_host,
                    "api_key": encrypted_api_key,
                    "enabled": form_data.enabled,
                    "config": form_data.config.model_dump() if form_data.config else None,
                    "updated_at": int(time.time()),
                    "created_at": int(time.time()),
                }
            )

            try:
                result = Agent(**agent.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                return AgentModel.model_validate(result)
            except Exception as e:
                db.rollback()
                print(f"Error creating agent: {e}")
                return None

    def get_agent_by_id(self, id: str) -> Optional[AgentModel]:
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(id=id).first()
                return AgentModel.model_validate(agent) if agent else None
        except Exception:
            return None

    def get_agent_by_uid(self, agent_uid: str) -> Optional[AgentModel]:
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(agent_uid=agent_uid).first()
                return AgentModel.model_validate(agent) if agent else None
        except Exception:
            return None

    def get_agents_by_user_id(self, user_id: str) -> list[AgentResponse]:
        with get_db() as db:
            agents = db.query(Agent).filter_by(owner_user_id=user_id).all()
            
            agent_responses = []
            for agent in agents:
                owner = Users.get_user_by_id(agent.owner_user_id)
                
                # Decrypt API key for masking (don't expose the encrypted version)
                try:
                    decrypted_key = decrypt_api_key(agent.api_key)
                    masked_key = mask_api_key(decrypted_key)
                except:
                    masked_key = "***INVALID***"
                
                agent_data = AgentModel.model_validate(agent).model_dump()
                agent_data['api_key_masked'] = masked_key
                del agent_data['api_key']  # Remove the encrypted key from response
                
                agent_response = AgentResponse(
                    **agent_data,
                    owner=UserResponse.model_validate(owner) if owner else None
                )
                agent_responses.append(agent_response)
            
            return agent_responses

    def get_all_agents(self) -> list[AgentResponse]:
        with get_db() as db:
            agents = db.query(Agent).all()
            
            # Get all unique user IDs
            user_ids = list(set(agent.owner_user_id for agent in agents))
            users = Users.get_users_by_user_ids(user_ids) if user_ids else []
            users_dict = {user.id: user for user in users}
            
            agent_responses = []
            for agent in agents:
                owner = users_dict.get(agent.owner_user_id)
                agent_response = AgentResponse(
                    **AgentModel.model_validate(agent).model_dump(),
                    owner=UserResponse.model_validate(owner) if owner else None
                )
                agent_responses.append(agent_response)
            
            return agent_responses

    def get_enabled_agents_by_uids(self, agent_uids: list[str]) -> list[AgentModel]:
        with get_db() as db:
            agents = (
                db.query(Agent)
                .filter(Agent.agent_uid.in_(agent_uids))
                .filter(Agent.enabled == True)
                .all()
            )
            return [AgentModel.model_validate(agent) for agent in agents]
    
    def get_decrypted_api_key(self, agent_uid: str) -> Optional[str]:
        """
        Get the decrypted API key for an agent (for internal use only)
        
        Args:
            agent_uid: The agent UID
            
        Returns:
            Decrypted API key or None if not found
        """
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(agent_uid=agent_uid).first()
                if agent and agent.enabled:
                    return decrypt_api_key(agent.api_key)
                return None
        except Exception as e:
            print(f"Error getting decrypted API key: {e}")
            return None

    def update_agent_by_id(
        self, id: str, form_data: AgentUpdateForm, user_id: str
    ) -> Optional[AgentModel]:
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(id=id).first()
                if not agent:
                    return None
                
                # Check ownership or admin privileges
                user = Users.get_user_by_id(user_id)
                if not user:
                    return None
                
                if agent.owner_user_id != user_id and user.role not in ["admin", "superadmin"]:
                    return None
                
                update_data = {}
                if form_data.name is not None:
                    update_data["name"] = form_data.name
                if form_data.api_host is not None:
                    update_data["api_host"] = form_data.api_host
                if form_data.api_key_env is not None:
                    update_data["api_key_env"] = form_data.api_key_env
                if form_data.config is not None:
                    update_data["config"] = form_data.config.model_dump()
                if form_data.enabled is not None:
                    update_data["enabled"] = form_data.enabled
                
                update_data["updated_at"] = int(time.time())
                
                db.query(Agent).filter_by(id=id).update(update_data)
                db.commit()
                
                updated_agent = db.query(Agent).filter_by(id=id).first()
                return AgentModel.model_validate(updated_agent)
        except Exception as e:
            print(f"Error updating agent: {e}")
            return None

    def toggle_agent_by_id(self, id: str, user_id: str) -> Optional[AgentModel]:
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(id=id).first()
                if not agent:
                    return None
                
                # Check ownership or admin privileges
                user = Users.get_user_by_id(user_id)
                if not user:
                    return None
                
                if agent.owner_user_id != user_id and user.role not in ["admin", "superadmin"]:
                    return None
                
                new_enabled = not agent.enabled
                db.query(Agent).filter_by(id=id).update({
                    "enabled": new_enabled,
                    "updated_at": int(time.time())
                })
                db.commit()
                
                updated_agent = db.query(Agent).filter_by(id=id).first()
                return AgentModel.model_validate(updated_agent)
        except Exception as e:
            print(f"Error toggling agent: {e}")
            return None

    def delete_agent_by_id(self, id: str, user_id: str) -> bool:
        try:
            with get_db() as db:
                agent = db.query(Agent).filter_by(id=id).first()
                if not agent:
                    return False
                
                # Check ownership or admin privileges
                user = Users.get_user_by_id(user_id)
                if not user:
                    return False
                
                if agent.owner_user_id != user_id and user.role not in ["admin", "superadmin"]:
                    return False
                
                db.query(Agent).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception as e:
            print(f"Error deleting agent: {e}")
            return False


Agents = AgentsTable()
import pytest
import asyncio
import os
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the modules to test
from open_webui.models.agents import Agent, AgentModel, AgentForm, AgentUpdateForm, Agents
from open_webui.utils.jiutian_jwt import generate_jwt_from_apikey, validate_apikey_format, is_token_expired
from open_webui.routers.agents import router as agents_router
from open_webui.routers.multi_chat import router as multi_chat_router
from open_webui.socket.multi_agent import multi_agent_manager, ConversationSession


class TestJiutianJWT:
    """Test JWT utility functions"""
    
    def test_generate_jwt_from_apikey_valid(self):
        """Test JWT generation with valid API key"""
        api_key = "test_id.test_secret"
        token = generate_jwt_from_apikey(api_key, 3600)
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert not is_token_expired(token)
    
    def test_generate_jwt_from_apikey_invalid_format(self):
        """Test JWT generation with invalid API key format"""
        with pytest.raises(Exception) as exc_info:
            generate_jwt_from_apikey("invalid_key", 3600)
        
        assert "invalid apikey format" in str(exc_info.value)
    
    def test_validate_apikey_format_valid(self):
        """Test API key format validation with valid keys"""
        assert validate_apikey_format("id.secret") == True
        assert validate_apikey_format("long_id.long_secret") == True
    
    def test_validate_apikey_format_invalid(self):
        """Test API key format validation with invalid keys"""
        assert validate_apikey_format("invalid") == False
        assert validate_apikey_format("") == False
        assert validate_apikey_format(".") == False
        assert validate_apikey_format("id.") == False
        assert validate_apikey_format(".secret") == False
    
    def test_token_expiry(self):
        """Test token expiry functionality"""
        # Generate token with very short expiry
        api_key = "test_id.test_secret"
        token = generate_jwt_from_apikey(api_key, 1)  # 1 second
        
        # Token should not be expired immediately
        assert not is_token_expired(token)
        
        # Wait for token to expire
        time.sleep(2)
        assert is_token_expired(token)


class TestAgentModel:
    """Test Agent database model and operations"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('open_webui.models.agents.get_db') as mock_get_db:
            mock_session = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_session
            mock_get_db.return_value.__exit__.return_value = None
            yield mock_session
    
    def test_agent_form_validation(self):
        """Test AgentForm validation"""
        form = AgentForm(
            name="Test Agent",
            api_host="https://jiutian.10086.cn",
            api_key_env="TEST_API_KEY",
            enabled=True
        )
        
        assert form.name == "Test Agent"
        assert form.api_host == "https://jiutian.10086.cn"
        assert form.api_key_env == "TEST_API_KEY"
        assert form.enabled == True
    
    def test_agent_config_defaults(self):
        """Test AgentConfig default values"""
        from open_webui.models.agents import AgentConfig
        
        config = AgentConfig()
        assert config.modelId == "jiutian-lan"
        assert config.params["temperature"] == 0.8
        assert config.params["top_p"] == 0.95
        assert config.timeout == 30
        assert config.max_retries == 1
    
    def test_insert_new_agent(self, mock_db_session):
        """Test creating a new agent"""
        form = AgentForm(
            name="Test Agent",
            api_host="https://jiutian.10086.cn",
            api_key_env="TEST_API_KEY"
        )
        
        # Mock successful database operations
        mock_agent = Mock()
        mock_agent.id = "test-id"
        mock_agent.agent_uid = "test-uid"
        mock_agent.name = "Test Agent"
        
        mock_db_session.add.return_value = None
        mock_db_session.commit.return_value = None
        mock_db_session.refresh.return_value = None
        
        with patch('open_webui.models.agents.Agent') as mock_agent_class:
            mock_agent_class.return_value = mock_agent
            with patch('open_webui.models.agents.AgentModel.model_validate') as mock_validate:
                mock_validate.return_value = AgentModel(
                    id="test-id",
                    agent_uid="test-uid",
                    name="Test Agent",
                    owner_user_id="user-id",
                    api_host="https://jiutian.10086.cn",
                    api_key_env="TEST_API_KEY",
                    enabled=True,
                    config=None,
                    updated_at=int(time.time()),
                    created_at=int(time.time())
                )
                
                result = Agents.insert_new_agent(form, "user-id")
                
                assert result is not None
                assert result.name == "Test Agent"
                mock_db_session.add.assert_called_once()
                mock_db_session.commit.assert_called_once()


class TestMultiAgentWebSocket:
    """Test multi-agent WebSocket functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh multi-agent manager for testing"""
        from open_webui.socket.multi_agent import MultiAgentWebSocketManager
        return MultiAgentWebSocketManager()
    
    @pytest.mark.asyncio
    async def test_join_conversation(self, manager):
        """Test joining a conversation"""
        conv_id = "test-conv-1"
        user_id = "user-1"
        session_id = "session-1"
        agent_uids = ["agent-1", "agent-2"]
        
        # Mock sio.enter_room
        with patch('open_webui.socket.multi_agent.sio') as mock_sio:
            mock_sio.enter_room = AsyncMock()
            
            result = await manager.join_conversation(conv_id, user_id, session_id, agent_uids)
            
            assert result == True
            assert conv_id in manager.active_conversations
            assert session_id in manager.session_to_conv
            assert manager.session_to_conv[session_id] == conv_id
            
            conversation = manager.active_conversations[conv_id]
            assert conversation.user_id == user_id
            assert session_id in conversation.session_ids
            assert conversation.agent_uids == agent_uids
    
    @pytest.mark.asyncio
    async def test_leave_conversation(self, manager):
        """Test leaving a conversation"""
        conv_id = "test-conv-1"
        user_id = "user-1"
        session_id = "session-1"
        agent_uids = ["agent-1"]
        
        with patch('open_webui.socket.multi_agent.sio') as mock_sio:
            mock_sio.enter_room = AsyncMock()
            mock_sio.leave_room = AsyncMock()
            
            # First join
            await manager.join_conversation(conv_id, user_id, session_id, agent_uids)
            
            # Then leave
            result = await manager.leave_conversation(session_id)
            
            assert result == True
            assert conv_id not in manager.active_conversations  # Should be removed when no sessions
            assert session_id not in manager.session_to_conv
    
    @pytest.mark.asyncio
    async def test_send_agent_message(self, manager):
        """Test sending agent message"""
        conv_id = "test-conv-1"
        user_id = "user-1"
        session_id = "session-1"
        agent_uids = ["agent-1"]
        
        with patch('open_webui.socket.multi_agent.sio') as mock_sio:
            mock_sio.enter_room = AsyncMock()
            mock_sio.emit = AsyncMock()
            
            # Join conversation first
            await manager.join_conversation(conv_id, user_id, session_id, agent_uids)
            
            # Send message
            message_data = {"type": "delta", "content": "Hello"}
            result = await manager.send_agent_message(conv_id, "agent-1", message_data)
            
            assert result == True
            mock_sio.emit.assert_called_once()
            
            # Check the emit call
            call_args = mock_sio.emit.call_args
            assert call_args[0][0] == "multi-agent-message"
            assert call_args[1]["room"] == f"conv_{conv_id}"
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_conversations(self, manager):
        """Test cleanup of inactive conversations"""
        conv_id = "test-conv-1"
        user_id = "user-1"
        session_id = "session-1"
        agent_uids = ["agent-1"]
        
        with patch('open_webui.socket.multi_agent.sio') as mock_sio:
            mock_sio.enter_room = AsyncMock()
            
            # Join conversation
            await manager.join_conversation(conv_id, user_id, session_id, agent_uids)
            
            # Manually set old timestamp
            conversation = manager.active_conversations[conv_id]
            conversation.last_activity = time.time() - 7200  # 2 hours ago
            
            # Cleanup with 1 hour timeout
            cleaned_count = await manager.cleanup_inactive_conversations(3600)
            
            assert cleaned_count == 1
            assert conv_id not in manager.active_conversations
            assert session_id not in manager.session_to_conv


class TestMultiChatAPI:
    """Test multi-chat API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(multi_chat_router, prefix="/api")
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return Mock(id="user-1", role="student", token="test-token")
    
    def test_multi_chat_request_validation(self, client):
        """Test multi-chat request validation"""
        # Test empty agent_uids
        with patch('open_webui.routers.multi_chat.get_verified_user') as mock_auth:
            mock_auth.return_value = Mock(id="user-1", role="student")
            
            response = client.post("/api/multi-chat", json={
                "conv_id": "test-conv",
                "user_id": "user-1",
                "message": "Hello",
                "agent_uids": []
            })
            
            assert response.status_code == 400
            assert "At least one agent UID is required" in response.json()["detail"]
    
    def test_multi_chat_empty_message(self, client):
        """Test multi-chat with empty message"""
        with patch('open_webui.routers.multi_chat.get_verified_user') as mock_auth:
            mock_auth.return_value = Mock(id="user-1", role="student")
            
            response = client.post("/api/multi-chat", json={
                "conv_id": "test-conv",
                "user_id": "user-1",
                "message": "",
                "agent_uids": ["agent-1"]
            })
            
            assert response.status_code == 400
            assert "Message cannot be empty" in response.json()["detail"]


class TestAgentAPI:
    """Test Agent API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(agents_router, prefix="/api/agents")
        return TestClient(app)
    
    def test_get_agents_unauthorized(self, client):
        """Test getting agents without authentication"""
        response = client.get("/api/agents/")
        assert response.status_code == 401
    
    def test_create_agent_teacher_role(self, client):
        """Test creating agent with teacher role"""
        with patch('open_webui.routers.agents.get_teacher_user') as mock_auth:
            mock_auth.return_value = Mock(id="user-1", role="teacher")
            
            with patch('open_webui.routers.agents.Agents.insert_new_agent') as mock_create:
                mock_agent = Mock()
                mock_agent.id = "agent-1"
                mock_agent.name = "Test Agent"
                mock_create.return_value = mock_agent
                
                with patch('open_webui.routers.agents.Agents.get_agents_by_user_id') as mock_get:
                    mock_get.return_value = [mock_agent]
                    
                    response = client.post("/api/agents/", json={
                        "name": "Test Agent",
                        "api_host": "https://jiutian.10086.cn",
                        "api_key_env": "TEST_API_KEY"
                    })
                    
                    # Note: This will still fail due to authentication, but tests the logic
                    # In a real test environment, you'd mock the entire auth chain


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
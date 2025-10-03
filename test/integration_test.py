#!/usr/bin/env python3
"""
Integration tests for multi-agent system
Tests the complete flow from API calls to WebSocket responses
"""

import asyncio
import json
import os
import time
import uuid
import aiohttp
import socketio
import pytest
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = os.getenv('TEST_BASE_URL', 'http://localhost:8080')
WS_URL = os.getenv('TEST_WS_URL', 'http://localhost:8080')
TEST_TOKEN = os.getenv('TEST_TOKEN', 'test-token')
TEST_API_KEY = os.getenv('TEST_JIUTIAN_API_KEY', 'test_id.test_secret')

# Mock Jiutian API server for testing
class MockJiutianServer:
    """Mock server that simulates Jiutian API responses"""
    
    def __init__(self, port=9999):
        self.port = port
        self.app = None
        self.runner = None
        
    async def start(self):
        """Start the mock server"""
        from aiohttp import web
        
        self.app = web.Application()
        self.app.router.add_post('/largemodel/api/v1/completions', self.handle_completions)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, 'localhost', self.port)
        await site.start()
        
        logger.info(f"Mock Jiutian server started on port {self.port}")
    
    async def stop(self):
        """Stop the mock server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Mock Jiutian server stopped")
    
    async def handle_completions(self, request):
        """Handle completions API requests"""
        try:
            data = await request.json()
            
            # Validate request
            required_fields = ['modelId', 'prompt', 'stream']
            for field in required_fields:
                if field not in data:
                    return web.json_response(
                        {'error': f'Missing required field: {field}'}, 
                        status=400
                    )
            
            # Simulate streaming response
            if data.get('stream', False):
                return await self.stream_response(data)
            else:
                return await self.single_response(data)
                
        except Exception as e:
            logger.error(f"Error in mock completions handler: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def stream_response(self, data):
        """Generate streaming response"""
        from aiohttp import web
        
        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        
        await response.prepare()
        
        # Simulate agent thinking
        await response.write(b'data:{"response":"","delta":"","finished":null}\n\n')
        await asyncio.sleep(0.1)
        
        # Simulate incremental response
        full_response = f"这是来自模型 {data['modelId']} 对问题 '{data['prompt']}' 的回答。"
        
        accumulated = ""
        for i, char in enumerate(full_response):
            accumulated += char
            delta_data = {
                "response": accumulated,
                "delta": char,
                "finished": None
            }
            
            await response.write(f'data:{json.dumps(delta_data)}\n\n'.encode())
            await asyncio.sleep(0.05)  # Simulate typing delay
        
        # Send completion
        final_data = {
            "Usage": {
                "completion_tokens": len(full_response),
                "prompt_tokens": len(data['prompt']),
                "total_tokens": len(full_response) + len(data['prompt'])
            },
            "response": accumulated,
            "delta": "[EOS]",
            "finished": "Stop",
            "history": data.get('history', []) + [[data['prompt'], accumulated]],
            "prompt": data['prompt']
        }
        
        await response.write(f'data:{json.dumps(final_data)}\n\n'.encode())
        await response.write_eof()
        
        return response
    
    async def single_response(self, data):
        """Generate single response"""
        from aiohttp import web
        
        response_text = f"这是来自模型 {data['modelId']} 对问题 '{data['prompt']}' 的回答。"
        
        response_data = {
            "response": response_text,
            "finished": "Stop",
            "Usage": {
                "completion_tokens": len(response_text),
                "prompt_tokens": len(data['prompt']),
                "total_tokens": len(response_text) + len(data['prompt'])
            }
        }
        
        return web.json_response(response_data)


class MultiAgentIntegrationTest:
    """Integration test suite for multi-agent system"""
    
    def __init__(self):
        self.mock_server = MockJiutianServer()
        self.sio = None
        self.received_messages = []
        self.conversation_complete = False
        
    async def setup(self):
        """Set up test environment"""
        # Start mock server
        await self.mock_server.start()
        
        # Wait for server to be ready
        await asyncio.sleep(1)
        
        # Set up environment variable for testing
        os.environ['TEST_JIUTIAN_API_KEY'] = TEST_API_KEY
        
        logger.info("Test environment set up")
    
    async def teardown(self):
        """Clean up test environment"""
        if self.sio:
            await self.sio.disconnect()
        
        await self.mock_server.stop()
        logger.info("Test environment cleaned up")
    
    async def test_agent_crud_operations(self):
        """Test Agent CRUD operations"""
        logger.info("Testing Agent CRUD operations...")
        
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
            
            # Test creating an agent
            agent_data = {
                "name": "Test Agent",
                "api_host": f"http://localhost:{self.mock_server.port}",
                "api_key_env": "TEST_JIUTIAN_API_KEY",
                "enabled": True,
                "config": {
                    "modelId": "jiutian-lan",
                    "params": {
                        "temperature": 0.8,
                        "top_p": 0.95
                    }
                }
            }
            
            # Create agent
            async with session.post(
                f"{BASE_URL}/api/agents/",
                json=agent_data,
                headers=headers
            ) as resp:
                if resp.status == 201:
                    agent = await resp.json()
                    agent_id = agent['id']
                    logger.info(f"Created agent: {agent_id}")
                    
                    # Test getting agent
                    async with session.get(
                        f"{BASE_URL}/api/agents/{agent_id}",
                        headers=headers
                    ) as get_resp:
                        if get_resp.status == 200:
                            retrieved_agent = await get_resp.json()
                            assert retrieved_agent['name'] == agent_data['name']
                            logger.info("Agent retrieval successful")
                        else:
                            logger.error(f"Failed to get agent: {get_resp.status}")
                    
                    # Test updating agent
                    update_data = {"name": "Updated Test Agent"}
                    async with session.put(
                        f"{BASE_URL}/api/agents/{agent_id}",
                        json=update_data,
                        headers=headers
                    ) as update_resp:
                        if update_resp.status == 200:
                            updated_agent = await update_resp.json()
                            assert updated_agent['name'] == update_data['name']
                            logger.info("Agent update successful")
                        else:
                            logger.error(f"Failed to update agent: {update_resp.status}")
                    
                    # Test toggling agent
                    async with session.post(
                        f"{BASE_URL}/api/agents/{agent_id}/toggle",
                        headers=headers
                    ) as toggle_resp:
                        if toggle_resp.status == 200:
                            toggled_agent = await toggle_resp.json()
                            logger.info(f"Agent toggle successful, enabled: {toggled_agent['enabled']}")
                        else:
                            logger.error(f"Failed to toggle agent: {toggle_resp.status}")
                    
                    # Clean up - delete agent
                    async with session.delete(
                        f"{BASE_URL}/api/agents/{agent_id}",
                        headers=headers
                    ) as delete_resp:
                        if delete_resp.status == 200:
                            logger.info("Agent deletion successful")
                        else:
                            logger.error(f"Failed to delete agent: {delete_resp.status}")
                
                else:
                    logger.error(f"Failed to create agent: {resp.status}")
                    response_text = await resp.text()
                    logger.error(f"Response: {response_text}")
    
    async def test_multi_chat_flow(self):
        """Test complete multi-chat flow"""
        logger.info("Testing multi-chat flow...")
        
        # First, create test agents
        agent_ids = await self.create_test_agents()
        
        if not agent_ids:
            logger.error("Failed to create test agents")
            return
        
        try:
            # Set up WebSocket connection
            await self.setup_websocket()
            
            # Send multi-chat request
            conv_id = str(uuid.uuid4())
            await self.send_multi_chat_request(conv_id, agent_ids)
            
            # Wait for responses
            await self.wait_for_responses(timeout=30)
            
            # Verify responses
            self.verify_responses()
            
        finally:
            # Clean up agents
            await self.cleanup_test_agents(agent_ids)
    
    async def create_test_agents(self) -> List[str]:
        """Create test agents for multi-chat testing"""
        agent_ids = []
        
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
            
            for i in range(2):  # Create 2 test agents
                agent_data = {
                    "name": f"Test Agent {i+1}",
                    "api_host": f"http://localhost:{self.mock_server.port}",
                    "api_key_env": "TEST_JIUTIAN_API_KEY",
                    "enabled": True,
                    "config": {
                        "modelId": "jiutian-lan",
                        "params": {
                            "temperature": 0.8,
                            "top_p": 0.95
                        }
                    }
                }
                
                async with session.post(
                    f"{BASE_URL}/api/agents/",
                    json=agent_data,
                    headers=headers
                ) as resp:
                    if resp.status == 201:
                        agent = await resp.json()
                        agent_ids.append(agent['agent_uid'])
                        logger.info(f"Created test agent: {agent['agent_uid']}")
                    else:
                        logger.error(f"Failed to create test agent {i+1}: {resp.status}")
        
        return agent_ids
    
    async def cleanup_test_agents(self, agent_uids: List[str]):
        """Clean up test agents"""
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
            
            # Get all agents to find IDs
            async with session.get(f"{BASE_URL}/api/agents/", headers=headers) as resp:
                if resp.status == 200:
                    agents = await resp.json()
                    
                    for agent in agents:
                        if agent['agent_uid'] in agent_uids:
                            async with session.delete(
                                f"{BASE_URL}/api/agents/{agent['id']}",
                                headers=headers
                            ) as delete_resp:
                                if delete_resp.status == 200:
                                    logger.info(f"Cleaned up agent: {agent['agent_uid']}")
    
    async def setup_websocket(self):
        """Set up WebSocket connection"""
        self.sio = socketio.AsyncClient()
        
        @self.sio.event
        async def connect():
            logger.info("WebSocket connected")
        
        @self.sio.event
        async def disconnect():
            logger.info("WebSocket disconnected")
        
        @self.sio.on('multi-agent-message')
        async def on_agent_message(data):
            logger.info(f"Received agent message: {data}")
            self.received_messages.append(data)
        
        @self.sio.on('multi-agent-system')
        async def on_system_message(data):
            logger.info(f"Received system message: {data}")
            if data.get('message_type') == 'complete':
                self.conversation_complete = True
        
        await self.sio.connect(f"{WS_URL}/ws/socket.io", auth={'token': TEST_TOKEN})
    
    async def send_multi_chat_request(self, conv_id: str, agent_uids: List[str]):
        """Send multi-chat request"""
        # Join conversation
        await self.sio.emit('multi-agent-join', {
            'auth': {'token': TEST_TOKEN},
            'conv_id': conv_id,
            'agent_uids': agent_uids
        })
        
        # Wait a bit for join to complete
        await asyncio.sleep(1)
        
        # Send multi-chat request via HTTP API
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
            
            request_data = {
                "conv_id": conv_id,
                "user_id": "test-user",
                "message": "请介绍一下你自己",
                "agent_uids": agent_uids,
                "history": []
            }
            
            async with session.post(
                f"{BASE_URL}/api/multi-chat",
                json=request_data,
                headers=headers
            ) as resp:
                if resp.status == 202:
                    response = await resp.json()
                    logger.info(f"Multi-chat request accepted: {response}")
                else:
                    logger.error(f"Multi-chat request failed: {resp.status}")
                    response_text = await resp.text()
                    logger.error(f"Response: {response_text}")
    
    async def wait_for_responses(self, timeout: int = 30):
        """Wait for agent responses"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.conversation_complete:
                logger.info("Conversation completed")
                break
            
            await asyncio.sleep(0.5)
        
        if not self.conversation_complete:
            logger.warning("Conversation did not complete within timeout")
    
    def verify_responses(self):
        """Verify that we received expected responses"""
        logger.info(f"Received {len(self.received_messages)} messages")
        
        # Check that we received messages from agents
        agent_messages = [msg for msg in self.received_messages if msg.get('agent_id') != 'system']
        
        if len(agent_messages) > 0:
            logger.info("✓ Received agent responses")
        else:
            logger.error("✗ No agent responses received")
        
        # Check for completion messages
        complete_messages = [
            msg for msg in self.received_messages 
            if msg.get('data', {}).get('type') == 'complete'
        ]
        
        if len(complete_messages) > 0:
            logger.info("✓ Received completion messages")
        else:
            logger.error("✗ No completion messages received")


async def run_integration_tests():
    """Run all integration tests"""
    test_suite = MultiAgentIntegrationTest()
    
    try:
        await test_suite.setup()
        
        # Run tests
        await test_suite.test_agent_crud_operations()
        await test_suite.test_multi_chat_flow()
        
        logger.info("All integration tests completed")
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        raise
    
    finally:
        await test_suite.teardown()


if __name__ == "__main__":
    # Run integration tests
    asyncio.run(run_integration_tests())
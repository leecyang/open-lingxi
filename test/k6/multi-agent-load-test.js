import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Counter, Trend } from 'k6/metrics';

// Custom metrics
const wsConnectionErrors = new Counter('ws_connection_errors');
const wsMessagesSent = new Counter('ws_messages_sent');
const wsMessagesReceived = new Counter('ws_messages_received');
const agentResponseTime = new Trend('agent_response_time');
const multiChatRequestRate = new Rate('multi_chat_request_success');

// Test configuration
export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 users
    { duration: '1m', target: 10 },   // Stay at 10 users
    { duration: '30s', target: 20 },  // Ramp up to 20 users
    { duration: '2m', target: 20 },   // Stay at 20 users
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests should be below 2s
    ws_connection_errors: ['count<10'], // Less than 10 WebSocket connection errors
    agent_response_time: ['p(90)<5000'], // 90% of agent responses should be below 5s
    multi_chat_request_success: ['rate>0.9'], // 90% success rate for multi-chat requests
  },
};

// Test data
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const WS_URL = __ENV.WS_URL || 'ws://localhost:8080';
const TEST_TOKEN = __ENV.TEST_TOKEN || 'test-token';

// Sample agent UIDs (these should exist in your test environment)
const AGENT_UIDS = [
  'agent-1',
  'agent-2',
  'agent-3'
];

// Sample messages for testing
const TEST_MESSAGES = [
  '你好，请介绍一下自己',
  '今天天气怎么样？',
  '请解释一下人工智能的基本概念',
  '帮我写一个简单的Python函数',
  '什么是机器学习？',
  '请推荐一些学习编程的资源',
  '如何提高工作效率？',
  '请解释一下区块链技术'
];

// Helper function to generate random conversation ID
function generateConvId() {
  return `conv-${Math.random().toString(36).substr(2, 9)}`;
}

// Helper function to get random message
function getRandomMessage() {
  return TEST_MESSAGES[Math.floor(Math.random() * TEST_MESSAGES.length)];
}

// Helper function to get random agent UIDs
function getRandomAgentUids(count = 2) {
  const shuffled = AGENT_UIDS.sort(() => 0.5 - Math.random());
  return shuffled.slice(0, Math.min(count, AGENT_UIDS.length));
}

// Test scenario 1: Multi-chat API load test
export function testMultiChatAPI() {
  const convId = generateConvId();
  const message = getRandomMessage();
  const agentUids = getRandomAgentUids();
  
  const payload = {
    conv_id: convId,
    user_id: `user-${__VU}`,
    message: message,
    agent_uids: agentUids,
    history: []
  };
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TEST_TOKEN}`,
    },
  };
  
  const response = http.post(`${BASE_URL}/api/multi-chat`, JSON.stringify(payload), params);
  
  const success = check(response, {
    'multi-chat request successful': (r) => r.status === 202,
    'response has conv_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.conv_id === convId;
      } catch (e) {
        return false;
      }
    },
  });
  
  multiChatRequestRate.add(success);
  
  if (!success) {
    console.error(`Multi-chat request failed: ${response.status} ${response.body}`);
  }
  
  sleep(1);
}

// Test scenario 2: WebSocket connection and messaging
export function testWebSocketConnection() {
  const convId = generateConvId();
  const agentUids = getRandomAgentUids();
  
  const url = `${WS_URL}/ws/socket.io/?transport=websocket`;
  
  const res = ws.connect(url, {}, function (socket) {
    let messageCount = 0;
    let startTime = Date.now();
    let responseReceived = false;
    
    socket.on('open', function () {
      console.log(`WebSocket connected for VU ${__VU}`);
      
      // Authenticate
      socket.send(JSON.stringify({
        type: 'auth',
        token: TEST_TOKEN
      }));
      
      // Join multi-agent conversation
      socket.send(JSON.stringify({
        type: 'multi-agent-join',
        data: {
          auth: { token: TEST_TOKEN },
          conv_id: convId,
          agent_uids: agentUids
        }
      }));
      
      wsMessagesSent.add(1);
    });
    
    socket.on('message', function (message) {
      try {
        const data = JSON.parse(message);
        wsMessagesReceived.add(1);
        
        if (data.type === 'multi-agent-message') {
          if (!responseReceived) {
            responseReceived = true;
            const responseTime = Date.now() - startTime;
            agentResponseTime.add(responseTime);
          }
          messageCount++;
        }
        
        if (data.type === 'multi-agent-joined') {
          console.log(`Joined conversation ${convId} for VU ${__VU}`);
          
          // Send a test message
          startTime = Date.now();
          socket.send(JSON.stringify({
            type: 'multi-chat-request',
            data: {
              conv_id: convId,
              user_id: `user-${__VU}`,
              message: getRandomMessage(),
              agent_uids: agentUids
            }
          }));
          
          wsMessagesSent.add(1);
        }
        
      } catch (e) {
        console.error(`Error parsing WebSocket message: ${e}`);
      }
    });
    
    socket.on('error', function (e) {
      console.error(`WebSocket error for VU ${__VU}: ${e}`);
      wsConnectionErrors.add(1);
    });
    
    socket.on('close', function () {
      console.log(`WebSocket closed for VU ${__VU}, received ${messageCount} messages`);
    });
    
    // Keep connection open for a while to receive responses
    sleep(10);
  });
  
  check(res, {
    'WebSocket connection successful': (r) => r && r.status === 101,
  });
}

// Test scenario 3: Agent management API
export function testAgentManagementAPI() {
  // Test getting agents list
  const getAgentsResponse = http.get(`${BASE_URL}/api/agents/enabled/list`, {
    headers: {
      'Authorization': `Bearer ${TEST_TOKEN}`,
    },
  });
  
  check(getAgentsResponse, {
    'get enabled agents successful': (r) => r.status === 200,
    'response is array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body);
      } catch (e) {
        return false;
      }
    },
  });
  
  // Test getting conversation status (if we have a conversation)
  if (__VU === 1) { // Only one VU tests this to avoid conflicts
    const convId = generateConvId();
    const statusResponse = http.get(`${BASE_URL}/api/conversations/${convId}/status`, {
      headers: {
        'Authorization': `Bearer ${TEST_TOKEN}`,
      },
    });
    
    // This might return 404 if conversation doesn't exist, which is expected
    check(statusResponse, {
      'conversation status request processed': (r) => r.status === 404 || r.status === 200,
    });
  }
  
  sleep(0.5);
}

// Main test function
export default function () {
  const scenario = Math.random();
  
  if (scenario < 0.5) {
    // 50% of the time, test multi-chat API
    testMultiChatAPI();
  } else if (scenario < 0.8) {
    // 30% of the time, test WebSocket connections
    testWebSocketConnection();
  } else {
    // 20% of the time, test agent management API
    testAgentManagementAPI();
  }
}

// Setup function (runs once per VU)
export function setup() {
  console.log('Starting multi-agent load test...');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`WebSocket URL: ${WS_URL}`);
  console.log(`Test agents: ${AGENT_UIDS.join(', ')}`);
  
  // Verify that the API is accessible
  const healthCheck = http.get(`${BASE_URL}/health`);
  if (healthCheck.status !== 200) {
    console.warn(`Health check failed: ${healthCheck.status}`);
  }
  
  return {
    baseUrl: BASE_URL,
    wsUrl: WS_URL,
    agentUids: AGENT_UIDS
  };
}

// Teardown function (runs once after all VUs finish)
export function teardown(data) {
  console.log('Multi-agent load test completed');
  console.log(`WebSocket messages sent: ${wsMessagesSent.count}`);
  console.log(`WebSocket messages received: ${wsMessagesReceived.count}`);
  console.log(`WebSocket connection errors: ${wsConnectionErrors.count}`);
}
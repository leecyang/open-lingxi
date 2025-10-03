# Multi-Agent System for Open WebUI

这是一个为 Open WebUI 项目开发的多智能体系统，支持与九天大模型应用平台的集成。该系统允许用户同时与多个AI智能体进行对话，并实时查看各个智能体的响应。

## 功能特性

### 核心功能
- **多智能体并发对话**: 支持同时向多个智能体发送消息并接收响应
- **实时流式响应**: 通过WebSocket实现实时的流式消息推送
- **九天API集成**: 完全兼容九天大模型应用平台的API规范
- **JWT认证**: 按照九天API手册实现的HS256 JWT token生成
- **知识助手支持**: 支持配置知识助手ID以获取增强的回答能力

### 权限管理 (RBAC)
- **超级管理员 (superadmin)**: 可以管理所有智能体，包括创建、编辑、删除和启用/禁用
- **教师 (teacher)**: 可以管理自己创建的智能体
- **学生 (student)**: 只能使用已启用的智能体进行对话

### 技术特性
- **并发控制**: 使用信号量限制并发请求数量
- **超时和重试**: 支持per-agent的超时设置和重试机制
- **错误处理**: 完善的错误处理和用户反馈
- **性能监控**: 支持Prometheus监控和Grafana可视化

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 (Svelte)  │    │  后端 (FastAPI)  │    │  九天API服务器   │
│                 │    │                 │    │                 │
│ MultiAgentMatrix│◄──►│ Multi-Chat API  │◄──►│ /completions    │
│ AgentManagement │    │ Agent CRUD API  │    │ (Stream)        │
│                 │    │ WebSocket       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         │              ┌─────────────────┐
         │              │ PostgreSQL DB   │
         │              │ - agents        │
         │              │ - users         │
         └──────────────┤ - conversations │
                        └─────────────────┘
                        ┌─────────────────┐
                        │ Redis           │
                        │ - WebSocket     │
                        │ - Session       │
                        └─────────────────┘
```

## 环境变量配置

### 必需的环境变量

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/openwebui

# Redis配置 (用于WebSocket)
WEBSOCKET_MANAGER=redis
WEBSOCKET_REDIS_URL=redis://localhost:6379/0
ENABLE_WEBSOCKET_SUPPORT=true

# 安全配置
WEBUI_SECRET_KEY=your-secret-key-change-this-in-production

# 九天API密钥 (根据需要配置多个)
JIUTIAN_API_KEY_1=your_api_key_id.your_api_secret
JIUTIAN_API_KEY_2=another_api_key_id.another_api_secret
JIUTIAN_API_KEY_3=third_api_key_id.third_api_secret
```

### 可选的环境变量

```bash
# 认证配置
WEBUI_AUTH=true
DEFAULT_USER_ROLE=student
ENABLE_SIGNUP=true

# 日志配置
LOG_LEVEL=INFO

# CORS配置
CORS_ALLOW_ORIGIN=*

# 并发控制
MAX_CONCURRENT_REQUESTS=10
```

## 部署指南

### 使用 Docker Compose (推荐)

1. **克隆项目并进入目录**
```bash
git clone <repository-url>
cd open-lingxi
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的环境变量
```

3. **启动服务**
```bash
# 启动完整的多智能体系统
docker-compose -f docker-compose.multi-agent.yml up -d

# 或者启动包含监控的完整系统
docker-compose -f docker-compose.multi-agent.yml --profile monitoring up -d
```

4. **验证部署**
```bash
# 检查服务状态
docker-compose -f docker-compose.multi-agent.yml ps

# 查看日志
docker-compose -f docker-compose.multi-agent.yml logs -f backend
```

### 手动部署

#### 后端部署

1. **安装依赖**
```bash
cd backend
pip install -r requirements.txt
```

2. **数据库迁移**
```bash
# 确保PostgreSQL运行并创建数据库
python -m alembic upgrade head
```

3. **启动后端服务**
```bash
python -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```

#### 前端部署

1. **安装依赖**
```bash
npm install
```

2. **构建前端**
```bash
npm run build
```

3. **启动前端服务**
```bash
npm run preview
# 或者使用生产服务器如nginx
```

## 九天API密钥获取和配置

### 1. 获取API密钥

根据九天大模型应用平台用户使用手册：

1. 登录九天大模型应用平台
2. 进入API管理页面
3. 创建新的API密钥
4. 复制API密钥，格式为：`{id}.{secret}`

例如：`646ae749bcf5bc1a1498aeaf.IbIpYGawQ8VwQ2HYTohDCKJP/aGgGaC`

### 2. 配置环境变量

将API密钥配置到环境变量中：

```bash
# 在 .env 文件中添加
JIUTIAN_API_KEY_1=646ae749bcf5bc1a1498aeaf.IbIpYGawQ8VwQ2HYTohDCKJP/aGgGaC
```

### 3. 测试API连接

使用提供的测试脚本验证API连接：

```python
from open_webui.utils.jiutian_jwt import generate_jwt_from_apikey

# 测试JWT生成
api_key = "your_id.your_secret"
token = generate_jwt_from_apikey(api_key, 3600)
print(f"Generated token: {token}")
```

## 在UI中创建和管理智能体

### 超级管理员操作

1. **访问管理页面**
   - 登录后访问 `/admin/agents`

2. **创建智能体**
   - 点击"创建智能体"按钮
   - 填写基本信息：
     - 智能体名称
     - API主机地址 (如：`https://jiutian.10086.cn`)
     - API密钥环境变量名 (如：`JIUTIAN_API_KEY_1`)
   - 配置模型参数：
     - 选择模型 (jiutian-lan, jiutian-med, jiutian-cus, jiutian-gov)
     - 设置温度、Top-p、最大长度等参数
     - 可选：配置知识助手ID
   - 设置高级选项：
     - 超时时间
     - 最大重试次数

3. **管理智能体**
   - 查看所有智能体列表
   - 启用/禁用智能体
   - 编辑智能体配置
   - 删除智能体

### 教师操作

1. **访问教师页面**
   - 登录后访问 `/teacher/agents`

2. **管理自己的智能体**
   - 只能看到和管理自己创建的智能体
   - 功能与超级管理员相同，但范围限制在自己的智能体

### 学生使用

1. **多智能体对话**
   - 访问多智能体聊天页面
   - 选择要对话的智能体（可多选）
   - 发送消息并查看各智能体的实时响应

## API 文档

### Agent管理API

#### 获取智能体列表
```http
GET /api/agents/
Authorization: Bearer <token>
```

#### 创建智能体
```http
POST /api/agents/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "智能体名称",
  "api_host": "https://jiutian.10086.cn",
  "api_key_env": "JIUTIAN_API_KEY_1",
  "enabled": true,
  "config": {
    "modelId": "jiutian-lan",
    "params": {
      "temperature": 0.8,
      "top_p": 0.95,
      "max_gen_len": 256
    },
    "klAssistId": "可选的知识助手ID",
    "timeout": 30,
    "max_retries": 1
  }
}
```

#### 更新智能体
```http
PUT /api/agents/{agent_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "更新的名称",
  "enabled": false
}
```

#### 切换智能体状态
```http
POST /api/agents/{agent_id}/toggle
Authorization: Bearer <token>
```

#### 删除智能体
```http
DELETE /api/agents/{agent_id}
Authorization: Bearer <token>
```

### 多智能体对话API

#### 发送多智能体消息
```http
POST /api/multi-chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "conv_id": "conversation-uuid",
  "user_id": "user-id",
  "message": "你好，请介绍一下自己",
  "agent_uids": ["agent-uid-1", "agent-uid-2"],
  "history": []
}
```

响应：
```json
{
  "conv_id": "conversation-uuid",
  "status": "accepted",
  "message": "Request accepted. Processing 2 agents."
}
```

### WebSocket事件

#### 连接和认证
```javascript
const socket = io('ws://localhost:8080/ws/socket.io', {
  auth: { token: 'your-jwt-token' }
});
```

#### 加入对话
```javascript
socket.emit('multi-agent-join', {
  auth: { token: 'your-jwt-token' },
  conv_id: 'conversation-uuid',
  agent_uids: ['agent-uid-1', 'agent-uid-2']
});
```

#### 接收智能体消息
```javascript
socket.on('multi-agent-message', (data) => {
  console.log('Agent message:', data);
  // data.agent_id - 智能体ID
  // data.data.type - 消息类型 (delta, complete, error, status)
  // data.data.content - 消息内容
});
```

#### 接收系统消息
```javascript
socket.on('multi-agent-system', (data) => {
  console.log('System message:', data);
  // data.message_type - 系统消息类型 (start, complete, error)
  // data.data.message - 系统消息内容
});
```

## 测试

### 运行单元测试
```bash
cd backend
python -m pytest test_agents.py -v
```

### 运行集成测试
```bash
python test/integration_test.py
```

### 运行负载测试
```bash
# 使用Docker
docker-compose -f docker-compose.multi-agent.yml --profile testing run k6

# 或者本地运行
k6 run test/k6/multi-agent-load-test.js
```

## 监控和日志

### Prometheus指标

系统提供以下监控指标：
- `multi_agent_requests_total` - 多智能体请求总数
- `multi_agent_request_duration_seconds` - 请求处理时间
- `websocket_connections_total` - WebSocket连接数
- `agent_response_time_seconds` - 智能体响应时间

### Grafana仪表板

启动监控服务后，访问 `http://localhost:3001` 查看Grafana仪表板：
- 用户名：`admin`
- 密码：`admin_password`

### 日志查看

```bash
# 查看后端日志
docker-compose -f docker-compose.multi-agent.yml logs -f backend

# 查看WebSocket日志
docker-compose -f docker-compose.multi-agent.yml logs -f backend | grep "multi-agent"

# 查看nginx访问日志
docker-compose -f docker-compose.multi-agent.yml logs -f nginx
```

## 故障排除

### 常见问题

1. **智能体无响应**
   - 检查API密钥是否正确配置
   - 验证九天API服务器连接
   - 查看后端日志中的错误信息

2. **WebSocket连接失败**
   - 确认Redis服务正常运行
   - 检查WEBSOCKET_REDIS_URL配置
   - 验证防火墙设置

3. **权限错误**
   - 确认用户角色设置正确
   - 检查JWT token是否有效
   - 验证RBAC配置

4. **数据库连接问题**
   - 检查DATABASE_URL配置
   - 确认PostgreSQL服务运行
   - 运行数据库迁移

### 调试模式

启用调试模式获取更详细的日志：

```bash
# 设置环境变量
export LOG_LEVEL=DEBUG

# 或在docker-compose中设置
environment:
  LOG_LEVEL: DEBUG
```

## 性能优化

### 建议的生产配置

1. **并发控制**
```bash
MAX_CONCURRENT_REQUESTS=20  # 根据服务器性能调整
```

2. **数据库连接池**
```bash
DATABASE_POOL_SIZE=10
DATABASE_POOL_MAX_OVERFLOW=20
```

3. **Redis配置**
```bash
WEBSOCKET_REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=100
```

4. **Nginx优化**
- 启用gzip压缩
- 配置适当的缓存策略
- 设置合理的超时时间

## 安全考虑

1. **API密钥管理**
   - 使用环境变量存储API密钥
   - 定期轮换API密钥
   - 不要在代码中硬编码密钥

2. **网络安全**
   - 使用HTTPS加密传输
   - 配置防火墙规则
   - 启用rate limiting

3. **访问控制**
   - 实施严格的RBAC
   - 定期审查用户权限
   - 监控异常访问

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用与Open WebUI相同的许可证。

## 联系方式

- 项目维护者：leecyang
- 协作者：lyyzka
- 邮箱：yangyangli0426@gmail.com

## 更新日志

### v1.0.0
- 初始版本发布
- 支持多智能体并发对话
- 集成九天大模型API
- 实现RBAC权限控制
- 提供完整的管理界面
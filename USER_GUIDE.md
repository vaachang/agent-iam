# Agent IAM 系统 — 用户指南

给 AI 发通行证：构建 Agent 身份与权限系统。

## 一分钟理解本系统

想象飞书里有三个 AI 助手：

| 助手 | 能做什么 | 不能做什么 |
|------|---------|-----------|
| 飞书文档助手 | 读写飞书文档、委托其他助手干活 | 不能直接查企业通讯录 |
| 企业数据助手 | 查通讯录、日历、多维表格、知识库 | 不能对外搜索 |
| 外部检索助手 | 搜索公开网页 | **绝对碰不了飞书企业数据** |

本系统就是给每个助手发一张"通行证"（Access Token），通行证上写明了它能做什么、不能做什么。每当助手之间相互委托干活时，必须先验通行证——合法的放行，非法的拦截，并且每一笔都记在审计日志里。

---

## 快速上手

### 前提条件

- Python 3.10+
- 已配置好的飞书应用（见[配置飞书应用](#配置飞书应用)）
- 可访问的 SearXNG 搜索引擎（用于外部检索Agent）
- 火山引擎 LLM API Key（用于报告增强，可选）

### 三步启动

```bash
# 1. 创建并激活虚拟环境
python3 -m venv venv && source venv/bin/activate

# 2. 进入项目目录并安装依赖
cd /path/to/fs-chongci
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的飞书 App ID / Secret 和 LLM API Key

# 4. 启动系统
bash start.sh
```

启动成功后会看到：

```
============================================
  System started successfully!
  IAM Server: http://127.0.0.1:8900
  Health:     http://127.0.0.1:8900/health
  API Docs:   http://127.0.0.1:8900/docs
============================================
```

### 停止系统

```bash
bash stop.sh
```

---

## 运行演示

系统提供了三个演示入口：

### 演示一：正常委托流程

```bash
python demo_normal.py
```

**场景**：用户张三让飞书文档助手生成一份调研报告。飞书文档助手拿到通行证后，委托企业数据Agent去查飞书里的多维表格、通讯录等数据，再委托外部检索Agent去搜索公开信息，最后将所有数据汇总成报告。

**预期结果**：全程绿灯，所有授权检查通过。

### 演示二：越权拦截流程

```bash
python demo_unauthorized.py
```

**场景**：外部检索Agent想越界——它试图委托企业数据Agent读取多维表格和通讯录数据。但它的通行证上根本没有这些权限。

**预期结果**：两次尝试均被拦截，返回 `CAPABILITY_MISMATCH` 错误码，审计日志记下两条 DENY 记录。

### 演示三：端到端全流程（含LLM增强 + 飞书文档写入）

```bash
python test_e2e.py
```

**场景**：完整跑通 User → 飞书文档助手 → 企业数据Agent + 外部检索Agent → LLM增强报告 → 写入飞书文档 的全链路。

**预期结果**：生成一份 LLM 增强的综合调研报告，写入飞书文档并提供文档 URL。

---

## 核心概念

### Agent 身份与认证

每个 Agent 有两个凭据：

- `agent_id`：唯一标识，如 `feishu_doc_agent`
- `agent_secret`：密钥，用于向 IAM 服务器证明"我就是我"

Agent 用这两个凭据向 IAM 服务器换取 Access Token（JWT 格式），之后所有跨 Agent 调用都携带这个 Token。

### Capability（能力声明）

Capability 采用 `resource:action` 格式，声明一个 Agent 能做什么：

```
feishu_bitable:read       → 能读多维表格
feishu_doc:write           → 能写飞书文档
external:search            → 能搜索公开网页
delegate:enterprise_data   → 能委托企业数据Agent
```

每个 Agent 注册时就定好了自己的 capability 清单，运行期间不能越界。

### 委托授权：用户权限 ∩ Agent 能力

当 Agent 代表用户（如张三）执行操作时，通行证上的有效权限是**两者权限的交集**：

```
有效权限 = 用户权限 ∩ Agent 能力
```

举例：
- 张三有权 `delegate:enterprise_data`，飞书文档助手有能力 `delegate:enterprise_data` → 有效权限包含此项
- 李四只有权 `external:search`，飞书文档助手没有 `external:search` → 有效权限为空，无法做任何事

### A2A 认证流程（Agent 到 Agent）

```
Agent A                  IAM Server                   Agent B
  │                         │                            │
  │ 1. 用 agent_id+secret  │                            │
  │    换 Access Token      │                            │
  │ ───────────────────────>│                            │
  │                         │                            │
  │ 2. 返回 JWT Token       │                            │
  │ <───────────────────────│                            │
  │                         │                            │
  │ 3. 携带 Token 调用      │                            │
  │    Agent B 的业务接口   │                            │
  │ ───────────────────────────────────────────────────>│
  │                         │                            │
  │                         │ 4. Agent B 拿 Token 找     │
  │                         │    IAM 验证权限            │
  │                         │ <──────────────────────────│
  │                         │                            │
  │                         │ 5. 返回验证结果            │
  │                         │    (通过/拒绝)             │
  │                         │ ──────────────────────────>│
  │                         │                            │
  │ 6. 拿到结果 / 被拒绝    │                            │
  │ <───────────────────────────────────────────────────│
```

### 信任链

```
用户张三
  │ 委托
  ▼
飞书文档助手 (Token: sub=feishu_doc_agent, delegated_user=user_zhangsan)
  │ 携带 Token 委托
  ▼
企业数据Agent (向IAM验证Token → 检查capability → 执行)
  │ 访问
  ▼
飞书 OpenAPI (通讯录、多维表格、知识库...)
```

---

## 配置文件说明

### .env 环境变量

```bash
# 飞书应用凭据（必填——否则飞书API调用会失败）
FEISHU_ENTERPRISE_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_ENTERPRISE_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_DOC_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_DOC_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# LLM 增强报告（可选——不填则用模板生成报告）
LLM_API_KEY=ark-xxxxxxxxxxxx
LLM_MODEL_ID=ep-xxxxxxxxxxxx
```

### config.py 中的 Agent 注册表

在 `config.py` 的 `AGENTS` 字典中定义 Agent：

```python
AGENTS = {
    "feishu_doc_agent": {
        "name": "飞书文档助手",
        "secret": "doc_agent_secret_key_2024",
        "capabilities": [
            "feishu_doc:read",
            "feishu_doc:write",
            "delegate:enterprise_data",
            "delegate:external_search",
        ],
    },
    # ... 更多 Agent
}
```

### config.py 中的用户权限表

在 `config.py` 的 `USERS` 字典中定义用户权限：

```python
USERS = {
    "user_zhangsan": {
        "name": "张三",
        "permissions": [
            "feishu_doc:read",
            "feishu_doc:write",
            "delegate:enterprise_data",
            "delegate:external_search",
        ],
    },
}
```

---

## API 使用指南

IAM 服务器运行在 `http://127.0.0.1:8900`，完整的 Swagger 文档在 `http://127.0.0.1:8900/docs`。

### 签发 Token

```bash
curl -X POST http://127.0.0.1:8900/token/issue \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "feishu_doc_agent",
    "agent_secret": "doc_agent_secret_key_2024",
    "delegated_user": "user_zhangsan"
  }'
```

成功响应：

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "agent_id": "feishu_doc_agent",
  "agent_name": "飞书文档助手",
  "effective_capabilities": [
    "feishu_doc:read",
    "feishu_doc:write",
    "delegate:enterprise_data",
    "delegate:external_search"
  ]
}
```

### 验证 Token 权限

```bash
curl -X POST http://127.0.0.1:8900/token/verify \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOi...",
    "required_capability": "feishu_bitable:read",
    "verifier_agent_id": "enterprise_data_agent"
  }'
```

权限通过时 `decision` 为 `"allow"`，被拒绝时为 `"deny"` 并附带原因。

### 查询审计日志

```bash
# 最近 20 条记录
curl "http://127.0.0.1:8900/audit/logs?limit=20"

# 只看被拒绝的记录
curl "http://127.0.0.1:8900/audit/logs?decision=deny&limit=20"

# 统计概览
curl "http://127.0.0.1:8900/audit/summary"

# 导出全部日志
curl "http://127.0.0.1:8900/audit/export"
```

### 撤销 Token

```bash
curl -X POST http://127.0.0.1:8900/token/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOi...",
    "reason": "Agent 出现异常行为"
  }'
```

撤销后该 Token 及从其派生的所有子 Token 将立即失效，后续验证返回 `TOKEN_REVOKED`。

### 动态权限提升（临时提权）

```bash
curl -X POST http://127.0.0.1:8900/token/elevate \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOi...",
    "requested_capability": "analysis:summarize",
    "justification": "紧急需要分析一份安全日志",
    "ttl_seconds": 300
  }'
```

提升后的 Token 有效期最多 5 分钟，到期自动失效。

### 查看已注册的 Agent

```bash
curl "http://127.0.0.1:8900/agents"
```

### 查看已注册的用户

```bash
curl "http://127.0.0.1:8900/users"
```

### 运行时动态注册新 Agent

```bash
curl -X POST http://127.0.0.1:8900/agents/register \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_custom_agent",
    "agent_name": "自定义Agent",
    "agent_secret": "my-secret-key",
    "capabilities": ["external:search"],
    "description": "通过运行时API注册的自定义Agent"
  }'
```

### 系统监控

```bash
curl "http://127.0.0.1:8900/health/metrics"
```

返回各项运行时指标（Token 签发数、验证数、拦截数等）和告警信息。

---

## 错误码速查

| 错误码 | 含义 | 常见原因 |
|--------|------|---------|
| `AUTH_FAILED` | 认证失败 | agent_id 不存在或 agent_secret 错误 |
| `TOKEN_INVALID` | Token 无效 | Token 被篡改、格式错误或已过期 |
| `TOKEN_REVOKED` | Token 已撤销 | 管理员手动撤销了该 Token |
| `CAPABILITY_MISMATCH` | 能力不匹配 | Agent 的通行证上没有请求的权限 |
| `DELEGATION_DENIED` | 委托被拒 | Agent 本有这个能力，但当前委托用户没有 |
| `TOKEN_BINDING_MISMATCH` | 绑定不匹配 | Token 被绑定的 Agent 之外的 Agent 使用（防盗用） |
| `RATE_LIMITED` | 频率超限 | 短时间内请求过多，请等待后再试 |

---

## 添加你自己的 Agent

需要两步：

**1. 在 `config.py` 中注册：**

```python
AGENTS = {
    # ... 已有 Agent
    "my_agent": {
        "name": "我的Agent",
        "secret": "my_agent_secret_123",
        "capabilities": ["my_service:read", "my_service:write"],
    },
}
```

**2. 创建 Agent 类，继承 `AgentBase`：**

```python
# agents/my_agent.py
from . import AgentBase

class MyAgent(AgentBase):
    def __init__(self):
        super().__init__("my_agent")

    def do_something(self, caller_token: str) -> dict:
        # 权限校验——自动向 IAM Server 验证
        self.check_and_enforce("my_service:read", caller_token)

        # 业务逻辑
        return {"status": "ok", "data": "..."}
```

`check_and_enforce()` 会自动完成：向 IAM Server 验证 Token → 检查 capability → 不通过则抛 `PermissionError` → 通过则返回验证结果。

---

## 审计日志说明

审计日志存储在项目根目录的 `audit.log` 文件中，JSONL 格式（每行一条 JSON）。

每条日志包含：

| 字段 | 说明 |
|------|------|
| `timestamp` | 事件时间（UTC） |
| `event` | 事件类型：`token_issue` / `token_verify` / `token_revoke` / `token_elevate` |
| `agent_id` | 发起操作的 Agent ID |
| `caller_agent_id` | Token 持有者 Agent ID（verify 事件） |
| `verifier_agent_id` | 验证方 Agent ID（verify 事件，即被调用方） |
| `delegated_user` | 委托用户 |
| `required_capability` | 请求的 capability |
| `decision` | `"allow"` 或 `"deny"` |
| `reason` | 决策原因 |
| `error_code` | 错误码（拒绝时） |
| `token_jti` | Token 唯一 ID（用于追踪） |

日志查询支持按 `decision` 筛选，方便快速定位所有被拦截的请求。

---

## 配置飞书应用

### 企业数据Agent 的应用

1. 打开 [飞书开放平台](https://open.feishu.cn)
2. 创建企业自建应用，获取 App ID 和 App Secret
3. 在"权限管理"中添加以下权限：
   - 通讯录：`contact:contact:readonly`
   - 日历：`calendar:calendar:readonly`
   - 多维表格：`bitable:app`
   - 知识库：`wiki:wiki:readonly`
4. 发布应用并通过管理员审核

### 飞书文档助手的应用

1. 同上创建第二个自建应用
2. 添加权限：
   - 云文档：`docx:document`（读写）
   - 多维表格：`bitable:app`（读取用）
3. 发布并审核

---

## 项目文件结构

```
fs-chongci/
├── iam_server.py              # IAM 授权服务器（FastAPI）
├── config.py                  # Agent/用户/能力注册表 + 系统配置
├── agents/
│   ├── __init__.py            # Agent 基类（封装 Token 签发/验证/审计）
│   ├── feishu_doc_agent.py    # 飞书文档助手（编排 + 飞书 Doc API）
│   ├── enterprise_data_agent.py  # 企业数据 Agent（飞书通讯录/日历/多维表格/知识库）
│   ├── external_search_agent.py  # 外部检索 Agent（SearXNG）
│   └── ai_analyst_agent.py   # AI 分析 Agent（火山引擎 LLM，异构接入示例）
├── demo_normal.py             # 演示一：正常委托流程
├── demo_unauthorized.py       # 演示二：越权拦截流程
├── test_e2e.py                # 演示三：端到端全流程
├── start.sh / stop.sh         # 启动/停止脚本
├── .env                       # 飞书 App ID/Secret + LLM Key
├── audit.log                  # 审计日志
└── README.md                  # 技术概述
```

---

## 常见问题

**Q: 启动时报 "port 8900 already in use"？**

```bash
bash stop.sh   # 先停掉旧进程
bash start.sh  # 再启动
```

**Q: 飞书数据查询返回错误？**

检查 `.env` 中的飞书 App ID 和 App Secret 是否正确，以及应用是否已获得所需权限并完成发布。

**Q: 外部搜索返回 0 条结果？**

确认 SearXNG 服务在 `http://192.168.1.248:18935` 可访问。如不可访问，Agent 会优雅降级返回空结果。

**Q: LLM 增强报告失败？**

LLM 是可选功能。如果失败，系统自动回退到模板生成报告，不影响主流程。

**Q: 如何查看 Swagger API 文档？**

启动系统后访问 http://127.0.0.1:8900/docs

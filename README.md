# Agent IAM System - AI Agent 身份与权限系统

给 AI 发通行证：构建 Agent 身份与权限系统。

## 项目概述

本项目实现了一个面向 AI Agent 的通用身份与权限管理系统（IAM），解决多 Agent 协作场景下的身份混淆、权限滥用、信任链缺失等安全问题。

核心功能：
- **Agent 身份认证**：基于 JWT 的 Access Token 签发与验证，agent_id + agent_secret 双因子认证
- **细粒度权限管控**：基于能力声明（Capability）的授权模型，resource:action 格式
- **委托授权**：用户权限 ∩ Agent能力 的有效权限交集计算，最小权限原则
- **越权拦截**：实时检查并拒绝超出授权范围的请求，返回结构化错误码
- **审计追溯**：记录每一次授权决策的完整上下文，含调用链（caller → verifier）追踪

## 系统架构

```
User
  │
  ▼
┌─────────────────────────────────────────────────┐
│           飞书文档助手 Agent                       │
│  Capabilities: feishu_doc:read, feishu_doc:write│
│                delegate:enterprise_data          │
│                delegate:external_search          │
└──────┬──────────────────────────┬───────────────┘
       │ delegate                  │ delegate
       ▼                          ▼
┌──────────────┐          ┌──────────────────┐
│ 企业数据Agent │          │ 外部检索Agent     │
│              │          │                  │
│ contacts:read│          │ external:search   │
│ calendar:read│          │                  │
│ bitable:read │          │ (无权访问飞书数据) │
│ kb:read      │          │                  │
└──────┬───────┘          └────────┬─────────┘
       │                           │
       ▼                           ▼
┌──────────────┐          ┌──────────────────┐
│ 飞书 OpenAPI │          │ SearXNG 搜索引擎  │
│ (企业内部数据)│          │ (公开网页信息)    │
└──────────────┘          └──────────────────┘
       │                           │
       ▼                           ▼
┌─────────────────────────────────────────────────┐
│              IAM Authorization Server            │
│  - Token 签发 (POST /token/issue)                │
│  - Token 验证 (POST /token/verify)               │
│  - 审计日志 (GET  /audit/logs)                   │
└─────────────────────────────────────────────────┘
```

### A2A 认证流程（类似 OAuth 2.0）

```
Agent A                    IAM Server                   Agent B
  │                           │                            │
  │  1. POST /token/issue     │                            │
  │  (agent_id, secret, user) │                            │
  │ ─────────────────────────>│                            │
  │                           │                            │
  │  2. Access Token (JWT)    │                            │
  │ <─────────────────────────│                            │
  │                           │                            │
  │  3. Call Agent B          │                            │
  │  (Bearer token, operation)│                            │
  │ ──────────────────────────────────────────────────────>│
  │                           │                            │
  │                           │  4. POST /token/verify     │
  │                           │  (token, required_cap)     │
  │                           │ <──────────────────────────│
  │                           │                            │
  │                           │  5. Verify result          │
  │                           │ ──────────────────────────>│
  │                           │                            │
  │  6. Result / Denied       │                            │
  │ <──────────────────────────────────────────────────────│
```

## Access Token 设计

基于 JWT (JSON Web Token)，包含以下字段：

| 字段 | 说明 |
|------|------|
| `sub` | Agent 唯一标识（agent_id） |
| `agent_name` | Agent 名称 |
| `capabilities` | Agent 拥有的能力列表 |
| `delegated_user` | 委托的用户身份（用户权限与Agent能力的交集） |
| `iat` | 签发时间 |
| `exp` | 过期时间 |
| `jti` | Token 唯一ID（用于审计追溯和撤销） |
| `iss` | 签发者（agent-iam-system） |

### Token 示例
```json
{
  "sub": "feishu_doc_agent",
  "agent_name": "飞书文档助手",
  "capabilities": ["feishu_doc:read", "feishu_doc:write",
                   "delegate:enterprise_data", "delegate:external_search"],
  "delegated_user": "user_zhangsan",
  "iat": 1717000000,
  "exp": 1717003600,
  "jti": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "iss": "agent-iam-system"
}
```

## 用户权限模型

系统定义用户权限集，当 Agent 代表用户执行操作时，Token 中的有效权限为：

**有效权限 = 用户权限 ∩ Agent 能力**

| 用户 | 权限 |
|------|------|
| user_zhangsan (张三) | `feishu_doc:read`, `feishu_doc:write`, `delegate:enterprise_data`, `delegate:external_search` |
| user_lisi (李四) | `external:search` |
| anonymous | (无) |

示例：user_lisi (仅 `external:search`) + feishu_doc_agent (无 `external:search`) → 有效权限为空集，Token 无法用于任何委托操作。

## Agent 能力声明 (Capability Statement)

| Agent | Capabilities | 说明 |
|-------|-------------|------|
| 飞书文档助手 | `feishu_doc:read`, `feishu_doc:write`, `delegate:enterprise_data`, `delegate:external_search` | 可读写文档，可委托其他Agent |
| 企业数据Agent | `feishu_contacts:read`, `feishu_calendar:read`, `feishu_bitable:read`, `feishu_knowledge_base:read` | 唯一可访问飞书企业数据 |
| 外部检索Agent | `external:search` | 仅可搜索公开网页，无权访问飞书数据 |

## 审计日志字段

| 字段 | 说明 |
|------|------|
| `timestamp` | 事件时间（UTC ISO 8601） |
| `event` | 事件类型（token_issue, token_verify） |
| `agent_id` | 发起操作的 Agent ID |
| `agent_name` | Agent 名称 |
| `delegated_user` | 委托用户 |
| `required_capability` | 请求的能力 |
| `token_capabilities` | Token 实际拥有的能力列表 |
| `token_jti` | Token 唯一标识 |
| `decision` | 授权决策（allow / deny） |
| `reason` | 决策原因 |

## 快速开始

### 环境要求
- Python 3.10+
- 依赖: fastapi, uvicorn, pyjwt, httpx, pydantic

### 启动系统

```bash
# 1. 激活虚拟环境（如有）
python3 -m venv venv && source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 IAM 授权服务
bash start.sh
```

### 运行演示

```bash
# 统一交互式演示（推荐）
python demo.py

# 或分别运行独立演示
python demo_normal.py        # 演示一：正常委托流程
python demo_unauthorized.py  # 演示二：越权拦截流程
```

### 停止系统

```bash
bash stop.sh
```

## API 接口定义

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/health/metrics` | 运行时指标 + 告警 |
| POST | `/token/issue` | 签发 Access Token（含有效权限交集、范围限制、Token 绑定） |
| POST | `/token/verify` | 验证 Token 并检查能力（支持 silent 模式） |
| POST | `/token/refresh` | 刷新 Token（无需重新认证） |
| POST | `/token/elevate` | 动态授权：临时提升权限（TTL≤300s） |
| POST | `/token/revoke` | 撤销 Token（级联撤销所有派生 Token） |
| POST | `/token/revoke-by-jti` | 按 JTI 撤销 Token |
| GET | `/token/blacklist` | 查看当前撤销的 Token |
| GET | `/audit/logs` | 查询审计日志（支持 decision 筛选） |
| GET | `/audit/summary` | 审计统计摘要（按 Agent / 事件类型） |
| GET | `/audit/export` | 导出完整审计日志（JSON） |
| GET | `/agents` | 列出所有注册的 Agent |
| POST | `/agents/register` | 运行时注册新 Agent |
| DELETE | `/agents/{agent_id}` | 运行时注销 Agent |
| GET | `/users` | 列出所有注册的用户及其权限 |

### 错误码

| 错误码 | 说明 |
|--------|------|
| `AUTH_FAILED` | Agent 认证失败（密钥错误） |
| `TOKEN_INVALID` | Token 无效或已过期 |
| `TOKEN_REVOKED` | Token 已被撤销 |
| `CAPABILITY_MISMATCH` | Token 不含请求的能力 |
| `DELEGATION_DENIED` | 委托授权被拒绝（用户无此权限） |
| `TOKEN_BINDING_MISMATCH` | Token 绑定来源不匹配（防盗用） |
| `RATE_LIMITED` | 请求频率超限 |

### 委托范围限制

Token 签发时支持 `delegated_scopes` 参数，可进一步缩小有效权限范围：

```json
{
  "agent_id": "feishu_doc_agent",
  "agent_secret": "...",
  "delegated_user": "user_zhangsan",
  "delegated_scopes": ["feishu_doc:read"]
}
```

### 级联撤销

撤销 Token 时会自动递归撤销所有从该 Token 动态提升（elevate）派生的子 Token，确保完整的权限回收。

### 速率限制

`/token/issue` 端点内置滑动窗口速率限制（默认 60 次/分钟），可通过环境变量 `RATE_LIMIT_MAX` 和 `RATE_LIMIT_WINDOW` 配置。


## 项目结构

```
fs-chongci/
├── README.md                  # 本文件
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量模板
├── config.py                  # 配置 (Agent/User/Capability 注册)
├── iam_server.py              # IAM 授权服务器 (v2.1.0)
├── start.sh                   # 启动脚本
├── stop.sh                    # 停止脚本
├── demo.py                    # 统一交互式演示 (推荐)
├── demo_normal.py             # 正常委托演示
├── demo_unauthorized.py       # 越权拦截演示
├── test_requirements.py       # 需求达标测试 (85 项)
├── test_bugs.py               # 边界测试 (65 项)
├── test_e2e.py                # 端到端测试
├── test_final.py              # 最终验证
├── agents/
│   ├── __init__.py            # Agent 基类 (IAM 交互封装)
│   ├── feishu_doc_agent.py    # 飞书文档助手 Agent
│   ├── enterprise_data_agent.py  # 企业数据 Agent
│   ├── external_search_agent.py  # 外部检索 Agent
│   └── ai_analyst_agent.py   # AI 分析 Agent (异构接入)
└── docs/
    └── design.md              # 技术方案设计文档
```

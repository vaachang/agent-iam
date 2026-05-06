#!/usr/bin/env python3
"""Comprehensive runtime test suite for Agent IAM System."""
import json
import os
import httpx
import sys
import time

IAM = "http://127.0.0.1:8900"
PASS, FAIL = 0, 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")

# ============================================================
print("=" * 60)
print("测试 1: 系统启动与基础端点")
print("=" * 60)

resp = httpx.get(f"{IAM}/health")
check("GET /health 返回200", resp.status_code == 200)
check("health 含 status=ok", resp.json().get("status") == "ok")

resp = httpx.get(f"{IAM}/agents")
data = resp.json()
check("GET /agents 返回200", resp.status_code == 200)
check(">= 4个Agent已注册", len(data) >= 4, f"got {len(data)}")
check("feishu_doc_agent 已注册", "feishu_doc_agent" in data)
check("enterprise_data_agent 已注册", "enterprise_data_agent" in data)
check("external_search_agent 已注册", "external_search_agent" in data)
check("ai_analyst_agent 已注册(异构)", "ai_analyst_agent" in data)

resp = httpx.get(f"{IAM}/users")
data = resp.json()
check("GET /users 返回200", resp.status_code == 200)

resp = httpx.get(f"{IAM}/docs")
check("API 文档 /docs 可访问", resp.status_code == 200)

print(f"  测试1: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T1_PASS, T1_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 2: Token 签发与身份认证")
print("=" * 60)

# 2a: Correct credentials → success
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent",
    "agent_secret": "doc_agent_secret_key_2024",
    "delegated_user": "user_zhangsan",
})
check("正确凭据签发Token (200)", resp.status_code == 200, f"got {resp.status_code}")
token_data = resp.json()
check("返回 access_token", bool(token_data.get("access_token")))
check("token_type=Bearer", token_data.get("token_type") == "Bearer")
check("expires_in > 0", token_data.get("expires_in", 0) > 0)
check("返回 agent_id", token_data.get("agent_id") == "feishu_doc_agent")
check("返回 agent_name", token_data.get("agent_name") == "飞书文档助手")
check("返回 effective_capabilities", isinstance(token_data.get("effective_capabilities"), list))
DOC_TOKEN = token_data["access_token"]

# 2b: Wrong credentials → 401
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent",
    "agent_secret": "WRONG_SECRET",
    "delegated_user": "user_zhangsan",
})
check("错误凭据返回401", resp.status_code == 401)
check("错误凭据含 error_code", bool(resp.json().get("detail", {}).get("error_code")))

# 2c: Unknown agent → 401
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "nonexistent_agent",
    "agent_secret": "whatever",
    "delegated_user": "user_zhangsan",
})
check("未知Agent返回401", resp.status_code == 401)

# 2d: Effective capabilities = intersection
# feishu_doc_agent caps: [feishu_doc:read, feishu_doc:write, delegate:enterprise_data, delegate:external_search]
# user_lisi perms: [external:search]
# intersection should be empty
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent",
    "agent_secret": "doc_agent_secret_key_2024",
    "delegated_user": "user_lisi",
})
check("用户权限∩Agent能力=交集计算", resp.status_code == 200)
eff = resp.json().get("effective_capabilities", [])
check("lisi+doc_agent 交集为空", eff == [], f"expected empty, got {eff}")

print(f"  测试2: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T2_PASS, T2_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 3: Token 验证与权限校验")
print("=" * 60)

# 3a: Verify valid token with matching capability → allow
resp = httpx.post(f"{IAM}/token/verify", json={
    "token": DOC_TOKEN,
    "required_capability": "feishu_doc:read",
    "verifier_agent_id": "enterprise_data_agent",
})
check("token验证(匹配)返回200", resp.status_code == 200)
result = resp.json()
check("decision=allow", result.get("decision") == "allow")
check("valid=true", result.get("valid") == True)
check("返回 agent_id", result.get("agent_id") == "feishu_doc_agent")
check("返回 capabilities", isinstance(result.get("capabilities"), list))

# 3b: Verify valid token with non-matching capability → deny
resp = httpx.post(f"{IAM}/token/verify", json={
    "token": DOC_TOKEN,
    "required_capability": "feishu_bitable:read",
    "verifier_agent_id": "enterprise_data_agent",
})
check("token验证(不匹配)返回200", resp.status_code == 200)
result = resp.json()
check("decision=deny", result.get("decision") == "deny", f"got {result.get('decision')}")
check("含 error_code", bool(result.get("error_code")))
check("含 reason", bool(result.get("reason")))

# 3c: Verify invalid token → deny
resp = httpx.post(f"{IAM}/token/verify", json={
    "token": "invalid.token.here",
    "required_capability": "feishu_doc:read",
})
check("无效token返回200(deny)", resp.status_code == 200)
result = resp.json()
check("无效token decision=deny", result.get("decision") == "deny")
check("无效token valid=false", result.get("valid") == False)

# 3d: Token from lisi (only external:search) trying feishu_doc → DELEGATION_DENIED
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent",
    "agent_secret": "doc_agent_secret_key_2024",
    "delegated_user": "user_lisi",
})
check("lisi+doc_agent token签发成功", resp.status_code == 200)
LISI_TOKEN = resp.json()["access_token"]

resp = httpx.post(f"{IAM}/token/verify", json={
    "token": LISI_TOKEN,
    "required_capability": "feishu_doc:read",
    "verifier_agent_id": "test",
})
result = resp.json()
check("lisi token被拒 decision=deny", result.get("decision") == "deny")
check("错误码=DELEGATION_DENIED", result.get("error_code") == "DELEGATION_DENIED",
     f"got {result.get('error_code')}, reason={result.get('reason')}")

print(f"  测试3: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T3_PASS, T3_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 4: 审计日志完整性")
print("=" * 60)

# Wait a moment for async logging
time.sleep(0.5)

resp = httpx.get(f"{IAM}/audit/logs", params={"limit": 50})
check("GET /audit/logs 返回200", resp.status_code == 200)
logs = resp.json().get("logs", [])
check("审计日志非空", len(logs) > 0, f"got {len(logs)} entries")

# Check event types
events = set(e.get("event") for e in logs)
check("含 token_issue 事件", "token_issue" in events)
check("含 token_verify 事件", "token_verify" in events)

# Check decisions
decisions = set(e.get("decision") for e in logs)
check("含 allow 决策", "allow" in decisions)
check("含 deny 决策", "deny" in decisions)

# Check fields present
sample = logs[0]
required_fields = ["timestamp", "event", "decision", "reason"]
for f in required_fields:
    check(f"日志含字段 {f}", f in sample, f"missing field: {f}")

# Summary
resp = httpx.get(f"{IAM}/audit/summary")
check("GET /audit/summary 返回200", resp.status_code == 200)
stats = resp.json()
check("summary 有 by_agent 统计", isinstance(stats.get("by_agent"), dict))

# Export
resp = httpx.get(f"{IAM}/audit/export")
check("GET /audit/export 返回200", resp.status_code == 200)
check("export 含 exported_at", bool(resp.json().get("exported_at")))

# Filter by decision
resp = httpx.get(f"{IAM}/audit/logs", params={"limit": 20, "decision": "deny"})
deny_logs = resp.json().get("logs", [])
check("按decision=deny筛选", all(e.get("decision") == "deny" for e in deny_logs),
     f"got {len(deny_logs)} entries")

print(f"  测试4: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T4_PASS, T4_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 5: Agent 委托与越权拦截 (核心场景)")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.enterprise_data_agent import EnterpriseDataAgent
from agents.external_search_agent import ExternalSearchAgent
from agents.ai_analyst_agent import AIAnalystAgent

ea = EnterpriseDataAgent()
exa = ExternalSearchAgent()
aia = AIAnalystAgent()

# 5a: external_search_agent gets token for user_lisi
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "external_search_agent",
    "agent_secret": "external_agent_secret_key_2024",
    "delegated_user": "user_lisi",
})
check("外部检索Agent获取token(200)", resp.status_code == 200)
EXT_TOKEN = resp.json()["access_token"]
ext_caps = resp.json().get("effective_capabilities", [])
check("外部检索Agent有效权限=[external:search]",
      ext_caps == ["external:search"], f"got {ext_caps}")

# 5b: External agent tries to read bitable → MUST be denied
print()
print("  --- 越权拦截测试 ---")
try:
    result = ea.list_bitable_apps(EXT_TOKEN)
    check("外部Agent访问多维表格被拦截", False, f"UNEXPECTED ALLOW: {result}")
except PermissionError as e:
    check("外部Agent访问多维表格被拦截", "CAPABILITY_MISMATCH" in str(e), str(e))

# 5c: External agent tries to read contacts → MUST be denied
try:
    result = ea.list_users(EXT_TOKEN)
    check("外部Agent访问通讯录被拦截", False, f"UNEXPECTED ALLOW: {result}")
except PermissionError as e:
    check("外部Agent访问通讯录被拦截", True, str(e)[:80])

# 5d: External agent's own capability still works
try:
    result = exa.search("test", EXT_TOKEN)
    check("外部Agent自身搜索正常", result.get("status") in ("ok", "error"),
         f"got {result}")
except PermissionError as e:
    check("外部Agent自身搜索正常", False, f"自身权限被误伤: {e}")

# 5e: AI Analyst heterogeneous agent test (use user_zhangsan who has full analysis perms)
# First add analysis permissions to user_zhangsan for this test
print()
print("  --- 异构Agent测试 ---")
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "ai_analyst_agent",
    "agent_secret": "ai_analyst_secret_key_2024",
    "delegated_user": "user_zhangsan",
})
check("AI分析Agent获取token(200)", resp.status_code == 200)
AI_TOKEN = resp.json()["access_token"]

try:
    result = aia.classify("Agent IAM系统用于管理AI Agent的身份和权限",
                          ["技术架构", "产品介绍", "安全系统"], AI_TOKEN)
    check("异构Agent classify权限验证通过", result.get("status") == "ok", str(result)[:100])
except PermissionError as e:
    check("异构Agent classify权限验证通过", False, f"IAM层拒绝: {e}")
except RuntimeError as e:
    if "LLM not configured" in str(e):
        check("异构Agent classify IAM层通过(LLM未配置)", True)
    else:
        check("异构Agent classify IAM层通过", False, str(e))

try:
    result = aia.summarize("IAM系统是用于管理AI Agent身份权限的系统，支持多Agent协作", AI_TOKEN)
    check("异构Agent summarize权限验证通过", result.get("status") == "ok", str(result)[:100])
except PermissionError as e:
    check("异构Agent summarize权限验证通过", False, f"IAM层拒绝: {e}")
except RuntimeError as e:
    if "LLM not configured" in str(e):
        check("异构Agent summarize IAM层通过(LLM未配置)", True)
    else:
        check("异构Agent summarize IAM层通过", False, str(e))

print(f"  测试5: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T5_PASS, T5_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 6: 结构化错误码验证")
print("=" * 60)

# Verify all error codes are present in config and used
from config import ERROR_CODES
expected_codes = ["AUTH_FAILED", "TOKEN_INVALID", "TOKEN_EXPIRED", "CAPABILITY_MISMATCH", "DELEGATION_DENIED"]
for code in expected_codes:
    check(f"错误码 {code} 已定义", code in ERROR_CODES)

# Verify actual API error responses contain error codes
# Auth failed
resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent", "agent_secret": "bad", "delegated_user": "anonymous",
})
detail = resp.json().get("detail", {})
check("AUTH_FAILED 在响应中", detail.get("error_code") == "AUTH_FAILED")

# Token invalid
resp = httpx.post(f"{IAM}/token/verify", json={
    "token": "garbage", "required_capability": "x",
})
check("TOKEN_INVALID 在响应中", resp.json().get("error_code") == "TOKEN_INVALID")

print(f"  测试6: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T6_PASS, T6_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 7: Agent 能力声明与 Capability 模型")
print("=" * 60)

resp = httpx.get(f"{IAM}/agents")
agents = resp.json()

# Check capability format is resource:action
for agent_id, info in agents.items():
    caps = info.get("capabilities", [])
    for cap in caps:
        check(f"{agent_id}: {cap} 格式为 resource:action",
              ":" in cap, f"bad format: {cap}")

# Enterprise data agent must have bitable:read
ea_info = agents.get("enterprise_data_agent", {})
check("企业数据Agent有 feishu_bitable:read",
      "feishu_bitable:read" in ea_info.get("capabilities", []))
check("企业数据Agent有 feishu_contacts:read",
      "feishu_contacts:read" in ea_info.get("capabilities", []))

# External search agent must NOT have feishu_* capabilities
exa_info = agents.get("external_search_agent", {})
for cap in exa_info.get("capabilities", []):
    check(f"外部检索Agent不应含飞书权限({cap})",
          not cap.startswith("feishu_"),
          f"found {cap}")

# AI analyst has analysis:* caps
aia_info = agents.get("ai_analyst_agent", {})
check("AI分析Agent 有 analysis:summarize",
      "analysis:summarize" in aia_info.get("capabilities", []))
check("AI分析Agent 有 analysis:classify",
      "analysis:classify" in aia_info.get("capabilities", []))

print(f"  测试7: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T7_PASS, T7_FAIL = PASS, FAIL
PASS, FAIL = 0, 0

# ============================================================
print()
print("=" * 60)
print("测试 8: silent 模式验证 (不产生审计日志)")
print("=" * 60)

resp_before = httpx.get(f"{IAM}/audit/summary")
before_total = resp_before.json().get("total", 0)

# silent=true should skip audit
httpx.post(f"{IAM}/token/verify", json={
    "token": DOC_TOKEN,
    "required_capability": "nonexistent:cap",
    "silent": True,
})

time.sleep(0.3)
resp_after = httpx.get(f"{IAM}/audit/summary")
after_total = resp_after.json().get("total", 0)
check("silent=true 不产生审计日志", before_total == after_total,
      f"before={before_total}, after={after_total}")

print(f"  测试8: {PASS}通过 / {FAIL}失败 / {PASS+FAIL}总计")
T8_PASS, T8_FAIL = PASS, FAIL

# ============================================================
print()
print("=" * 60)
print("  总 结")
print("=" * 60)
total_pass = T1_PASS+T2_PASS+T3_PASS+T4_PASS+T5_PASS+T6_PASS+T7_PASS+T8_PASS
total_fail = T1_FAIL+T2_FAIL+T3_FAIL+T4_FAIL+T5_FAIL+T6_FAIL+T7_FAIL+T8_FAIL
print(f"  总计: {total_pass} 通过 / {total_fail} 失败 / {total_pass+total_fail} 项")
if total_fail == 0:
    print("  结果: 所有测试通过!")
else:
    print(f"  结果: {total_fail} 项失败，需要修复")

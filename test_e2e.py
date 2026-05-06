#!/usr/bin/env python3
"""端到端测试：完整跑一遍 feishu_doc_agent 的 execute_report_workflow 流程。"""
import json, os, sys, time, httpx

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

# Load .env
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key] = val

IAM = "http://127.0.0.1:8900"
SEP = "=" * 64
SEP2 = "-" * 48

# ====================================================================
print(SEP)
print("  端到端测试: User → 飞书文档助手 → 企业数据Agent + 外部检索Agent")
print("  场景: 用户张三委托飞书文档助手生成「AI Agent IAM 综合调研报告」")
print(SEP)

# Step 1 — 获取 IAM Token
print(f"\n{SEP2}")
print("  Step 1/5: 飞书文档助手获取 IAM Access Token")
print(f"  委托用户: user_zhangsan (张三)")
print(f"{SEP2}")

resp = httpx.post(f"{IAM}/token/issue", json={
    "agent_id": "feishu_doc_agent",
    "agent_secret": "doc_agent_secret_key_2024",
    "delegated_user": "user_zhangsan",
})
if resp.status_code != 200:
    print(f"  [FAIL] Token 签发失败: {resp.text}")
    sys.exit(1)
token_data = resp.json()
token = token_data["access_token"]
print(f"  Token 签发成功")
print(f"  有效权限: {token_data['effective_capabilities']}")
print(f"  Token JTI: {token_data.get('access_token', '')[:50]}...")

# Step 2 — 委托企业数据Agent 查询真实飞书数据
print(f"\n{SEP2}")
print("  Step 2/5: 委托企业数据Agent 查询飞书企业数据")
print(f"  验证 capability: delegate:enterprise_data")
print(f"{SEP2}")

from agents.enterprise_data_agent import EnterpriseDataAgent
ea = EnterpriseDataAgent()

enterprise_data = {"status": "error", "data": {}}
try:
    enterprise_data = ea.get_all_enterprise_data(token)
    print(f"  IAM 验证通过")
    if enterprise_data.get("status") == "ok":
        print(f"  飞书数据查询结果:")
        for category, result in enterprise_data.get("data", {}).items():
            if isinstance(result, dict):
                status = result.get("status", "?")
                count = result.get("count", "?")
                print(f"    - {category}: status={status}, count={count}")
            else:
                print(f"    - {category}: {result}")
except PermissionError as e:
    print(f"  [IAM拦截] 权限不足: {e}")
    enterprise_data = {"error": str(e)}

# Step 3 — 委托外部检索Agent 搜索公开信息
print(f"\n{SEP2}")
print("  Step 3/5: 委托外部检索Agent 搜索公开信息")
print(f"  验证 capability: delegate:external_search")
print(f"  搜索关键词: AI Agent 身份与权限管理")
print(f"{SEP2}")

from agents.external_search_agent import ExternalSearchAgent
exa = ExternalSearchAgent()

search_results = {"status": "error", "results": []}
try:
    search_results = exa.search("AI Agent 身份与权限管理", token)
    print(f"  IAM 验证通过")
    if search_results.get("status") == "ok":
        count = search_results.get("count", 0)
        print(f"  搜索结果: {count} 条")
        for r in search_results.get("results", [])[:5]:
            print(f"    - {r.get('title', 'N/A')[:80]}")
    elif search_results.get("note"):
        print(f"  注意: {search_results.get('note')}")
    else:
        print(f"  搜索异常: {search_results.get('detail', 'unknown')}")
except PermissionError as e:
    print(f"  [IAM拦截] 权限不足: {e}")
    search_results = {"error": str(e)}

# Step 4 — LLM 增强报告编译
print(f"\n{SEP2}")
print("  Step 4/5: LLM 增强编译报告")
print(f"  引擎: 火山引擎 LLM (ep-20260422180415-nk596)")
print(f"{SEP2}")

from agents.feishu_doc_agent import FeishuDocAgent
doc_agent = FeishuDocAgent()

report = doc_agent._compile_report_enhanced(
    "AI Agent 身份与权限管理系统 — 企业落地综合调研",
    enterprise_data,
    search_results,
)
llm_used = getattr(doc_agent, "_llm_used", False)
print(f"  报告类型: {'LLM 增强' if llm_used else '模板生成'}")
print(f"  报告长度: {len(report)} 字符")
print(f"\n  --- 报告预览 (前 600 字符) ---")
print(report[:600])

# Step 5 — 写入飞书文档
print(f"\n{SEP2}")
print("  Step 5/5: 将报告写入飞书文档")
print(f"{SEP2}")

doc_result = {"status": "error", "detail": "not executed"}
try:
    doc_result = doc_agent.create_doc(
        title="综合报告: AI Agent IAM 企业落地调研",
        content=report,
    )
    if doc_result.get("status") == "ok":
        print(f"  文档创建成功!")
        print(f"  URL: {doc_result.get('document_url')}")
        print(f"  写入块数: {doc_result.get('blocks_written', 0)}")
        print(f"  Document ID: {doc_result.get('document_id')}")
    else:
        print(f"  异常: {doc_result}")
except Exception as e:
    print(f"  [FAIL] 文档写入失败: {e}")
    doc_result = {"status": "error", "detail": str(e)}

# Step 6 — 审计日志查看
print(f"\n{SEP2}")
print("  Step 6: 审计日志回顾")
print(f"{SEP2}")

resp = httpx.get(f"{IAM}/audit/summary")
if resp.status_code == 200:
    stats = resp.json()
    print(f"  总事件: {stats['total']} | ALLOW: {stats['allow']} | DENY: {stats['deny']}")
    print(f"  按 Agent 统计:")
    for agent, counts in stats.get("by_agent", {}).items():
        print(f"    {agent}: {counts}")

resp = httpx.get(f"{IAM}/audit/logs", params={"limit": 10})
if resp.status_code == 200:
    print(f"\n  最近 10 条审计记录:")
    for entry in resp.json().get("logs", []):
        mark = "[ALLOW]" if entry.get("decision") == "allow" else "[DENY]"
        event = entry.get("event", "?")
        caller = entry.get("caller_agent_id") or entry.get("agent_id", "?")
        cap = entry.get("required_capability", "")
        reason = entry.get("reason", "")
        error = entry.get("error_code", "")
        err = f" [{error}]" if error else ""
        cap_str = f" cap={cap}" if cap else ""
        print(f"  {mark} {event} | agent={caller}{cap_str} | {reason}{err}")

# ====================================================================
print(f"\n{SEP}")
print("  端到端测试完成")
print(SEP)
print(f"  飞书文档URL: {doc_result.get('document_url', 'N/A')}")
print(f"  报告类型: {'LLM增强' if llm_used else '模板'} | 长度: {len(report)} 字符")
print(f"  企业数据: {'成功' if enterprise_data.get('status') == 'ok' else '部分/失败'}")
print(f"  外部搜索: {'成功' if search_results.get('status') == 'ok' else '部分/失败'}")
print(f"  文档写入: {'成功' if doc_result.get('status') == 'ok' else '失败'}")

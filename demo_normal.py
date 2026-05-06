#!/usr/bin/env python3
"""
Demo: Normal Delegation Flow

飞书文档助手 → 企业数据Agent: successfully delegates data queries,
then compiles report and writes to Feishu doc.

All authorization checks pass and are logged.
"""

import json
import sys
import time
import httpx


def check_server():
    """Wait for IAM server to be ready."""
    for _ in range(30):
        try:
            resp = httpx.get("http://127.0.0.1:8900/health", timeout=2)
            if resp.status_code == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def main():
    print("=" * 60)
    print("  演示一：正常委托流程")
    print("  飞书文档助手 → 企业数据Agent → 外部检索Agent")
    print("=" * 60)
    print()

    if not check_server():
        print("ERROR: IAM server is not running. Start it first with:")
        print("  python iam_server.py &")
        sys.exit(1)

    print("[OK] IAM Server is running\n")

    # Import agents (from project root)
    sys.path.insert(0, ".")
    from agents.feishu_doc_agent import FeishuDocAgent

    doc_agent = FeishuDocAgent()
    print(f"[INFO] 飞书文档助手已就绪")
    print(f"       Capabilities: {doc_agent.capabilities}")
    print()

    # --- Step 1: 飞书文档助手 gets token ---
    print("--- Step 1: 获取 Access Token ---")
    print("     计算有效权限: 用户权限 ∩ Agent能力")
    try:
        token = doc_agent.get_token(delegated_user="user_zhangsan")
        print(f"[OK] Token issued for {doc_agent.agent_name}")
        print(f"     Delegated user: user_zhangsan")
        print(f"     有效权限: {doc_agent.effective_capabilities}")
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
    print()

    enterprise_data = {"status": "error", "data": {}}
    search_results = {"status": "error", "results": []}

    # --- Step 2: 委托企业数据Agent ---
    print("--- Step 2: 委托企业数据Agent 查询企业数据 ---")
    try:
        enterprise_data = doc_agent.delegate_to_enterprise_data(
            token, "get_all_enterprise_data"
        )
        print(f"[OK] 企业数据Agent 返回数据:")
        print(f"     Status: {enterprise_data.get('status')}")
        if enterprise_data.get("status") == "ok":
            for category, result in enterprise_data.get("data", {}).items():
                if isinstance(result, dict) and result.get("status") == "ok":
                    print(f"     - {category}: {result.get('count', 'N/A')} records")
                elif isinstance(result, dict):
                    print(f"     - {category}: {result.get('status', 'error')}")
    except PermissionError as e:
        print(f"[DENIED] {e}")
    print()

    # --- Step 3: 委托外部检索Agent ---
    print("--- Step 3: 委托外部检索Agent 搜索外部信息 ---")
    try:
        search_results = doc_agent.delegate_to_external_search(
            token, "AI Agent 身份与权限管理"
        )
        print(f"[OK] 外部检索Agent 返回数据:")
        print(f"     Status: {search_results.get('status')}")
        if search_results.get("status") == "ok":
            print(f"     Result count: {search_results.get('count', 0)}")
            for r in search_results.get("results", []):
                print(f"     - {r.get('title', 'N/A')}")
    except PermissionError as e:
        print(f"[DENIED] {e}")
    print()

    # --- Step 4: Write report to Feishu doc ---
    print("--- Step 4: 生成报告并写入飞书文档 ---")
    report = doc_agent._compile_report(
        "AI Agent 身份与权限管理综合调研",
        enterprise_data,
        search_results,
    )
    print("[OK] 报告已编译")
    print()
    print("--- 报告预览 (前500字符) ---")
    print(report[:500])
    print()

    # --- Step 5: Show audit logs ---
    print("--- 审计日志 ---")
    client = httpx.Client()
    resp = client.get("http://127.0.0.1:8900/audit/logs", params={"limit": 20})
    client.close()
    if resp.status_code == 200:
        logs = resp.json().get("logs", [])
        for entry in logs:
            decision_mark = "[ALLOW]" if entry.get("decision") == "allow" else "[DENY]"
            agent = entry.get("caller_agent_id") or entry.get("agent_id", "N/A")
            verifier = entry.get("verifier_agent_id", "")
            verifier_str = f" → {verifier}" if verifier and verifier != "unknown" else ""
            print(f"  {decision_mark} {entry.get('event')} | "
                  f"caller={agent}{verifier_str} | "
                  f"cap={entry.get('required_capability', 'N/A')} | "
                  f"reason={entry.get('reason', 'N/A')}")
    print()

    print("=" * 60)
    print("  演示一完成：正常委托流程全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()

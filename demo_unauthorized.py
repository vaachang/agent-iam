#!/usr/bin/env python3
"""
Demo: Unauthorized Interception

外部检索Agent 尝试委托企业数据Agent读取多维表格数据。
由于外部检索Agent没有对应的权限，请求被拦截，
返回明确错误码，审计日志记录拦截信息。
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
    print("  演示二：越权拦截流程")
    print("  外部检索Agent → 企业数据Agent (应被拦截)")
    print("=" * 60)
    print()

    if not check_server():
        print("ERROR: IAM server is not running. Start it first with:")
        print("  python iam_server.py &")
        sys.exit(1)

    print("[OK] IAM Server is running\n")

    sys.path.insert(0, ".")
    from agents.external_search_agent import ExternalSearchAgent
    from agents.enterprise_data_agent import EnterpriseDataAgent

    external_agent = ExternalSearchAgent()
    enterprise_agent = EnterpriseDataAgent()

    print(f"[INFO] 外部检索Agent Capabilities: {external_agent.capabilities}")
    print(f"[INFO] 企业数据Agent 需要 capability: delegate:enterprise_data (或具体数据权限)")
    print()

    # --- Step 1: 外部检索Agent gets its own token ---
    print("--- Step 1: 外部检索Agent 获取 Access Token ---")
    print("     计算有效权限: 用户权限 ∩ Agent能力")
    try:
        external_token = external_agent.get_token(delegated_user="user_lisi")
        print(f"[OK] Token issued for 外部检索Agent")
        print(f"     Agent 注册能力: {external_agent.capabilities}")
        print(f"     有效权限(交集): {external_agent.effective_capabilities}")
    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
    print()

    # --- Step 2: 外部检索Agent attempts to read enterprise bitable ---
    print("--- Step 2: 外部检索Agent 尝试读取企业多维表格数据 ---")
    print("     (应被拦截: 外部检索Agent 没有 delegate:enterprise_data 或 feishu_bitable:read)")
    print()
    try:
        result = enterprise_agent.list_bitable_apps(external_token)
        print(f"[UNEXPECTED] 请求通过了！这表示权限系统存在漏洞！")
        print(f"     Result: {result}")
    except PermissionError as e:
        print(f"[DENIED] 权限不足，请求被正确拦截！")
        print(f"     错误信息: {e}")
    print()

    # --- Step 3: 外部检索Agent also tries to read contacts ---
    print("--- Step 3: 外部检索Agent 尝试读取企业通讯录 ---")
    print("     (同样应该被拦截)")
    print()
    try:
        result = enterprise_agent.list_users(external_token)
        print(f"[UNEXPECTED] 请求通过了！这表示权限系统存在漏洞！")
    except PermissionError as e:
        print(f"[DENIED] 权限不足，请求被正确拦截！")
        print(f"     错误信息: {e}")
    print()

    # --- Step 4: Verify external search still works ---
    print("--- Step 4: 验证外部检索Agent 仍可以使用自身权限 ---")
    try:
        result = external_agent.search("test query", external_token)
        print(f"[OK] 外部检索正常 (自身权限不受影响)")
        print(f"     Status: {result.get('status')}")
    except PermissionError as e:
        print(f"[FAIL] 自身权限也被拒绝: {e}")
    print()

    # --- Step 5: Show audit logs ---
    print("--- 审计日志 (筛选 DENY 记录) ---")
    client = httpx.Client()
    resp = client.get(
        "http://127.0.0.1:8900/audit/logs",
        params={"limit": 20, "decision": "deny"},
    )
    client.close()
    if resp.status_code == 200:
        logs = resp.json().get("logs", [])
        if not logs:
            print("  (没有 DENY 记录)")
        for entry in logs:
            agent = entry.get("caller_agent_id") or entry.get("agent_id", "N/A")
            verifier = entry.get("verifier_agent_id", "")
            verifier_str = f" → {verifier}" if verifier and verifier != "unknown" else ""
            print(f"  [DENY] {entry.get('event')} | "
                  f"caller={agent}{verifier_str} | "
                  f"required={entry.get('required_capability', 'N/A')} | "
                  f"reason={entry.get('reason', 'N/A')} | "
                  f"code={entry.get('error_code', 'N/A')}")
    print()

    print("=" * 60)
    print("  演示二完成：越权请求已被成功拦截！")
    print("=" * 60)


if __name__ == "__main__":
    main()

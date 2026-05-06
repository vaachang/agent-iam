#!/usr/bin/env python3
"""Agent IAM System v2.0 — 交互式演示 (含动态授权、Token撤销、绑定、自然语言驱动)"""
import json, os, sys, time, httpx

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

# Load .env
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

IAM = "http://127.0.0.1:8900"
SEP = "=" * 64
SEP2 = "-" * 48
demo_doc_url = ""


def show_logs(label, decision=None, limit=5):
    print(f"\n{SEP2}\n  {label}\n{SEP2}")
    params = {"limit": limit}
    if decision:
        params["decision"] = decision
    resp = httpx.get(f"{IAM}/audit/logs", params=params)
    logs = resp.json().get("logs", [])
    if not logs:
        print("  (无记录)")
        return
    for entry in logs:
        mark = "[ALLOW]" if entry.get("decision") == "allow" else "[DENY]"
        event = entry.get("event", "?")
        caller = entry.get("caller_agent_id") or entry.get("agent_id", "?")
        verifier = entry.get("verifier_agent_id", "")
        required = entry.get("required_capability", "")
        reason = entry.get("reason", "")
        error = f" [{entry.get('error_code')}]" if entry.get("error_code") else ""
        line = f"  {mark} {event:12s} | caller={caller}"
        if verifier and verifier != "unknown":
            line += f" → verifier={verifier}"
        if required:
            line += f" | cap={required}"
        line += f" | {reason}{error}"
        print(line)


def classify_intent_nl(user_input: str) -> dict:
    """Use LLM to parse natural language into structured intent."""
    from config import LLM_API_KEY, LLM_MODEL_ID, LLM_API_BASE as LLM_BASE
    if not (LLM_API_KEY and LLM_MODEL_ID):
        return None
    prompt = (
        "你是 Agent IAM 系统的意图识别器。分析用户输入，返回JSON。\n"
        "意图类型: normal_delegation(生成报告/调研), unauthorized_test(越权测试/拦截), "
        "audit_review(审计日志), system_overview(系统概览), "
        "token_revoke(撤销Token), dynamic_elevate(动态提升权限)\n"
        '格式: {"intent":"类型","topic":"主题","user":"user_zhangsan或user_lisi"}\n'
        f"输入: {user_input}\n直接返回JSON:"
    )
    try:
        resp = httpx.post(
            f"{LLM_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL_ID, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 200},
            timeout=15.0,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except Exception:
        pass
    return None


# ========== DEMO FUNCTIONS ==========

def demo_overview():
    print(f"\n{SEP}\n  系统概览\n{SEP}")
    resp = httpx.get(f"{IAM}/agents")
    for aid, info in resp.json().items():
        print(f"  {info['name']} ({aid})\n    {info['description']}")
        print(f"    Capabilities: {', '.join(info['capabilities'])}")
    print()
    resp = httpx.get(f"{IAM}/users")
    for uid, info in resp.json().items():
        print(f"  {info['name']} ({uid}): {', '.join(info['permissions']) or '(无)'}")
    resp = httpx.get(f"{IAM}/health/metrics")
    m = resp.json()
    print(f"\n  系统指标: issued={m['counters']['tokens_issued']} "
          f"revoked={m['counters']['tokens_revoked']}")
    print(f"  告警: {', '.join(m.get('alerts', ['N/A']))}")


def demo_normal_delegation():
    global demo_doc_url
    print(f"\n{SEP}\n  演示一：正常委托流程\n{SEP}")

    resp = httpx.post(f"{IAM}/token/issue", json={
        "agent_id": "feishu_doc_agent", "agent_secret": "doc_agent_secret_key_2024",
        "delegated_user": "user_zhangsan",
    })
    token = resp.json()["access_token"]
    print(f"  [1/4] Token 签发 ✅ {resp.json()['effective_capabilities']}")

    from agents.feishu_doc_agent import FeishuDocAgent
    doc = FeishuDocAgent()
    try:
        enterprise = doc.delegate_to_enterprise_data(token, "get_all_enterprise_data")
        print(f"  [2/4] 企业数据查询 ✅ "
              f"contacts={enterprise.get('data',{}).get('contacts',{}).get('count',0)}, "
              f"calendars={enterprise.get('data',{}).get('calendars',{}).get('count',0)}")
    except PermissionError as e:
        print(f"  [2/4] ❌ {e}")
        enterprise = {"error": str(e)}
    try:
        search = doc.delegate_to_external_search(token, "AI Agent 身份与权限管理")
        print(f"  [3/4] 外部检索 ✅ {search.get('count',0)} 条结果")
    except PermissionError as e:
        print(f"  [3/4] ❌ {e}")
        search = {"error": str(e)}

    report = doc._compile_report_enhanced("AI Agent IAM 调研报告", enterprise, search)
    doc_result = doc.create_doc("综合报告: Agent IAM 调研", report)
    print(f"  [4/4] 飞书文档 ✅ {doc_result.get('document_url')} ({doc_result.get('blocks_written',0)} blocks)")
    demo_doc_url = doc_result.get('document_url', '')
    show_logs("审计日志", limit=6)


def demo_unauthorized():
    print(f"\n{SEP}\n  演示二：越权拦截流程\n{SEP}")
    from agents.external_search_agent import ExternalSearchAgent
    from agents.enterprise_data_agent import EnterpriseDataAgent
    exa, ea = ExternalSearchAgent(), EnterpriseDataAgent()

    resp = httpx.post(f"{IAM}/token/issue", json={
        "agent_id": "external_search_agent", "agent_secret": "external_agent_secret_key_2024",
        "delegated_user": "user_lisi",
    })
    ext_token = resp.json()["access_token"]
    print(f"  外部检索Agent Token: {resp.json()['effective_capabilities']}")

    blocked = 0
    for name, method in [("多维表格", ea.list_bitable_apps), ("通讯录", ea.list_users), ("日历", ea.list_calendars)]:
        try:
            method(ext_token)
            print(f"  ❌ {name}: 越权通过!")
        except PermissionError as e:
            blocked += 1
            print(f"  ✅ {name}: 拦截成功 [{str(e)[:80]}...]")

    result = exa.search("test", ext_token)
    print(f"  ✅ 自身搜索不受影响: {result.get('count',0)} 结果")
    print(f"\n  拦截率: {blocked}/3")
    show_logs("DENY 记录", decision="deny", limit=5)


def demo_dynamic_elevation():
    print(f"\n{SEP}\n  演示三：动态授权 (Token Elevation)\n{SEP}")

    resp = httpx.post(f"{IAM}/token/issue", json={
        "agent_id": "feishu_doc_agent", "agent_secret": "doc_agent_secret_key_2024",
        "delegated_user": "user_lisi",
    })
    tk = resp.json()
    token = tk["access_token"]
    print(f"  [1] 基础Token (user_lisi): {tk['effective_capabilities']}")

    resp = httpx.post(f"{IAM}/token/verify", json={
        "token": token, "required_capability": "feishu_doc:read",
    })
    print(f"  [2] 尝试 feishu_doc:read → {resp.json()['decision']} (lisi无此权限)")

    resp = httpx.post(f"{IAM}/token/elevate", json={
        "token": token, "requested_capability": "feishu_doc:read",
        "justification": "紧急报告需要临时文档读取权限", "ttl_seconds": 60,
    })
    el = resp.json()
    print(f"  [3] 动态提升 → {el['decision']}")
    if el.get("access_token"):
        resp = httpx.post(f"{IAM}/token/verify", json={
            "token": el["access_token"], "required_capability": "feishu_doc:read",
        })
        print(f"      提升后验证 → {resp.json()['decision']} (临时授权 {el['expires_in']}s)")

    resp = httpx.post(f"{IAM}/token/elevate", json={
        "token": token, "requested_capability": "delegate:enterprise_data",
        "justification": "尝试越权", "ttl_seconds": 60,
    })
    print(f"  [4] 尝试提升到 delegate:enterprise_data → {resp.json()['decision']} (user_lisi未授权此权限)")


def demo_token_revocation():
    print(f"\n{SEP}\n  演示四：Token 实时撤销\n{SEP}")

    resp = httpx.post(f"{IAM}/token/issue", json={
        "agent_id": "feishu_doc_agent", "agent_secret": "doc_agent_secret_key_2024",
        "delegated_user": "user_zhangsan",
    })
    token = resp.json()["access_token"]
    print(f"  [1] 签发 Token")

    resp = httpx.post(f"{IAM}/token/verify", json={"token": token, "required_capability": "feishu_doc:read"})
    print(f"  [2] 验证: {resp.json()['decision']}")

    resp = httpx.post(f"{IAM}/token/revoke", json={"token": token, "reason": "agent_misbehavior"})
    print(f"  [3] 撤销: {resp.json()['status']}")

    resp = httpx.post(f"{IAM}/token/verify", json={"token": token, "required_capability": "feishu_doc:read"})
    print(f"  [4] 再次验证: {resp.json()['decision']} [{resp.json().get('error_code','?')}]")

    resp = httpx.get(f"{IAM}/token/blacklist")
    print(f"  [5] 黑名单: {resp.json()['revoked_count']} 个已撤销Token")


def demo_token_binding():
    print(f"\n{SEP}\n  演示五：Token 防盗用绑定\n{SEP}")

    resp = httpx.post(f"{IAM}/token/issue", json={
        "agent_id": "external_search_agent", "agent_secret": "external_agent_secret_key_2024",
        "delegated_user": "user_lisi", "bound_to": "agent-host-001.internal",
    })
    token = resp.json()["access_token"]
    print(f"  [1] 绑定Token (bound_to=agent-host-001.internal)")

    resp = httpx.post(f"{IAM}/token/verify", json={
        "token": token, "required_capability": "external:search",
        "bound_to": "agent-host-001.internal",
    })
    print(f"  [2] 合法来源验证: {resp.json()['decision']}")

    resp = httpx.post(f"{IAM}/token/verify", json={
        "token": token, "required_capability": "external:search",
        "bound_to": "attacker.evil.com",
    })
    r = resp.json()
    print(f"  [3] 盗用来源验证: {r['decision']} [{r.get('error_code','')}]")


def demo_natural_language():
    print(f"\n{SEP}\n  自然语言指令驱动模式\n{SEP}")
    print("  示例: 「帮我调研AI Agent安全方案并生成报告」")
    print("         「用李四的身份测试越权拦截」")
    print("         「查看审计日志」「撤销最近签发的Token」")
    user_input = input("\n  请输入指令: ").strip()
    if not user_input:
        return

    print(f"\n{SEP2}\n  解析: \"{user_input}\"\n{SEP2}")
    intent = classify_intent_nl(user_input)
    if not intent:
        if any(w in user_input for w in ["越权", "拦截", "测试"]):
            intent = {"intent": "unauthorized_test", "user": "user_lisi" if "李四" in user_input else "user_zhangsan"}
        elif any(w in user_input for w in ["日志", "审计"]):
            intent = {"intent": "audit_review"}
        elif any(w in user_input for w in ["撤销", "吊销"]):
            intent = {"intent": "token_revoke"}
        else:
            intent = {"intent": "normal_delegation", "topic": user_input, "user": "user_zhangsan"}
        print(f"  本地匹配: {intent['intent']}")
    else:
        print(f"  LLM识别: {intent}")

    it = intent.get("intent", "normal_delegation")
    if it == "normal_delegation":
        demo_normal_delegation()
    elif it == "unauthorized_test":
        demo_unauthorized()
    elif it == "audit_review":
        show_logs("审计日志", limit=15)
    elif it == "token_revoke":
        demo_token_revocation()
    elif it == "dynamic_elevate":
        demo_dynamic_elevation()
    elif it == "system_overview":
        demo_overview()


# ========== MAIN ==========

def main():
    if httpx.get(f"{IAM}/health").status_code != 200:
        print("[ERROR] IAM Server not running. Start: bash start.sh")
        sys.exit(1)

    print(f"\n{SEP}\n     Agent IAM 系统 v2.0 — 交互式演示\n{SEP}")
    demo_overview()

    while True:
        print(f"\n{SEP}\n  选择演示项目:")
        print("    0. 系统概览         3. 动态授权 (Token Elevation)")
        print("    1. 正常委托流程      4. Token 实时撤销")
        print("    2. 越权拦截流程      5. Token 防盗用绑定")
        print("    6. 审计日志审查     7. 运行全部演示")
        print("    n. 自然语言指令     q. 退出")
        print(SEP)
        choice = input("  > ").strip()

        if choice == "0":   demo_overview()
        elif choice == "1": demo_normal_delegation()
        elif choice == "2": demo_unauthorized()
        elif choice == "3": demo_dynamic_elevation()
        elif choice == "4": demo_token_revocation()
        elif choice == "5": demo_token_binding()
        elif choice == "6": show_logs("审计日志", limit=15)
        elif choice == "7":
            demo_overview(); demo_normal_delegation(); demo_unauthorized()
            demo_dynamic_elevation(); demo_token_revocation(); demo_token_binding()
            show_logs("审计日志", limit=15)
        elif choice.lower() == "n": demo_natural_language()
        elif choice.lower() == "q":
            print("  再见!")
            break


if __name__ == "__main__":
    main()

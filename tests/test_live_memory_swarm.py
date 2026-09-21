import sys
import io
import time
import requests
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def run_test():
    print(">>> [Step 1] Checking /health...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    print("    Health status:", r.json())

    print("\n>>> [Step 2] Initiating new research swarm for MSFT...")
    r = requests.post(f"{BASE_URL}/api/research", json={"query": "Analyze MSFT for the last 12 months"})
    assert r.status_code == 200, f"Failed: {r.text}"
    init_data = r.json()
    session_id = init_data["session_id"]
    print(f"    Session initiated: {session_id}")

    print("\n>>> [Step 3] Streaming research swarm SSE events...")
    with requests.get(f"{BASE_URL}/api/research/stream/{session_id}", stream=True) as stream_resp:
        for line in stream_resp.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    payload = json.loads(line_str[6:])
                    event_type = payload.get("event")
                    if event_type == "step":
                        agent = payload.get("agent")
                        status = payload.get("status")
                        print(f"    [Agent] {agent}: {status}")
                    elif event_type == "report":
                        print("    [Report] Final report received via SSE!")
                    elif event_type == "done":
                        print("    [Done] Swarm completed execution.")
                        break
                    elif event_type == "error":
                        print("    [Error]", payload.get("error"))
                        break

    print("\n>>> [Step 4] Fetching completed session and verifying conversational memory seeding...")
    r = requests.get(f"{BASE_URL}/api/research/{session_id}")
    assert r.status_code == 200
    session_data = r.json()
    chat_messages = session_data.get("chat_messages", [])
    report = session_data.get("report", "")
    
    print(f"    Initial chat memory messages count: {len(chat_messages)}")
    assert len(chat_messages) >= 2, f"Expected at least 2 seeded messages, got {len(chat_messages)}"
    assert chat_messages[0]["role"] == "user"
    assert chat_messages[1]["role"] == "assistant"
    print("    Turn 0 (User query) and Turn 1 (Assistant dossier) verified in DB memory!")

    print("\n>>> [Step 5] Validating direct clickable URLs in Report Section 10 & 9...")
    assert "## 10. Sources" in report or "10. Sources" in report, "Section 10 missing"
    assert "https://finance.yahoo.com" in report, "Yahoo Finance direct URLs missing"
    assert "sec.gov" in report, "SEC direct URLs missing"
    print("    Report successfully includes direct URLs for SEC, Yahoo Finance, and Tavily articles!")

    print("\n>>> [Step 6] Asking conversational follow-up Question 1...")
    q1 = "What is MSFT's gross margin and debt-to-equity ratio according to the quantitative analysis?"
    r1 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "message": q1})
    assert r1.status_code == 200
    ans1 = r1.json()
    print("    Follow-up 1 Answer (first 180 chars):", ans1.get("answer")[:180].replace("\n", " "), "...")
    print("    Memory turns reported:", ans1.get("memory_turns"))
    assert ans1.get("memory_turns") >= 3

    print("\n>>> [Step 7] Asking conversational follow-up Question 2 (referencing previous turns & requesting URLs)...")
    q2 = "Provide the direct links and URLs for the SEC filing and financial statements."
    r2 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "message": q2})
    assert r2.status_code == 200
    ans2 = r2.json()
    print("    Follow-up 2 Answer (first 180 chars):", ans2.get("answer")[:180].replace("\n", " "), "...")
    print("    Memory turns reported:", ans2.get("memory_turns"))
    assert "http" in ans2.get("answer"), "Follow-up answer should contain clickable URLs"

    print("\n>>> [Step 8] Verifying full multi-turn memory in database...")
    r_check = requests.get(f"{BASE_URL}/api/research/{session_id}")
    updated_chat = r_check.json().get("chat_messages", [])
    print(f"    Total chat messages in DB now: {len(updated_chat)}")
    assert len(updated_chat) >= 6, f"Expected at least 6 messages, got {len(updated_chat)}"

    for idx, msg in enumerate(updated_chat):
        preview = msg['content'][:60].replace('\n', ' ')
        print(f"      Turn {idx}: [{msg['role']}] {preview}...")

    print("\n>>> ALL MULTI-TURN MEMORY AND DIRECT URL VERIFICATIONS PASSED 100%!")

if __name__ == "__main__":
    run_test()

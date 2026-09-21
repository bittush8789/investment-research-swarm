import sys
import io
import requests
import json

# Set stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"

def test_memory_and_urls():
    print(">>> 1. Health Check...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health = r.json()
    print(f"    Status: {health.get('status')}, Model: {health.get('groq_model')}")
    assert health.get("groq_model") == "openai/gpt-oss-120b", "Expected openai/gpt-oss-120b"

    print(">>> 2. Fetching recent sessions from history...")
    r = requests.get(f"{BASE_URL}/api/history?limit=5")
    assert r.status_code == 200
    history = r.json()
    assert len(history) > 0, "No sessions found in history"
    session_id = history[0]["session_id"]
    ticker = history[0]["ticker"]
    print(f"    Found session: {session_id} for {ticker}")

    print(">>> 3. Fetching session details and checking chat memory...")
    r = requests.get(f"{BASE_URL}/api/research/{session_id}")
    assert r.status_code == 200
    data = r.json()
    report = data.get("report", "")
    chat_messages = data.get("chat_messages", [])
    print(f"    Initial chat memory messages count: {len(chat_messages)}")
    print(f"    Report length: {len(report)} characters")

    # Check for direct URLs in Section 10 and Section 9
    print(">>> 4. Validating direct clickable URLs in report...")
    assert "https://" in report or "http://" in report, "Report must contain direct URLs"
    assert "10. Sources" in report or "## Sources" in report, "Section 10 Sources missing"
    assert "https://finance.yahoo.com" in report or "sec.gov" in report, "Expected financial URLs in report"
    print("    Report contains direct URLs (SEC EDGAR / Yahoo Finance / Tavily)!")

    # Check multi-turn memory
    print(">>> 5. Testing multi-turn conversational memory (Turn 1)...")
    q1 = f"What are the top 2 risks for {ticker} mentioned in the report?"
    r1 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "message": q1})
    assert r1.status_code == 200, f"Follow-up 1 failed: {r1.text}"
    ans1 = r1.json()
    print(f"    Answer 1 (first 200 chars): {ans1.get('answer')[:200]}...")
    print(f"    Memory turns reported: {ans1.get('memory_turns')}")

    print(">>> 6. Testing multi-turn conversational memory (Turn 2 referencing prior question)...")
    q2 = f"Can you provide the direct source URLs and filing references for those risks?"
    r2 = requests.post(f"{BASE_URL}/api/chat", json={"session_id": session_id, "message": q2})
    assert r2.status_code == 200, f"Follow-up 2 failed: {r2.text}"
    ans2 = r2.json()
    print(f"    Answer 2 (first 200 chars): {ans2.get('answer')[:200]}...")
    print(f"    Memory turns reported: {ans2.get('memory_turns')}")
    assert "http" in ans2.get("answer"), "Follow-up answer should include URLs as requested"

    print(">>> 7. Verifying persistent database storage of conversation memory...")
    r_updated = requests.get(f"{BASE_URL}/api/research/{session_id}")
    updated_data = r_updated.json()
    updated_chat = updated_data.get("chat_messages", [])
    print(f"    Updated chat memory count in DB: {len(updated_chat)}")
    assert len(updated_chat) >= len(chat_messages) + 4, "Expected at least 4 new messages (2 user + 2 assistant)"
    
    # Verify last messages
    last_user_msg = updated_chat[-2]
    last_assistant_msg = updated_chat[-1]
    assert last_user_msg["role"] == "user" and last_user_msg["content"] == q2
    assert last_assistant_msg["role"] == "assistant"
    print("    Database verified: All turns persisted in chronological order!")

    print("\nALL MEMORY AND URL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_memory_and_urls()

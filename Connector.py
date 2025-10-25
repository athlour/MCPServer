"""
Ollama + MCP Connector (Enhanced Edition)
-----------------------------------------
Ultra-stable connector that links Ollama to a local MCP server.
Strictly enforces tool-based reasoning with no code output.
Includes:
- Automatic fallback for ignored tool calls
- Broader rain detection & smart notifications
- Built-in logging and error resilience
"""

import requests
import json
import re
import time
from datetime import datetime

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MCP_URL = "http://localhost:9000/mcp"
MODEL = "phi3:mini"  # Suggested: "phi3:mini", "llama3", or "mistral"
ALERT_KEYWORDS = ["rain", "drizzle", "shower", "storm"]
DEFAULT_CITY = "Chennai"

# ----------------------------------------------------------------------
# Utility: Print timestamps for clarity
# ----------------------------------------------------------------------
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ----------------------------------------------------------------------
# Helper: Query Ollama
# ----------------------------------------------------------------------
def ask_ollama(prompt: str, max_retries=3) -> str:
    """Send a prompt to Ollama, retry on failure."""
    payload = {"model": MODEL, "prompt": prompt, "stream": False}
    for attempt in range(max_retries):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=60)
            data = r.json()
            return data.get("response", r.text)
        except Exception as e:
            log(f"⚠️ Ollama request failed (attempt {attempt+1}): {e}")
            time.sleep(1)
    return "[Error: Ollama request failed after retries]"

# ----------------------------------------------------------------------
# Helper: Call MCP tool
# ----------------------------------------------------------------------
def call_mcp_tool(tool: str, args: dict, max_retries=2) -> dict:
    """Send a JSON-RPC request to the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(int(time.time())),
        "method": "mcp/call_tool",
        "params": {"tool": tool, "arguments": args},
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(MCP_URL, json=payload, timeout=60)
            if r.status_code == 200:
                return r.json()
            else:
                log(f"⚠️ MCP call failed (HTTP {r.status_code}): {r.text[:200]}")
        except Exception as e:
            log(f"⚠️ MCP call exception: {e}")
            time.sleep(1)
    return {"error": f"MCP call failed for {tool}"}

# ----------------------------------------------------------------------
# Helper: Detect JSON tool calls
# ----------------------------------------------------------------------
def detect_tool_call(text: str):
    """Detect valid JSON tool call blocks."""
    json_block = re.search(r"\{[\s\S]*?\}", text)
    if json_block:
        try:
            j = json.loads(json_block.group(0))
            if "name" in j and "arguments" in j:
                return j["name"], j["arguments"]
        except Exception:
            pass
    return None, None

# ----------------------------------------------------------------------
# Chat loop
# ----------------------------------------------------------------------
def chat_loop():
    print("\n🤖 Ollama + MCP Connector (Enhanced Mode)")
    print("💡 Type 'exit' to quit.\n")

    system_instruction = (
        "SYSTEM INSTRUCTION:\n"
        "You are an AI assistant connected to a local MCP server.\n"
        "You cannot write or show code.\n"
        "You must call tools for all external actions.\n"
        "Available tools:\n"
        "1. get_weather(city: string)\n"
        "2. send_notification(notification_input: string)\n"
        "Always respond ONLY in JSON format like:\n"
        "{ \"name\": \"<tool_name>\", \"arguments\": { ... } }\n"
    )
    ask_ollama(system_instruction)
    log("✅ System prompt initialized.\n")

    while True:
        try:
            user_input = input("🟢 You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                print("👋 Goodbye!")
                break

            # Reinforce instruction each turn
            enforced_input = (
                f"Reminder: Never show code. Use MCP tools only.\n\nUser request: {user_input}"
            )
            model_output = ask_ollama(enforced_input)
            print(f"\n💬 Ollama:\n{model_output}\n")

            tool, args = detect_tool_call(model_output)

            # Fallback detection for weather or notification
            if not tool:
                if "weather" in user_input.lower():
                    log("⚙️ Model ignored rule; forcing get_weather tool call.")
                    city_match = re.findall(r"in\s+([A-Za-z ]+)", user_input)
                    city = city_match[0].strip() if city_match else DEFAULT_CITY
                    tool, args = "get_weather", {"city": city}
                elif "notify" in user_input.lower() or "alert" in user_input.lower():
                    log("⚙️ Forcing send_notification tool call.")
                    tool, args = "send_notification", {
                        "notification_input": f"{user_input}|general_alerts"
                    }

            # If still no tool
            if not tool:
                log("⚙️ No tool call detected.\n")
                continue

            log(f"🧰 Tool Detected: {tool} with args {args}")
            mcp_response = call_mcp_tool(tool, args)

            text = (
                mcp_response.get("result", {})
                .get("content", [{}])[0]
                .get("text", "")
            )
            if not text:
                log("⚠️ Empty MCP result received.")
                continue

            print(f"🧮 MCP result: {text}\n")

            # Rain/Drizzle Notification Trigger
            if tool == "get_weather":
                lower_text = text.lower()
                if any(k in lower_text for k in ALERT_KEYWORDS):
                    log("☔ Weather alert detected — sending notification.")
                    notif_input = f"{text}|weather_alerts"
                    notif_result = call_mcp_tool(
                        "send_notification",
                        {"notification_input": notif_input},
                    )
                    notif_text = (
                        notif_result.get("result", {})
                        .get("content", [{}])[0]
                        .get("text", "")
                    )
                    log(f"🔔 Notification: {notif_text}\n")

            # Summarize result for user
            summary_prompt = f"Summarize in one line, clearly and concisely: {text}"
            summary = ask_ollama(summary_prompt)
            print(f"💡 Final Answer:\n{summary}\n")

        except KeyboardInterrupt:
            print("\n👋 Session ended by user.")
            break
        except Exception as e:
            log(f"❌ Unexpected error: {e}")
            continue

# ----------------------------------------------------------------------
if __name__ == "__main__":
    chat_loop()

"""
Flask + MCP Server with Weather + Notification Tools
----------------------------------------------------
- get_weather(city): Fetch current weather via OpenWeatherMap API
- send_notification(notification_input): Push message via Ntfy
"""

from flask import Flask, request, jsonify
from mcp.server import Server
from mcp.types import Tool, TextContent
import asyncio
import logging
import os
import requests

# --------------------------------------------------------------------
# Basic setup
# --------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
mcp_server = Server("flask-mcp-server")
app = Flask(__name__)

# --------------------------------------------------------------------
# TOOL: get_weather(city)
# --------------------------------------------------------------------
def get_weather(city: str) -> str:
    """
    Fetches the current weather for a given city using OpenWeatherMap API.
    Advises to carry an umbrella if rain is mentioned in the description.
    """
    api_key = "88fb13a484c079f6680237dbbc748f07"
    if not api_key:
        return "Weather API key not found. Please set the WEATHER_API_KEY environment variable."

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code != 200:
        return f"Error fetching weather: {response.json().get('message', 'Unknown error')}"

    data = response.json()
    if data.get('main') and data.get('weather'):
        temp = data['main']['temp']
        description = data['weather'][0]['description']
        weather_info = f"The current temperature in {city} is {temp}°C with {description}."
        if 'rain' in description.lower():
            weather_info += " Heavy rain expected. Carry an umbrella!"
        return weather_info
    else:
        return f"Unable to fetch weather for {city}. Please check the city name."

# --------------------------------------------------------------------
# TOOL: send_notification(notification_input)
# --------------------------------------------------------------------
import requests

def send_notification(notification_input: str) -> str:
    """
    Sends a push notification using the Ntfy API.
    Provide input as: "message|topic"
    Example: "Hello World|genai_demo"
    """
    try:
        # Ensure it’s a proper string
        if isinstance(notification_input, list):
            notification_input = " ".join(str(x) for x in notification_input)

        parts = str(notification_input).split("|", 1)
        if len(parts) != 2:
            return "Invalid input. Format must be 'message|topic'."

        message, topic = parts
        url = f"https://ntfy.sh/athlour"
        response = requests.post(url, data=message.strip().encode("utf-8"))

        if response.status_code == 200:
            return f"✅ Notification sent to '{topic.strip()}': {message.strip()}"
        return f"❌ Failed to send notification (HTTP {response.status_code})"

    except Exception as e:
        return f"Error sending notification: {e}"

# --------------------------------------------------------------------
# Register MCP tools
# --------------------------------------------------------------------
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise available tools to clients."""
    return [
        Tool(
            name="get_weather",
            description="Fetches current weather for a given city using OpenWeatherMap API.",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name to get weather for"}
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="send_notification",
            description="Sends a push notification using the Ntfy API. Format: 'message|topic'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "notification_input": {
                        "type": "string",
                        "description": "Input format: 'message|topic'",
                    }
                },
                "required": ["notification_input"],
            },
        ),
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from connector or ChatGPT MCP clients."""
    try:
        if name == "get_weather":
            city = arguments.get("city", "")
            result = get_weather(city)
            return [TextContent(type="text", text=result)]

        elif name == "send_notification":
            notification_input = arguments.get("notification_input", "")
            result = send_notification(notification_input)
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logging.exception("Tool execution error:")
        return [TextContent(type="text", text=f"Error executing tool {name}: {e}")]

# --------------------------------------------------------------------
# Flask routes
# --------------------------------------------------------------------
@app.route("/", methods=["GET"])
def root():
    return (
        "<h2>Flask + MCP Server</h2>"
        "<p>Tools: get_weather(city), send_notification(notification_input)</p>"
        "<p>POST JSON-RPC 2.0 requests to <code>/mcp</code>.</p>",
        200,
    )

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/tools", methods=["GET"])
def list_tools_http():
    loop = asyncio.new_event_loop()
    tools = loop.run_until_complete(list_tools())
    loop.close()
    return jsonify([tool.model_dump() for tool in tools]), 200

@app.route("/mcp", methods=["GET", "POST"])
def mcp_http_handler():
    if request.method == "GET":
        return jsonify({
            "message": "MCP endpoint active. Use POST for JSON-RPC calls.",
            "example": {
                "method": "mcp/call_tool",
                "params": {"tool": "get_weather", "arguments": {"city": "Chennai"}}
            }
        }), 200

    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Invalid JSON"},
            "id": None
        }), 400

    async def handle():
        # explicitly run the tool
        method = payload.get("method")
        if method == "mcp/call_tool":
            params = payload.get("params", {})
            tool = params.get("tool")
            args = params.get("arguments", {})

            if tool == "get_weather":
                result_text = get_weather(args.get("city", ""))
            elif tool == "send_notification":
                result_text = send_notification(args.get("notification_input", ""))
            else:
                result_text = f"Unknown tool '{tool}'"

            return {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {
                    "content": [
                        {"type": "text", "text": result_text}
                    ]
                }
            }

        elif method == "mcp/list_tools":
            tools = await list_tools()
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "result": {"tools": [tool.model_dump() for tool in tools]}
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32601, "message": "Unknown method"}
            }

    try:
        response = asyncio.run(handle())
        return jsonify(response)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return jsonify({
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {"code": -32000, "message": f"Internal Server Error: {exc}"}
        }), 500

# --------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------
if __name__ == "__main__":
    logging.info("Starting Flask MCP Server on http://localhost:9000")
    app.run(host="0.0.0.0", port=9000)

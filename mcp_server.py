#!/usr/bin/env python3
"""
Configurable MCP Server with Multiple Transports

A flexible FastMCP server using the official MCP SDK with support for
STDIO, SSE, and HTTP transports. Transport type and other settings
can be configured via command-line arguments.

Usage:
    python mcp_server.py                    # STDIO transport (default)
    python mcp_server.py -t sse             # SSE transport on port 8000
    python mcp_server.py -t sse -p 9000     # SSE transport on custom port
    python mcp_server.py -t http -p 8080    # HTTP transport on port 8080

For AutoGen integration:
    # STDIO (most compatible)
    from autogen_ext.tools.mcp import StdioServerParams
    params = StdioServerParams(command="python", args=["mcp_server.py"])
    
    # SSE
    from autogen_ext.tools.mcp import SseServerParams  
    params = SseServerParams(url="http://localhost:8000/sse")
    
    # HTTP
    from autogen_ext.tools.mcp import StreamableHttpServerParams
    params = StreamableHttpServerParams(url="http://localhost:8000")
"""

import argparse
import json
import sys
from typing import Dict, Any, Literal

# from mcp.server.fastmcp import FastMCP
from fastmcp import FastMCP
# Create the MCP server instance
mcp = FastMCP("clean-demo-server")

@mcp.tool()
def echo(text: str) -> str:
    """Echo back the input text"""
    return f"Echo: {text}"

@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together"""
    return a + b

@mcp.tool()
def get_weather(city: str) -> Dict[str, Any]:
    """Get mock weather information for a city"""
    return {
        "city": city,
        "temperature": "22°C",
        "condition": "Sunny",
        "humidity": "65%",
        "wind": "10 km/h",
        "timestamp": "2025-01-01T12:00:00Z"
    }

@mcp.tool()
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number"""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

@mcp.tool()
def reverse_string(text: str) -> str:
    """Reverse the input string"""
    return text[::-1]

@mcp.resource("info://server")
def get_server_info() -> str:
    """Get basic information about this MCP server"""
    info = {
        "name": "Configurable Demo MCP Server",
        "version": "1.0.0",
        "description": "A configurable FastMCP server with multiple transport support",
        "tools": ["echo", "add_numbers", "get_weather", "calculate_fibonacci", "reverse_string"],
        "resources": ["info://server", "docs://getting-started"],
        "transports": ["stdio", "sse", "http"],
        "default_transport": "stdio"
    }
    return json.dumps(info, indent=2)

@mcp.resource("docs://getting-started")
def get_getting_started() -> str:
    """Get a guide to using this MCP server"""
    return """Getting Started with Configurable Demo MCP Server

This server implements the MCP (Model Context Protocol) specification
with support for multiple transports: STDIO, SSE, and HTTP.

Command Line Usage:
  python mcp_server.py                    # STDIO transport (default)
  python mcp_server.py -t sse             # SSE transport on port 8000  
  python mcp_server.py -t sse -p 9000     # SSE transport on custom port
  python mcp_server.py -t http -p 8080    # HTTP transport on port 8080
  python mcp_server.py --verbose          # Enable verbose output
  python mcp_server.py --help             # Show all options

Available Tools:
1. echo - Echo back any text you provide
2. add_numbers - Add two numbers together  
3. get_weather - Get mock weather information for a city
4. calculate_fibonacci - Calculate the nth Fibonacci number
5. reverse_string - Reverse the input string

Available Resources:
1. info://server - JSON information about this server
2. docs://getting-started - This getting started guide

AutoGen Integration Examples:

STDIO Transport (most compatible):
```python
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
from autogen_agentchat.agents import AssistantAgent

# Set up MCP server parameters
params = StdioServerParams(
    command="python",
    args=["mcp_server.py", "--transport", "stdio"]
)

# Create tools from MCP server
tools = await mcp_server_tools(params)

# Create agent with MCP tools
agent = AssistantAgent(
    name="mcp_agent",
    model_client=your_model_client,
    tools=tools
)
```

SSE Transport:
```python
from autogen_ext.tools.mcp import SseServerParams, mcp_server_tools

# For default port 8000
params = SseServerParams(url="http://localhost:8000/sse")

# For custom port (start server with: python mcp_server.py -t sse -p 9000)
params = SseServerParams(url="http://localhost:9000/sse")

tools = await mcp_server_tools(params)
```

HTTP Transport:
```python  
from autogen_ext.tools.mcp import StreamableHttpServerParams, mcp_server_tools

# For default port 8000
params = StreamableHttpServerParams(url="http://localhost:8000")

# For custom port (start server with: python mcp_server.py -t http -p 8080)
params = StreamableHttpServerParams(url="http://localhost:8080")

tools = await mcp_server_tools(params)
```

This server provides a flexible, configurable implementation with support
for all major MCP transport types, making it compatible with various
deployment scenarios and AutoGen integrations.
"""

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Clean MCP Server with configurable transport",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mcp_server.py                          # STDIO transport (default)
  python mcp_server.py -t sse                   # SSE transport on port 8000
  python mcp_server.py -t sse -p 9000           # SSE transport on port 9000
  python mcp_server.py -t http -p 8080          # HTTP transport on port 8080
  python mcp_server.py -t stdio                 # Explicit STDIO transport
        """
    )
    
    parser.add_argument(
        '-t', '--transport',
        choices=['stdio', 'sse', 'http'],
        default='stdio',
        help='Transport type (default: stdio)'
    )
    
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8000,
        help='Port for SSE/HTTP transports (default: 8000)'
    )
    
    parser.add_argument(
        '--host',
        default='localhost',
        help='Host for SSE/HTTP transports (default: localhost)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser.parse_args()

def main():
    """Main entry point - runs the MCP server with configurable transport"""
    args = parse_args()
    
    print("Starting Configurable Demo MCP Server")
    print(f"Transport: {args.transport}")
    print("Mode: Subprocess/Local")
    
    if args.transport == "sse":
        print(f"SSE URL: http://{args.host}:{args.port}/sse")
    elif args.transport == "http":
        print(f"HTTP URL: http://{args.host}:{args.port}")
    elif args.transport == "stdio":
        print("STDIO: Ready for subprocess communication")
    
    print("Ready for AutoGen integration")
    print("=" * 50)
    
    if args.verbose:
        print(f"Configuration:")
        print(f"  Transport: {args.transport}")
        print(f"  Host: {args.host}")
        print(f"  Port: {args.port} (requested)")
        print(f"  Verbose: {args.verbose}")
        print("=" * 50)
    
    # Run the server with specified transport
    # Note: FastMCP may have limited port configuration support
    try:
        if args.transport == "sse":
            mcp.run(transport="sse" , host=args.host, port=args.port)
        elif args.transport == "http":
            mcp.run(transport="streamable-http" , host=args.host, port=args.port) 
        else:  # stdio
            mcp.run(transport="stdio")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

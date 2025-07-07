# MCP Chat Implementations

This folder contains different implementations of MCP (Model Context Protocol) chat interfaces using AutoGen's official MCP SDK.

## Files Overview

### 1. `mcp_cli.py` - Full-Featured CLI
- Complete command-line interface with multiple transports (STDIO, SSE, HTTP)
- Rich formatting and comprehensive error handling
- Multiple commands: `tools`, `call`, `chat`, `info`
- Advanced configuration options

### 2. `mcp_chat.py` - Simplified Chat Interface
- Streamlined class-based implementation
- Focuses on core chat functionality
- Better for understanding the basic structure
- Includes proper setup and error handling

### 3. `simple_mcp_chat.py` - Ultra-Simple Example
- Minimal code (~60 lines)
- Single function implementation
- Perfect for learning and quick testing
- Shows the bare essentials of MCP integration

## Usage

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
export OPENAI_API_KEY=your_api_key_here
```

### Running the Simple Version
```bash
python simple_mcp_chat.py
```

### Running the Class-Based Version
```bash
python mcp_chat.py [server_script.py]
```

### Running the Full CLI
```bash
# Chat with default settings
python mcp_cli.py chat

# List available tools
python mcp_cli.py tools

# Call a specific tool
python mcp_cli.py call echo --arg text="Hello World"

# Use different transport
python mcp_cli.py -t sse chat
```

## Key Features

All implementations use:
- ✅ Official AutoGen MCP SDK (`autogen_ext.tools.mcp`)
- ✅ Native MCP tool adapters
- ✅ Proper async/await patterns
- ✅ OpenAI GPT-4o-mini model
- ✅ Real-time streaming responses

## Which Version to Use?

- **Learning/Testing**: Use `simple_mcp_chat.py`
- **Development**: Use `mcp_chat.py` 
- **Production**: Use `mcp_cli.py`

## MCP Server

All versions expect an MCP server script (default: `mcp_server.py`) that implements the Model Context Protocol. The server should provide tools that the AI assistant can use to help users.

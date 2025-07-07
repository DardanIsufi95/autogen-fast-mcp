#!/usr/bin/env python3
"""
Simple MCP Chat - A streamlined version using AutoGen MCP SDK
Supports basic chat functionality with MCP tools
"""
import asyncio
import os
from typing import Optional

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage, ToolCallRequestEvent, ToolCallExecutionEvent, ToolCallSummaryMessage
from autogen_core import CancellationToken

# MCP imports
from autogen_ext.tools.mcp import (
    StdioServerParams,
    mcp_server_tools
)

from dotenv import load_dotenv
from pydantic import BaseModel
load_dotenv()



class SimpleMcpChat:
    """Simple MCP Chat interface"""
    
    def __init__(self, server_script: str = "mcp_server.py"):
        self.server_script = server_script
        self.model_client = None
        self.agent = None
        
    async def setup(self) -> bool:
        """Setup the chat session"""
        # 1. Setup OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ Error: No OPENAI_API_KEY found in environment")
            print("   Set it with: export OPENAI_API_KEY=your_key")
            return False
            
        self.model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",
            api_key=api_key
        )
        print("✅ OpenAI client ready")
        
        # 2. Setup MCP tools
        try:
            server_params = StdioServerParams(
                command="python",
                args=[self.server_script],
                read_timeout_seconds=30
            )
            
            tools = await mcp_server_tools(server_params)
            print(f"✅ Connected to MCP server: {len(tools)} tools available")
            
            # 3. Create agent with tools
            self.agent = AssistantAgent(
                name="mcp_assistant",
                model_client=self.model_client,
                tools=tools,  # type: ignore
                max_tool_iterations=2,
                system_message="You are a helpful assistant with access to MCP tools. Use the available tools to help users accomplish their tasks."
            )
            print("✅ Agent ready")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup MCP tools: {e}")
            return False
    
    async def chat(self):
        """Start interactive chat session"""
        if not self.agent:
            print("❌ Agent not initialized. Run setup() first.")
            return
            
        print("\n🤖 MCP Chat Session Started")
        print("Type 'quit', 'exit', or 'stop' to end the session\n")
        
        try:
            while True:
                # Get user input
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'stop']:
                    print("\n👋 Chat session ended")
                    break
                    
                # if not user_input:
                #     continue
                
                # Get the complete result from the agent
                print("Assistant: ", end="", flush=True)
                
                try:
                    result = await self.agent.run(
                        task=user_input,
                        cancellation_token=CancellationToken()
                    )
                    
                    # Display the conversation flow
                    for message in result.messages:
                        if isinstance(message, TextMessage):
                            # Skip the user's original message
                            if hasattr(message, 'source') and message.source == 'user':
                                continue
                            
                            if hasattr(message, 'content') and message.content:
                                print(message.content)
                        
                        elif isinstance(message, ToolCallRequestEvent):
                            print(f"\n🔧 Using tools: {[call.name for call in message.content]}")
                        
                        elif isinstance(message, ToolCallSummaryMessage):
                            print(f"\n📋 Tool Results:")
                            if hasattr(message, 'results') and message.results:
                                for tool_result in message.results:
                                    # Parse the tool result content
                                    content = tool_result.content
                                    if content.startswith('[{"type": "text", "text": "') and content.endswith('"}]'):
                                        # Extract the actual text from the JSON structure
                                        import json
                                        try:
                                            parsed = json.loads(content)
                                            actual_content = parsed[0]["text"] if parsed and "text" in parsed[0] else content
                                        except:
                                            actual_content = content
                                    else:
                                        actual_content = content
                                    
                                    print(f"   • {tool_result.name}: {actual_content}")
                            print()
                        
                
                except Exception as e:
                    print(f"❌ Error running agent: {e}")
                
                print("")  # New line after response
                
        except KeyboardInterrupt:
            print("\n\n👋 Chat session interrupted")
        except Exception as e:
            print(f"\n❌ Chat error: {e}")

async def main():
    """Main function to run the simple MCP chat"""
    import sys
    
    # Get server script from command line or use default
    server_script = sys.argv[1] if len(sys.argv) > 1 else "mcp_server.py"
    
    # Create and setup chat
    chat = SimpleMcpChat(server_script)
    
    print("🚀 Setting up Simple MCP Chat...")
    if await chat.setup():
        await chat.chat()
    else:
        print("❌ Failed to setup chat session")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Ultra-Simple MCP Chat Example
Minimal code to demonstrate MCP integration with AutoGen
"""
import asyncio
import os
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
from autogen_core import CancellationToken
from dotenv import load_dotenv

load_dotenv()

async def simple_mcp_chat():
    """Ultra-simple MCP chat in one function"""
    
    # 1. Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Set OPENAI_API_KEY environment variable")
        return
    
    # 2. Create OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found")
        return
        
    model = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=api_key
    )
    
    # 3. Connect to MCP server and get tools
    server_params = StdioServerParams(
        command="python",
        args=["mcp_server.py"]
    )
    tools = await mcp_server_tools(server_params)
    
    # 4. Create agent with MCP tools
    agent = AssistantAgent(
        name="assistant",
        model_client=model,
        tools=tools,  # type: ignore
        system_message="You are a helpful assistant with MCP tools."
    )
    
    # 5. Simple chat loop
    print(f"🤖 Chat ready! ({len(tools)} MCP tools available)")
    print("Type 'quit' to exit\n")
    
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == 'quit':
            break
            
        print("Assistant: ", end="", flush=True)
        
        # Track assistant responses only
        response_started = False
        
        async for msg in agent.run_stream(task=user_input, cancellation_token=CancellationToken()):
            if isinstance(msg, TextMessage) and msg.content:
                # Check if this is the user's message being echoed
                if msg.content.strip() == user_input.strip():
                    continue  # Skip the echo
                    
                # Check if this looks like a system/user message
                if msg.content.startswith("You:") or msg.content.startswith("User:"):
                    continue  # Skip user message echoes
                    
                # This should be the assistant's actual response
                print(msg.content, end="", flush=True)
                response_started = True
            
        print()

if __name__ == "__main__":
    asyncio.run(simple_mcp_chat())

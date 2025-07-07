#!/usr/bin/env python3
"""
Modern MCP CLI using official AutoGen MCP SDK
Supports STDIO, SSE, and StreamableHTTP transports
"""
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax

# AutoGen imports
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console as AutogenConsole
from autogen_agentchat.messages import TextMessage, ToolCallRequestEvent, ToolCallExecutionEvent, ToolCallSummaryMessage
from autogen_core import CancellationToken

# MCP imports
from autogen_ext.tools.mcp import (
    McpWorkbench,
    StdioServerParams,
    SseServerParams, 
    StreamableHttpServerParams,
    mcp_server_tools
)
from dotenv import load_dotenv
load_dotenv()
console = Console()

class ModernMcpCli:
    """Modern MCP CLI using official AutoGen SDK patterns"""
    
    def __init__(self, transport: str = "stdio", server_config: Optional[Dict[str, Any]] = None, **kwargs):
        self.transport = transport
        self.server_config = server_config or {}
        self.model_client = None
        self.workbench = None
        self.tools = []
        self.agent = None
        self.kwargs = kwargs
        
    async def setup_model_client(self) -> bool:
        """Setup OpenAI model client"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                console.print("[-] No OPENAI_API_KEY found in environment", style="red")
                console.print("    Set it with: export OPENAI_API_KEY=your_key", style="yellow")
                return False
                
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o-mini",
                api_key=api_key
            )
            console.print(f"[+] Model client ready: gpt-4o-mini", style="green")
            return True
            
        except Exception as e:
            console.print(f"[-] Failed to setup model client: {e}", style="red")
            return False
    
    def _get_server_params(self):
        """Get server parameters based on transport type and configuration"""
        if self.transport == "docker":
            return StdioServerParams(
                command="docker",
                args= ["run","-i","--rm","mcp/duckduckgo"],
                read_timeout_seconds=self.server_config.get("read_timeout", 30)
            ) 

        if self.transport == "stdio":
            return StdioServerParams(
                command=self.server_config.get("command", "python"),
                args=self.server_config.get("args", ["mcp_server.py"]),
                read_timeout_seconds=self.server_config.get("read_timeout", 30)
            )
        elif self.transport == "sse":
            return SseServerParams(
                url=self.server_config.get("url", "http://localhost:8000/sse"),
                timeout=self.server_config.get("timeout", 10),
                sse_read_timeout=self.server_config.get("sse_read_timeout", 300)
            )
        elif self.transport == "http":
            # StreamableHTTP - let the client handle the endpoint path
            url = self.server_config.get("url", "http://localhost:8000")
            # Ensure URL doesn't have any path for HTTP transport
            if url.endswith('/'):
                url = url.rstrip('/')
            
            return StreamableHttpServerParams(
                url=url,
                timeout=self.server_config.get("timeout", 30.0),
                sse_read_timeout=self.server_config.get("sse_read_timeout", 300.0),
                terminate_on_close=self.server_config.get("terminate_on_close", True)
            )
        else:
            raise ValueError(f"Unsupported transport: {self.transport}")
    
    async def setup_workbench(self) -> bool:
        """Setup MCP workbench using official patterns"""
        try:
            server_params = self._get_server_params()
            
            # Get tool adapters directly (preferred pattern)
            self.tools = await mcp_server_tools(server_params)
            console.print(f"[+] Connected via {self.transport.upper()}: {len(self.tools)} tools", style="green")
            
            # Also setup workbench for direct tool calls
            self.workbench = McpWorkbench(server_params=server_params)
            await self.workbench.start()
            
            return True
            
        except Exception as e:
            if self.transport == "http":
                console.print(f"[-] HTTP transport failed: {e}", style="red")
                console.print("[yellow]⚠️  HTTP transport may have compatibility issues.[/yellow]")
                console.print("[yellow]   Try using SSE transport instead:[/yellow]")
                console.print(f"[cyan]   python mcp_cli.py -t sse tools[/cyan]")
            else:
                console.print(f"[-] Failed to setup {self.transport} workbench: {e}", style="red")
            return False
    
    async def setup_agent(self) -> bool:
        """Setup AutoGen agent with MCP tools"""
        try:
            if not self.model_client:
                console.print("[-] Model client not ready", style="red")
                return False
                
            if not self.tools:
                console.print("[-] No tools available", style="red")
                return False
            
            self.agent = AssistantAgent(
                name="mcp_assistant",
                model_client=self.model_client,
                tools=self.tools,  # type: ignore
                max_tool_iterations=20,  # Limit tool iterations for better control
                system_message="You are a helpful assistant with access to MCP tools. Use the available tools to help users accomplish their tasks."
            )
            
            console.print(f"[+] Agent ready with {len(self.tools)} MCP tools", style="green")
            return True
            
        except Exception as e:
            console.print(f"[-] Failed to create agent: {e}", style="red")
            return False
    
    def _format_tool_calls(self, tool_calls):
        """Format tool call information in a readable way"""
        if not tool_calls:
            return
            
        console.print("\n[bold cyan]🔧 Tool Calls:[/bold cyan]")
        
        for i, call in enumerate(tool_calls, 1):
            # Create a panel for each tool call
            tool_name = getattr(call, 'name', 'Unknown')
            tool_args = getattr(call, 'arguments', '{}')
            
            try:
                # Try to parse arguments as JSON for better formatting
                if isinstance(tool_args, str):
                    args_dict = json.loads(tool_args)
                else:
                    args_dict = tool_args
                    
                args_text = ""
                if args_dict:
                    for key, value in args_dict.items():
                        args_text += f"  • {key}: {value}\n"
                else:
                    args_text = "  No parameters"
                    
            except (json.JSONDecodeError, AttributeError):
                args_text = f"  Raw: {tool_args}"
            
            panel_content = f"[bold white]{tool_name}[/bold white]\n{args_text.rstrip()}"
            console.print(Panel(
                panel_content,
                title=f"Tool {i}",
                border_style="cyan",
                padding=(0, 1)
            ))
    
    def _format_tool_results(self, tool_results):
        """Format tool execution results in a readable way"""
        if not tool_results:
            return
            
        console.print("\n[bold green]✅ Tool Results:[/bold green]")
        
        for i, result in enumerate(tool_results, 1):
            tool_name = getattr(result, 'name', 'Unknown')
            content = getattr(result, 'content', '')
            is_error = getattr(result, 'is_error', False)
            
            # Parse content if it's a JSON string
            try:
                if isinstance(content, str) and content.startswith('['):
                    content_list = json.loads(content)
                    if content_list and isinstance(content_list[0], dict):
                        content = content_list[0].get('text', content)
                        
                        # Try to parse as JSON for pretty printing
                        try:
                            json_data = json.loads(content)
                            content = json.dumps(json_data, indent=2)
                        except:
                            pass
            except:
                pass
            
            border_style = "red" if is_error else "green"
            title_emoji = "❌" if is_error else "✅"
            
            console.print(Panel(
                content,
                title=f"{title_emoji} {tool_name}",
                border_style=border_style,
                padding=(0, 1)
            ))
    
    async def _stream_response(self, user_input: str):
        """Stream response with custom formatting"""
        if not self.agent:
            console.print("[red]Agent not available[/red]")
            return
            
        try:
            response_started = False
            tool_calls_shown = False
            
            async for message in self.agent.run_stream(
                task=user_input,
                cancellation_token=CancellationToken()
            ):
                if isinstance(message, TextMessage):
                    if not response_started:
                        console.print(f"\n[bold blue]Assistant:[/bold blue]", end="")
                        response_started = True
                    
                    # Print the text content
                    if hasattr(message, 'content') and message.content:
                        # Skip if this is the user's message being echoed back
                        if message.content.strip() == user_input.strip():
                            continue
                        
                        # Skip user message indicators
                        if message.content.startswith("You:") or message.content.startswith("User:"):
                            continue
                            
                        print(f" {message.content}", end="")
                
                elif isinstance(message, ToolCallRequestEvent):
                    if not tool_calls_shown:
                        self._format_tool_calls(message.content)
                        tool_calls_shown = True
                
                elif isinstance(message, ToolCallExecutionEvent):
                    self._format_tool_results(message.content)
                
                elif isinstance(message, ToolCallSummaryMessage):
                    # This contains the final summary, we can optionally show it
                    pass
            
            if response_started:
                print()  # New line after response
                
        except Exception as e:
            console.print(f"\n[red]Error during response: {e}[/red]")
    
    async def list_tools(self):
        """List available MCP tools"""
        if not self.workbench:
            console.print("[-] Workbench not initialized", style="red")
            return
            
        try:
            tool_schemas = await self.workbench.list_tools()
            
            table = Table(title=f"MCP Tools ({self.transport.upper()} transport)")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            table.add_column("Parameters", style="yellow")
            
            for tool in tool_schemas:
                # Get parameter names using dict access
                params = []
                if 'parameters' in tool and tool['parameters']:
                    if isinstance(tool['parameters'], dict) and 'properties' in tool['parameters']:
                        params = list(tool['parameters']['properties'].keys())
                
                param_str = ", ".join(params) if params else "none"
                
                table.add_row(
                    tool['name'],
                    tool.get('description', "No description"),
                    param_str
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[-] Failed to list tools: {e}", style="red")
    
    async def call_tool(self, tool_name: str, **arguments):
        """Call a specific MCP tool"""
        if not self.workbench:
            console.print("[-] Workbench not initialized", style="red")
            return
            
        try:
            result = await self.workbench.call_tool(tool_name, arguments)
            
            # Format arguments nicely
            args_text = ""
            if arguments:
                for key, value in arguments.items():
                    args_text += f"  • {key}: {value}\n"
            else:
                args_text = "  No parameters"
            
            # Extract result content
            result_text = str(result)
            if hasattr(result, 'result') and result.result:
                try:
                    # Extract text content from result
                    content = result.result[0]
                    if hasattr(content, 'content'):
                        result_text = content.content
                except:
                    pass
            
            panel_content = f"[bold cyan]{tool_name}[/bold cyan]\n\n[bold]Parameters:[/bold]\n{args_text.rstrip()}\n\n[bold]Result:[/bold]\n{result_text}"
            
            panel = Panel(
                panel_content,
                title="🔧 Tool Call Result",
                border_style="green",
                padding=(1, 2)
            )
            console.print(panel)
            
        except Exception as e:
            console.print(f"[-] Failed to call tool '{tool_name}': {e}", style="red")
    
    async def chat(self):
        """Interactive chat with the agent"""
        if not self.agent:
            console.print("[-] Agent not initialized", style="red")
            return
            
        console.print("\n[bold green]MCP Chat Session Started[/bold green]")
        console.print("Type 'quit', 'exit', or 'stop' to end the session\n")
        
        try:
            while True:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'stop']:
                    console.print("\n[yellow]Chat session ended[/yellow]")
                    break
                    
                if not user_input:
                    continue
                
                # Use custom streaming with better formatting
                await self._stream_response(user_input)
                
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Chat session interrupted[/yellow]")
        except Exception as e:
            console.print(f"[-] Chat error: {e}", style="red")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.workbench:
            try:
                await self.workbench.stop()
            except Exception as e:
                console.print(f"Warning: Cleanup error: {e}", style="yellow")

# CLI Commands

@click.group()
@click.option('--transport', '-t', 
              type=click.Choice(['stdio', 'sse', 'http','docker']), 
              default='stdio',
              help='MCP transport type')
@click.option('--server-script', '-s',
              default='mcp_server.py',
              help='Server script for STDIO transport')
@click.option('--server-args',
              default='',
              help='Additional arguments for server script (e.g., "-t stdio --verbose")')
@click.option('--server-url', '-u',
              default='http://localhost:8000',
              help='Server URL for SSE/HTTP transports')
@click.option('--server-port', '-p',
              type=int,
              default=8000,
              help='Server port for SSE/HTTP transports')
@click.option('--timeout',
              type=int,
              default=30,
              help='Request timeout in seconds')
@click.pass_context
def cli(ctx, transport, server_script, server_args, server_url, server_port, timeout):
    """Modern MCP CLI using official AutoGen SDK"""
    ctx.ensure_object(dict)
    ctx.obj['transport'] = transport
    
    # Build server configuration
    server_config = {
        'timeout': timeout,
        'read_timeout': timeout,
        'sse_read_timeout': timeout * 10
    }
    
    if transport == 'stdio':
        # Build args list from server_script and server_args
        args = [server_script]
        if server_args:
            # Split server_args properly, handling quoted strings
            import shlex
            args.extend(shlex.split(server_args))
        
        server_config.update({
            'command': 'python',
            'args': args
        })
    else:
        # For SSE and HTTP, adjust URL based on port if default URL is used
        if server_url == 'http://localhost:8000' and server_port != 8000:
            server_url = f'http://localhost:{server_port}'
        
        server_config['url'] = server_url
        if transport == 'sse':
            server_config['url'] = f"{server_url}/sse" if not server_url.endswith('/sse') else server_url
    
    ctx.obj['server_config'] = server_config

@cli.command()
@click.pass_context
def tools(ctx):
    """List available MCP tools"""
    async def run():
        cli_app = ModernMcpCli(
            transport=ctx.obj['transport'],
            server_config=ctx.obj['server_config']
        )
        try:
            if await cli_app.setup_workbench():
                await cli_app.list_tools()
        finally:
            await cli_app.cleanup()
    
    asyncio.run(run())

@cli.command()
@click.argument('tool_name')
@click.option('--arg', '-a', multiple=True, 
              help='Tool arguments as key=value pairs')
@click.pass_context
def call(ctx, tool_name, arg):
    """Call a specific MCP tool"""
    async def run():
        cli_app = ModernMcpCli(
            transport=ctx.obj['transport'],
            server_config=ctx.obj['server_config']
        )
        try:
            if await cli_app.setup_workbench():
                # Parse arguments
                arguments = {}
                for a in arg:
                    if '=' in a:
                        key, value = a.split('=', 1)
                        arguments[key] = value
                    else:
                        console.print(f"[-] Invalid argument format: {a}", style="red")
                        console.print("    Use: --arg key=value", style="yellow")
                        return
                
                await cli_app.call_tool(tool_name, **arguments)
        finally:
            await cli_app.cleanup()
    
    asyncio.run(run())

@cli.command()
@click.pass_context  
def chat(ctx):
    """Interactive chat with MCP-enabled agent"""
    async def run():
        cli_app = ModernMcpCli(
            transport=ctx.obj['transport'],
            server_config=ctx.obj['server_config']
        )
        try:
            success = (
                await cli_app.setup_model_client() and
                await cli_app.setup_workbench() and
                await cli_app.setup_agent()
            )
            
            if success:
                await cli_app.chat()
            else:
                console.print("[-] Failed to initialize chat session", style="red")
        finally:
            await cli_app.cleanup()
    
    asyncio.run(run())

@cli.command()
@click.pass_context
def info(ctx):
    """Show MCP CLI information and setup status"""
    transport = ctx.obj['transport']
    server_config = ctx.obj['server_config']
    
    # Build server info based on transport
    if transport == 'stdio':
        server_info = f"Script: {' '.join(server_config.get('args', ['mcp_server.py']))}"
    else:
        server_info = f"URL: {server_config.get('url', 'Not configured')}"
    
    console.print(Panel.fit(
        f"[bold blue]Modern MCP CLI[/bold blue]\n\n"
        f"[bold]Transport:[/bold] {transport.upper()}\n"
        f"[bold]Server:[/bold] {server_info}\n"
        f"[bold]Timeout:[/bold] {server_config.get('timeout', 30)}s\n"
        f"[bold]API Key:[/bold] {'Found' if os.getenv('OPENAI_API_KEY') else 'Not found'}\n\n"
        f"[bold]Available Commands:[/bold]\n"
        f"• [cyan]tools[/cyan]  - List available MCP tools\n"
        f"• [cyan]call[/cyan]   - Call a specific tool\n"
        f"• [cyan]chat[/cyan]   - Interactive chat session\n"
        f"• [cyan]info[/cyan]   - Show this information\n\n"
        f"[bold]Server Configuration Examples:[/bold]\n"
        f"[dim]# Use custom server script[/dim]\n"
        f"[dim]mcp-cli --server-script my_server.py tools[/dim]\n"
        f"[dim]# Use server with arguments[/dim]\n"
        f"[dim]mcp-cli --server-args \"-t stdio --verbose\" tools[/dim]\n"
        f"[dim]# Use SSE transport (recommended for network)[/dim]\n"
        f"[dim]mcp-cli -t sse --server-port 9000 tools[/dim]\n"
        f"[dim]# Use custom URL[/dim]\n"
        f"[dim]mcp-cli -t sse --server-url http://remote:8080/sse tools[/dim]\n"
        f"[dim]# Custom timeout[/dim]\n"
        f"[dim]mcp-cli --timeout 60 chat[/dim]\n\n"
        f"[bold yellow]Note:[/bold yellow] HTTP transport may have compatibility issues.\n"
        f"Use STDIO (default) or SSE for best reliability.",
        title="MCP CLI Information",
        border_style="blue"
    ))

if __name__ == "__main__":
    cli()

import argparse
import asyncio
from typing import Any, Literal, Optional, Union
from weakref import proxy

from fastmcp import Client as MCPClient
from fastmcp import FastMCP

mcp = FastMCP("mcp-proxy-server")

# python mcp_proxy.py sse --port 8000 -- docker run -i --rm mcp/duckduckgo
## TODO fix container not shutting down properly

async def setup_proxy_tools(command_args):
    """Setup proxy tools by connecting to the external MCP server"""
    transport_config = {
        "mcpServers": {
            "command": {
                "command": command_args[0],
                "args": command_args[1:] if len(command_args) > 1 else [],
            }
        }
    }
    print(transport_config)
    async with MCPClient(transport=transport_config) as mcp_client:
        tool_list = await mcp_client.list_tools()

        print("Available tools:")
        
        tools_to_register = []
        for tool in tool_list:
            print(f" - {tool.name}: {tool.description}")
            tools_to_register.append(tool)
    
    # Register proxy tools dynamically with proper parameter definitions
    for tool in tools_to_register:
        # Extract parameter information from the tool schema
        schema = tool.inputSchema or {}
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        # Create a dynamic function string with proper typing
        param_defs = []
        param_calls = []
        
        for param_name, param_info in properties.items():
            # Skip 'ctx' parameter as it's MCP internal
            if param_name == 'ctx':
                continue
                
            # Determine type annotation with support for complex types (fully recursive)
            def get_python_type(param_info):
                # Handle schema references
                if '$ref' in param_info:
                    # For now, treat references as generic dicts
                    # In a full implementation, you'd resolve the reference
                    return "dict[str, Any]"
                
                param_type = param_info.get('type')
                
                # Handle the case where type is an array of types
                if isinstance(param_type, list):
                    if len(param_type) == 1:
                        param_type = param_type[0]
                    else:
                        # Multiple types specified as array - create Union
                        type_variants = []
                        for t in param_type:
                            temp_info = param_info.copy()
                            temp_info['type'] = t
                            type_variants.append(get_python_type(temp_info))
                        return f"Union[{', '.join(type_variants)}]"
                
                if param_type == 'integer':
                    return "int"
                elif param_type == 'number':
                    return "float"
                elif param_type == 'boolean':
                    return "bool"
                elif param_type == 'array':
                    # Handle arrays recursively - check if items type is specified
                    items = param_info.get('items', {})
                    if items:
                        item_type = get_python_type(items)
                        return f"list[{item_type}]"
                    else:
                        return "list[Any]"
                elif param_type == 'object':
                    # Handle objects recursively
                    properties = param_info.get('properties', {})
                    if properties:
                        # For objects with defined properties, create a Union of all possible value types
                        # This is more practical than TypedDict for dynamic use
                        value_types = []
                        for prop_info in properties.values():
                            prop_type = get_python_type(prop_info)
                            if prop_type not in value_types:
                                value_types.append(prop_type)
                        
                        if len(value_types) == 1:
                            return f"dict[str, {value_types[0]}]"
                        elif len(value_types) > 1:
                            return f"dict[str, Union[{', '.join(value_types)}]]"
                        else:
                            return "dict[str, Any]"
                    else:
                        # Generic object without specific properties
                        additional_props = param_info.get('additionalProperties')
                        if additional_props and isinstance(additional_props, dict):
                            value_type = get_python_type(additional_props)
                            return f"dict[str, {value_type}]"
                        else:
                            return "dict[str, Any]"
                elif param_type == 'null':
                    return "type(None)"
                elif 'enum' in param_info:
                    # For enums, create a Union of literal values for better type safety
                    enum_values = param_info['enum']
                    if enum_values:
                        if all(isinstance(v, str) for v in enum_values):
                            # Use Literal for string enums for precise type checking
                            escaped_values = [f'"{v}"' for v in enum_values]
                            return f"Literal[{', '.join(escaped_values)}]"
                        elif all(isinstance(v, int) for v in enum_values):
                            # Use Literal for int enums too
                            return f"Literal[{', '.join(map(str, enum_values))}]"
                        elif all(isinstance(v, (int, float)) for v in enum_values):
                            # Mixed numeric enums
                            return f"Literal[{', '.join(map(str, enum_values))}]"
                        else:
                            # Mixed types in enum, fall back to Union
                            type_set = set()
                            for v in enum_values:
                                if isinstance(v, str):
                                    type_set.add("str")
                                elif isinstance(v, int):
                                    type_set.add("int")
                                elif isinstance(v, float):
                                    type_set.add("float")
                                elif isinstance(v, bool):
                                    type_set.add("bool")
                                else:
                                    type_set.add("Any")
                            return f"Union[{', '.join(sorted(type_set))}]"
                    else:
                        return "str"
                elif param_type == 'string':
                    # Handle string with format specifications
                    format_type = param_info.get('format')
                    if format_type in ['date', 'date-time', 'time']:
                        return "str"  # Could be datetime if we want to be more specific
                    elif format_type == 'uri':
                        return "str"  # Could be a URL type
                    elif format_type == 'email':
                        return "str"  # Could be an Email type
                    else:
                        return "str"
                elif 'anyOf' in param_info or 'oneOf' in param_info:
                    # Handle union types
                    schemas = param_info.get('anyOf', param_info.get('oneOf', []))
                    if schemas:
                        union_types = []
                        for schema in schemas:
                            union_types.append(get_python_type(schema))
                        # Remove duplicates while preserving order
                        unique_types = []
                        for t in union_types:
                            if t not in unique_types:
                                unique_types.append(t)
                        if len(unique_types) == 1:
                            return unique_types[0]
                        else:
                            return f"Union[{', '.join(unique_types)}]"
                    else:
                        return "Any"
                elif 'allOf' in param_info:
                    # Handle intersection types (usually means object with merged properties)
                    all_schemas = param_info.get('allOf', [])
                    if all_schemas:
                        # Try to merge object types intelligently
                        all_object = True
                        all_properties = {}
                        for schema in all_schemas:
                            if schema.get('type') == 'object':
                                props = schema.get('properties', {})
                                all_properties.update(props)
                            else:
                                all_object = False
                                break
                        
                        if all_object and all_properties:
                            # Create a dict type based on merged properties
                            value_types = []
                            for prop_info in all_properties.values():
                                prop_type = get_python_type(prop_info)
                                if prop_type not in value_types:
                                    value_types.append(prop_type)
                            
                            if len(value_types) == 1:
                                return f"dict[str, {value_types[0]}]"
                            elif len(value_types) > 1:
                                return f"dict[str, Union[{', '.join(value_types)}]]"
                            else:
                                return "dict[str, Any]"
                        else:
                            return "dict[str, Any]"
                    else:
                        return "dict[str, Any]"
                elif param_type is None and not any(k in param_info for k in ['anyOf', 'oneOf', 'allOf', 'enum', '$ref']):
                    # No type specified and no complex schema - default behavior
                    return "Any"
                else:
                    # Default to string for unknown types or when type is explicitly 'string'
                    return "str"
            
            param_type = get_python_type(param_info)
            
            # Add to parameter definitions and calls
            if param_name in required:
                param_defs.append(f"{param_name}: {param_type}")
            else:
                default_val = param_info.get('default')
                if default_val is not None:
                    # Handle different types of default values
                    if isinstance(default_val, str):
                        param_defs.append(f'{param_name}: {param_type} = "{default_val}"')
                    elif isinstance(default_val, (list, dict)):
                        # For complex types, represent as string and eval later
                        param_defs.append(f"{param_name}: {param_type} = {repr(default_val)}")
                    else:
                        param_defs.append(f"{param_name}: {param_type} = {default_val}")
                else:
                    # Use Optional type for non-required parameters without defaults
                    if param_type.startswith(('list', 'dict')):
                        param_defs.append(f"{param_name}: Optional[{param_type}] = None")
                    else:
                        param_defs.append(f"{param_name}: Optional[{param_type}] = None")
            
            param_calls.append(param_name)
        
        # Create the function definition as a string
        params_str = ", ".join(param_defs)
        
        # Build the call arguments
        call_args_str = "{"
        for param in param_calls:
            call_args_str += f'"{param}": {param}, '
        call_args_str = call_args_str.rstrip(", ") + "}"
        
        # Create the complete function
        func_code = f'''
@mcp.tool
async def {tool.name}({params_str}):
    """{tool.description}"""
    # Filter out None values
    call_args = {{k: v for k, v in {call_args_str}.items() if v is not None}}
    async with MCPClient(transport=transport_config) as client:
        return await client.call_tool("{tool.name}", call_args)
'''
        
        # Execute the function definition
        exec_globals = {
            'mcp': mcp,
            'MCPClient': MCPClient,
            'transport_config': transport_config,
            'Optional': Optional,
            'Union': Union,
            'Any': Any,
            'Literal': Literal,
            'list': list,
            'dict': dict,
            'type': type
        }
        exec(func_code, exec_globals)


def main():
    parser = argparse.ArgumentParser(
        description=("Start the MCP proxy in one of two possible modes: as a client or a server."),
        epilog=(
            "Examples:\n"
            " mcp_proxy.py sse --port 8080 --host localhost -- docker run -i --rm mcp/duckduckgo\n"
            " mcp_proxy.py http --port 9000 -- python mcp_server.py\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=["sse", "http"],
        help="The mode to run the MCP proxy in.",
    ) 
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="The port to run the MCP proxy on (default: 8080)."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="The host to run the MCP proxy on (default: localhost)."
    )
    
    # Use parse_known_args to handle unknown arguments (the command)
    args, unknown = parser.parse_known_args()
    
    # Remove the -- separator if present
    if unknown and unknown[0] == '--':
        unknown = unknown[1:]
    
    args.command = unknown

    if not args.command:
        print("No command provided to run in the specified mode.")
        parser.print_help()
        exit(1)
    
    # Print arguments for debugging purposes
    print(f"Mode: {args.mode}, Port: {args.port}, Host: {args.host}, Command: {args.command[0] if args.command else 'None'}, Args: {args.command[1:] if len(args.command) > 1 else 'None'}")

    # Setup proxy tools first
    asyncio.run(setup_proxy_tools(args.command))
    
    # Now run the FastMCP server with proper transport
    if args.mode == "sse":
        mcp.run(transport="sse", port=args.port, host=args.host)
    elif args.mode == "http":
        mcp.run(transport="http", port=args.port, host=args.host)
    else:
        mcp.run()


if __name__ == "__main__":
    main()

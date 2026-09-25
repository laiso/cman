"""Small, dependency-free MCP stdio adapter for cman's Python functions."""

import inspect
import json
import sys
from typing import get_args, get_type_hints


def _schema(annotation):
    args = get_args(annotation)
    if args and type(None) in args:
        return {"anyOf": [_schema(arg) for arg in args if arg is not type(None)] + [{"type": "null"}]}
    return {"type": {str: "string", int: "integer", bool: "boolean", float: "number"}.get(annotation, "string")}


def _tool_description(name, function):
    signature = inspect.signature(function)
    hints = get_type_hints(function)
    properties = {}
    required = []
    for key, parameter in signature.parameters.items():
        properties[key] = _schema(hints.get(key, str))
        if parameter.default is inspect.Parameter.empty:
            required.append(key)
        else:
            properties[key]["default"] = parameter.default
    return {
        "name": name,
        "description": inspect.getdoc(function) or "",
        "inputSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    }


def serve(functions):
    descriptions = [_tool_description(name, function) for name, function in functions.items()]
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or "id" not in request:
                continue  # MCP notifications have no response.
            method = request.get("method")
            if method == "initialize":
                result = {
                    "protocolVersion": request.get("params", {}).get("protocolVersion", "2025-06-18"),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "cman", "version": "1.6.0"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": descriptions}
            elif method == "tools/call":
                params = request.get("params") or {}
                name = params.get("name")
                if name not in functions:
                    raise KeyError(f"Unknown tool: {name}")
                try:
                    output = functions[name](**(params.get("arguments") or {}))
                    result = {"content": [{"type": "text", "text": str(output)}], "isError": False}
                except (ValueError, TypeError, OSError) as error:
                    result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
            else:
                raise KeyError(f"Unknown method: {method}")
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            response = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                        "error": {"code": -32601 if isinstance(error, KeyError) else -32600, "message": str(error)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

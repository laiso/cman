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


class _RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _object(value, what):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _RpcError(-32602, f"{what} must be an object")
    return value


def _handle(request, functions, descriptions):
    method = request.get("method")
    params = _object(request.get("params"), "params")
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion") or "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "cman", "version": "1.6.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": descriptions}
    if method == "tools/call":
        name = params.get("name")
        if name not in functions:
            raise _RpcError(-32602, f"Unknown tool: {name}")
        arguments = _object(params.get("arguments"), "arguments")
        try:
            output = functions[name](**arguments)
            return {"content": [{"type": "text", "text": str(output)}], "isError": False}
        except Exception as error:  # Tool failures must not take down the server.
            return {"content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}], "isError": True}
    raise _RpcError(-32601, f"Unknown method: {method}")


def serve(functions):
    # MCP stdio is UTF-8 regardless of the platform locale (e.g. cp932 on Windows).
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8")
    descriptions = [_tool_description(name, function) for name, function in functions.items()]
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            try:
                request = json.loads(line)
            except json.JSONDecodeError as error:
                raise _RpcError(-32700, f"Parse error: {error}")
            if not isinstance(request, dict):
                raise _RpcError(-32600, "Request must be an object")
            if "id" not in request:
                continue  # MCP notifications have no response.
            request_id = request["id"]
            response = {"jsonrpc": "2.0", "id": request_id, "result": _handle(request, functions, descriptions)}
        except _RpcError as error:
            response = {"jsonrpc": "2.0", "id": request_id, "error": {"code": error.code, "message": str(error)}}
        except Exception as error:
            response = {"jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32603, "message": f"Internal error: {type(error).__name__}: {error}"}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()

from com.pnfsoftware.jeb.core.actions import ActionContext, Actions, ActionRenameData # type: ignore
from com.pnfsoftware.jeb.core import RuntimeProjectUtil # type: ignore
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit, IApkUnit, IDexDecompilerUnit # type: ignore
from com.pnfsoftware.jeb.core.units.code.java import IJavaSourceUnit, IJavaConstant # type: ignore
from com.pnfsoftware.jeb.core.units.code.android.dex import IDexClass, DexPoolType # type: ignore
from com.pnfsoftware.jeb.core.units.code import ICodeUnit, IDecompilerUnit, DecompilationContext, DecompilationOptions # type: ignore
from com.pnfsoftware.jeb.client.api import IScript # type: ignore
from com.pnfsoftware.jeb.core.util import DecompilerHelper # type: ignore
from java.lang import Runnable, Thread
from java.net import ServerSocket, Socket, SocketException, BindException
from java.io import BufferedReader, InputStreamReader, PrintWriter, IOException
import json
import time
import traceback

PORT = 8851

class MCPServer(Runnable):
    def __init__(self, dex_unit, decomp):
        self.dex_unit = dex_unit
        self.decomp = decomp
        self.server_name = "jeb-mcp-server"
        self.server_version = "1.0.0"
        self.server_socket = None
        self.resource_list = []  # Cache of all available resources and assets

        # Build the resource list when initialized
        self._build_resource_list()

        self.tools = {
            "decompile_method": {
                "description": "Decompile a method from DEX to Java source",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "method_signature": {
                            "type": "string",
                            "description": "Method signature (e.g. LClassName;->methodName(args)returnType)"
                        }
                    },
                    "required": ["method_signature"]
                }
            },
            "decompile_class": {
                "description": "Decompile an entire class to Java source",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "class_signature": {
                            "type": "string",
                            "description": "Class signature (e.g. LClassName;)"
                        }
                    },
                    "required": ["class_signature"]
                }
            },
            "implements_of_class": {
                "description": "Get implementations of a class/interface",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "class_signature": {
                            "type": "string",
                            "description": "Class signature"
                        }
                    },
                    "required": ["class_signature"]
                }
            },
            "list_classes": {
                "description": "List all classes in the DEX file with pagination",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Optional filter pattern"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting index for pagination (default: 0)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of classes to return (default: 25, max: 200)"
                        }
                    }
                }
            },
            "batch_rename": {
                "description": "Batch rename classes, methods, and fields",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "renamed_classes": {
                            "type": "object",
                            "description": "Map of class signatures to new names",
                            "additionalProperties": {"type": "string"}
                        },
                        "renamed_methods": {
                            "type": "object",
                            "description": "Map of method signatures to new names",
                            "additionalProperties": {"type": "string"}
                        },
                        "renamed_fields": {
                            "type": "object",
                            "description": "Map of field signatures to new names",
                            "additionalProperties": {"type": "string"}
                        }
                    }
                }
            },
            "batch_rename_local_variables": {
                "description": "Rename local variables across multiple methods",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "methods": {
                            "type": "array",
                            "description": "Methods with variable rename mappings",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "method_signature": {
                                        "type": "string",
                                        "description": "Method signature"
                                    },
                                    "variable_renames": {
                                        "type": "object",
                                        "description": "Old name -> new name mapping",
                                        "additionalProperties": {"type": "string"}
                                    }
                                },
                                "required": ["method_signature", "variable_renames"]
                            }
                        }
                    },
                    "required": ["methods"]
                }
            },
            "get_xrefs": {
                "description": "Get cross-references for methods, fields, or strings",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "xref_type": {
                            "type": "string",
                            "description": "Reference type",
                            "enum": ["METHOD", "FIELD", "STRING"]
                        },
                        "target": {
                            "type": "string",
                            "description": "Target signature (use Lpackage/class;-><init>()V for constructors)"
                        }
                    },
                    "required": ["xref_type", "target"]
                }
            },
            "get_manifest_file": {
                "description": "Get the AndroidManifest.xml file content with optional filtering",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "offset": {
                            "type": "integer",
                            "description": "Starting line number for pagination (default: 0). Only used when limit is specified."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of lines to return (default: unlimited). When not specified, returns full content with 20KB size limit."
                        },
                        "grep": {
                            "type": "string",
                            "description": "Search for specific text and show context around it. When used, limit applies to matched lines."
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of lines before/after grep match to show (default: 3)"
                        }
                    }
                }
            },
            "get_resource_file": {
                "description": "Get file from Resources or Assets folder with optional filtering",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the resource/asset file (e.g., 'res/layout/activity_main.xml' or 'assets/config.json')"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting line number for pagination (default: 0). Only used when limit is specified."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of lines to return (default: unlimited). When not specified, returns full content with 20KB size limit."
                        },
                        "grep": {
                            "type": "string",
                            "description": "Search for specific text and show context around it. When used, limit applies to matched lines."
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of lines before/after grep match to show (default: 3)"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            "search_resources": {
                "description": "Search for resource and asset files by regex pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to search for in file paths (e.g., '.*\\.xml$' for all XML files, 'layout/.*' for layout files)"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Starting index for pagination (default: 0)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 100)"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }

    def _get_apk_unit(self):
        """Get the APK unit from the DEX unit"""
        current_unit = self.dex_unit
        while current_unit:
            if isinstance(current_unit, IApkUnit):
                return current_unit
            current_unit = current_unit.getParent()

        prj = self.dex_unit.getParent()
        while prj and not hasattr(prj, 'findUnit'):
            prj = prj.getParent()
        return prj.findUnit(IApkUnit) if prj else None

    def _build_resource_list(self):
        try:
            apk_unit = self._get_apk_unit()
            if not apk_unit:
                print("[MCP] Warning: Could not find APK unit. Resource list will be empty.")
                return

            resources = apk_unit.getResources()
            if resources:
                self._traverse_units(resources, "res/")

            assets = apk_unit.getAssets()
            if assets:
                self._traverse_units(assets, "assets/")

            print("[MCP] Built resource list: %d files found" % len(self.resource_list))
        except Exception as e:
            print("[MCP] Error building resource list: " + str(e))
            traceback.print_exc()

    def _traverse_units(self, unit, prefix):
        try:
            children = unit.getChildren()
            if not children:
                if prefix != "res/" and prefix != "assets/":
                    self.resource_list.append(prefix.rstrip('/'))
                return

            for child in children:
                child_name = child.getName()
                child_path = prefix + child_name
                child_children = child.getChildren()

                if child_children and len(list(child_children)) > 0:
                    self._traverse_units(child, child_path + "/")
                else:
                    self.resource_list.append(child_path)
        except Exception as e:
            print("[MCP] Error traversing units at %s: %s" % (prefix, str(e)))

    def send_stop_request(self, port):
        client = None
        try:
            print("[MCP] Stopping existing server on port %d..." % port)
            client = Socket("localhost", port)
            client.setSoTimeout(5000)
            output_writer = PrintWriter(client.getOutputStream(), True)
            stop_request = {"jsonrpc": "2.0", "method": "stop_server", "id": 1}
            output_writer.println(json.dumps(stop_request))
            output_writer.flush()
            time.sleep(1)
            return True
        except Exception as e:
            print("[MCP] Could not stop server: " + str(e))
            return False
        finally:
            if client:
                try:
                    client.close()
                except Exception as e:
                    print("[MCP] Error closing client socket: " + str(e))

    def run(self):
        max_retries = 2
        retry_count = 0

        while retry_count < max_retries:
            try:
                self.server_socket = ServerSocket(PORT)
                self.server_socket.setReuseAddress(True)
                print("[MCP] Server listening on port %d" % PORT)

                while True:
                    try:
                        client_socket = self.server_socket.accept()
                        print("[MCP] Client connected: " + str(client_socket.getRemoteSocketAddress()))
                        handler = MCPClientHandler(client_socket, self)
                        thread = Thread(handler)
                        thread.setDaemon(True)
                        thread.start()
                    except SocketException as e:
                        if self.server_socket and self.server_socket.isClosed():
                            break
                    except Exception as e:
                        print("[MCP] Accept error: " + str(e))

                break

            except BindException as e:
                print("[MCP] Port %d already in use" % PORT)
                if retry_count < max_retries - 1:
                    if self.send_stop_request(PORT):
                        retry_count += 1
                        time.sleep(2)
                    else:
                        print("[MCP] Failed to stop existing server")
                        break
                else:
                    print("[MCP] Max retries reached")
                    break

            except Exception as e:
                print("[MCP] Server error: " + str(e))
                traceback.print_exc()
                break
            finally:
                if self.server_socket and not self.server_socket.isClosed():
                    try:
                        self.server_socket.close()
                    except Exception as e:
                        print("[MCP] Error closing server socket: " + str(e))
                    self.server_socket = None


class MCPClientHandler(Runnable):
    def __init__(self, client_socket, mcp_server):
        self.client_socket = client_socket
        self.mcp_server = mcp_server
    
    def run(self):
        input_reader = None
        output_writer = None

        try:
            input_stream = self.client_socket.getInputStream()
            input_reader = BufferedReader(InputStreamReader(input_stream, "UTF-8"))
            output_stream = self.client_socket.getOutputStream()
            output_writer = PrintWriter(output_stream, True)

            while True:
                request_line = input_reader.readLine()
                if not request_line:
                    break

                try:
                    request = json.loads(request_line)
                    response = self.handle_request(request)

                    if response is not None:
                        output_writer.println(json.dumps(response))
                        output_writer.flush()

                except ValueError as e:
                    error_response = self.error_response(None, -32700, "Parse error: " + str(e))
                    output_writer.println(json.dumps(error_response))
                    output_writer.flush()
                except Exception as e:
                    print("[MCP] Request error: " + str(e))
                    traceback.print_exc()
                    error_response = self.error_response(None, -32603, "Internal error: " + str(e))
                    output_writer.println(json.dumps(error_response))
                    output_writer.flush()

        except SocketException:
            pass  # client disconnected
        except IOException as e:
            print("[MCP] IO error: " + str(e.getMessage()))
        except Exception as e:
            print("[MCP] Handler error: " + str(e))
            traceback.print_exc()
        finally:
            try:
                if output_writer:
                    output_writer.close()
            except Exception as e:
                print("[MCP] Error closing output writer: " + str(e))
            try:
                if input_reader:
                    input_reader.close()
            except Exception as e:
                print("[MCP] Error closing input reader: " + str(e))
            try:
                if self.client_socket and not self.client_socket.isClosed():
                    self.client_socket.close()
            except Exception as e:
                print("[MCP] Error closing client socket: " + str(e))
    
    def handle_request(self, request):
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if request_id is None and method == "notifications/initialized":
            return None

        if method == "initialize":
            return self.handle_initialize(request_id, params)
        elif method == "tools/list":
            return self.handle_tools_list(request_id)
        elif method == "tools/call":
            return self.handle_tool_call(request_id, params)
        elif method == "stop_server":
            return self.handle_stop_server(request_id)
        elif method == "prompts/list":
            return self.error_response(request_id, -32601, "Method not found: prompts/list")
        else:
            return self.error_response(request_id, -32601, "Method not found: " + str(method))
    
    def handle_initialize(self, request_id, params):
        return self._success_response(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": self.mcp_server.server_name,
                "version": self.mcp_server.server_version
            }
        })
    
    def handle_tools_list(self, request_id):
        tools_list = [
            {
                "name": name,
                "description": info["description"],
                "inputSchema": info["inputSchema"]
            }
            for name, info in self.mcp_server.tools.items()
        ]

        return self._success_response(request_id, {"tools": tools_list})
    
    def handle_tool_call(self, request_id, params):
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "decompile_method":
                result = self.decompile_method(arguments.get("method_signature"))
            elif tool_name == "decompile_class":
                result = self.decompile_class(arguments.get("class_signature"))
            elif tool_name == "implements_of_class":
                result = self.class_implementations(arguments.get("class_signature"))
            elif tool_name == "list_classes":
                result = self.list_classes(
                    arguments.get("filter"),
                    arguments.get("offset", 0),
                    arguments.get("limit", 25)
                )
            elif tool_name == "batch_rename":
                result = self.batch_rename(
                    arguments.get("renamed_classes", {}),
                    arguments.get("renamed_methods", {}),
                    arguments.get("renamed_fields", {})
                )
            elif tool_name == "batch_rename_local_variables":
                result = self.batch_rename_local_variables(arguments.get("methods", []))
            elif tool_name == "get_xrefs":
                result = self.get_xrefs(arguments.get("xref_type"), arguments.get("target"))
            elif tool_name == "get_manifest_file":
                result = self.get_manifest_file(
                    arguments.get("offset", 0),
                    arguments.get("limit"),
                    arguments.get("grep"),
                    arguments.get("context_lines", 3)
                )
            elif tool_name == "get_resource_file":
                result = self.get_resource_file(
                    arguments.get("file_path"),
                    arguments.get("offset", 0),
                    arguments.get("limit"),
                    arguments.get("grep"),
                    arguments.get("context_lines", 3)
                )
            elif tool_name == "search_resources":
                result = self.search_resources(
                    arguments.get("pattern"),
                    arguments.get("offset", 0),
                    arguments.get("limit", 100)
                )
            else:
                return self.error_response(request_id, -32602, "Unknown tool: " + tool_name)

            return self._tool_result_response(request_id, result)
        except Exception as e:
            print("[MCP] Tool error: " + str(e))
            traceback.print_exc()
            return self.error_response(request_id, -32603, "Tool execution failed: " + str(e))

    def _get_mime_type(self, file_path):
        ext_map = {
            '.xml': "application/xml",
            '.json': "application/json",
            '.png': "image/png",
            '.jpg': "image/jpeg",
            '.jpeg': "image/jpeg",
            '.txt': "text/plain",
            '.html': "text/html",
            '.js': "application/javascript",
            '.css': "text/css"
        }
        for ext, mime in ext_map.items():
            if file_path.endswith(ext):
                return mime
        return "application/octet-stream"

    def handle_stop_server(self, request_id):
        print("[MCP] Stop request received")
        try:
            if self.mcp_server.server_socket and not self.mcp_server.server_socket.isClosed():
                self.mcp_server.server_socket.close()
            return self._success_response(request_id, {
                "status": "stopped",
                "message": "Server is shutting down"
            })
        except Exception as e:
            return self.error_response(request_id, -32603, "Failed to stop server: " + str(e))

    def decompile_method(self, method_signature):
        decomp = self.mcp_server.decomp
        opt = self._get_decompilation_options()

        try:
            if not decomp.decompileMethod(method_signature, DecompilationContext(opt)):
                return "Failed to decompile: " + method_signature

            text = decomp.getDecompiledMethodText(method_signature)
            return text if text else "Decompiled text is empty"
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def decompile_class(self, class_signature):
        decomp = self.mcp_server.decomp
        opt = self._get_decompilation_options()

        try:
            if not decomp.decompileClass(class_signature, DecompilationContext(opt)):
                return "Failed to decompile: " + class_signature

            text = decomp.getDecompiledClassText(class_signature)
            return text if text else "Decompiled text is empty"
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)
    
    def class_implementations(self, signature):
        unit = self.mcp_server.dex_unit
        if isinstance(unit.getParent(), IDexDecompilerUnit):
            unit = unit.getParent().getParent()
        elif not isinstance(unit, IDexUnit):
            return "Cannot retrieve DEX unit"

        # TODO: make depth configurable
        children = unit.getTypeHierarchy(signature, 10000, True).getChildren()
        results = []
        for child in children:
            sig = str(child).split("address=")[1].split("]")[0]
            results.append(sig)
        return "\n".join(results)
    
    def list_classes(self, filter_pattern, offset=0, limit=25):
        try:
            offset = max(0, offset)
            limit = max(1, min(limit, 200))

            classes = self.mcp_server.dex_unit.getClasses()
            class_list = [cls.getSignature(False) for cls in classes
                         if not filter_pattern or filter_pattern in cls.getSignature(False)]

            total_count = len(class_list)
            paginated_list = class_list[offset:offset + limit]

            result = "Found %d classes total" % total_count
            if filter_pattern:
                result += " (filtered by: '%s')" % filter_pattern
            result += "\nShowing %d-%d:\n\n" % (offset, min(offset + limit, total_count))

            if paginated_list:
                result += "\n".join(paginated_list)
                if offset + limit < total_count:
                    result += "\n\n--- More available ---"
                    result += "\nNext page: offset=%d, limit=%d" % (offset + limit, limit)
                    result += "\nRemaining: %d classes" % (total_count - offset - limit)
            else:
                result += "(no results in this range)"

            return result
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def batch_rename(self, renamed_classes, renamed_methods, renamed_fields):
        dex_unit = self.mcp_server.dex_unit
        results = {"classes_renamed": 0, "methods_renamed": 0, "fields_renamed": 0, "errors": []}

        try:
            if not dex_unit.isProcessed():
                return "DEX unit not processed yet"

            for sig, name in renamed_classes.items():
                try:
                    cls = dex_unit.getClass(sig)
                    if cls:
                        cls.setName(name)
                        results["classes_renamed"] += 1
                    else:
                        results["errors"].append("Class not found: %s" % sig)
                except Exception as e:
                    results["errors"].append("Class rename failed %s: %s" % (sig, str(e)))

            for sig, name in renamed_fields.items():
                try:
                    field = dex_unit.getField(sig)
                    if field:
                        field.setName(name)
                        results["fields_renamed"] += 1
                    else:
                        results["errors"].append("Field not found: %s" % sig)
                except Exception as e:
                    results["errors"].append("Field rename failed %s: %s" % (sig, str(e)))

            for sig, name in renamed_methods.items():
                try:
                    method = dex_unit.getMethod(sig)
                    if method:
                        method.setName(name)
                        results["methods_renamed"] += 1
                    else:
                        results["errors"].append("Method not found: %s" % sig)
                except Exception as e:
                    results["errors"].append("Method rename failed %s: %s" % (sig, str(e)))

            msg = "Batch rename:\n"
            msg += "- Classes: %d/%d\n" % (results["classes_renamed"], len(renamed_classes))
            msg += "- Methods: %d/%d\n" % (results["methods_renamed"], len(renamed_methods))
            msg += "- Fields: %d/%d\n" % (results["fields_renamed"], len(renamed_fields))
            msg += self._format_error_list(results["errors"])

            return msg
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def batch_rename_local_variables(self, methods):
        if not methods:
            return "No methods provided"

        dex_unit = self.mcp_server.dex_unit
        decomp = self.mcp_server.decomp
        results = {"methods_processed": 0, "variables_renamed": 0, "errors": []}

        try:
            dex_decomp = dex_unit.getParent() if isinstance(dex_unit.getParent(), IDexDecompilerUnit) else decomp

            for method_info in methods:
                method_sig = method_info.get("method_signature")
                var_renames = method_info.get("variable_renames", {})

                if not method_sig or not var_renames:
                    results["errors"].append("Missing signature or renames for method")
                    continue

                try:
                    java_method = dex_decomp.getMethod(method_sig, False)
                    if not java_method:
                        results["errors"].append("Method not found: %s" % method_sig)
                        continue

                    ident_mgr = java_method.getIdentifierManager()
                    if not ident_mgr:
                        results["errors"].append("No ident manager: %s" % method_sig)
                        continue

                    vars_renamed = 0
                    for old, new in var_renames.items():
                        try:
                            ident = ident_mgr.getIdentifier(old)
                            if ident:
                                dex_decomp.setIdentifierName(ident, new)
                                vars_renamed += 1
                                results["variables_renamed"] += 1
                            else:
                                results["errors"].append("Var '%s' not found in %s" % (old, method_sig))
                        except Exception as e:
                            results["errors"].append("Var rename error %s->%s: %s" % (old, new, str(e)))

                    if vars_renamed > 0:
                        results["methods_processed"] += 1

                except Exception as e:
                    results["errors"].append("Method error %s: %s" % (method_sig, str(e)))
                    traceback.print_exc()

            msg = "Batch rename variables:\n"
            msg += "- Methods: %d/%d\n" % (results["methods_processed"], len(methods))
            msg += "- Variables: %d\n" % results["variables_renamed"]
            msg += self._format_error_list(results["errors"])

            return msg
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def _apply_grep_filter(self, content, grep_pattern, context_lines=3):
        if not grep_pattern:
            return content

        lines = content.split('\n')
        matching_ranges = set()

        for i, line in enumerate(lines):
            if grep_pattern in line:
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                for j in range(start, end):
                    matching_ranges.add(j)

        if not matching_ranges:
            return "No matches found for pattern: '%s'" % grep_pattern

        sorted_ranges = sorted(matching_ranges)
        result_lines = []
        prev_line = -2

        for line_num in sorted_ranges:
            if line_num > prev_line + 1:
                result_lines.append("---")

            line_content = lines[line_num]
            if grep_pattern in line_content:
                result_lines.append("[%d]* %s" % (line_num + 1, line_content))
            else:
                result_lines.append("[%d]  %s" % (line_num + 1, line_content))
            prev_line = line_num

        header = "Found %d matching lines for pattern: '%s'\n\n" % (
            sum(1 for l in lines if grep_pattern in l), grep_pattern
        )
        return header + '\n'.join(result_lines)

    def _limit_content_size(self, content, max_size):
        if max_size == -1 or len(content) <= max_size:
            return content

        truncated = content[:max_size]
        remaining = len(content) - max_size
        return truncated + "\n\n... [TRUNCATED: %d more bytes available]" % remaining

    def _apply_line_pagination(self, content, offset, limit, file_name="file"):
        offset = max(0, offset)
        limit = max(1, limit) if limit else None

        lines = content.split('\n')
        total_lines = len(lines)

        if offset >= total_lines:
            return "No lines in this range (offset: %d, limit: %d)\n\nTotal lines in %s: %d" % (
                offset, limit, file_name, total_lines
            )

        end_line = offset + limit if limit else total_lines
        paginated_lines = lines[offset:end_line]

        result = "File: %s\n" % file_name
        result += "Total lines: %d\n" % total_lines
        result += "Showing lines %d-%d:\n\n" % (offset + 1, min(end_line, total_lines))
        result += '\n'.join(paginated_lines)

        if end_line < total_lines:
            result += "\n\n--- More available ---\n"
            result += "Next page: offset=%d, limit=%d\n" % (end_line, limit)
            result += "Remaining: %d lines" % (total_lines - end_line)

        return result

    def get_xrefs(self, xref_type, target):
        dex_unit = self.mcp_server.dex_unit
        pool_type_map = {
            "METHOD": DexPoolType.METHOD,
            "FIELD": DexPoolType.FIELD,
            "STRING": DexPoolType.STRING
        }

        pool_type = pool_type_map.get(xref_type)
        if not pool_type:
            return "Invalid xref_type. Use: METHOD, FIELD, or STRING"

        try:
            item_index = None
            if xref_type == "METHOD":
                method = dex_unit.getMethod(target)
                item_index = method.getIndex() if method else None
            elif xref_type == "FIELD":
                field = dex_unit.getField(target)
                item_index = field.getIndex() if field else None
            elif xref_type == "STRING":
                item_index = dex_unit.findStringIndex(target)

            if item_index is None or item_index < 0:
                return "%s not found: %s" % (xref_type, target)

            ref_mgr = dex_unit.getReferenceManager()
            xrefs = ref_mgr.getReferences(pool_type, item_index, 0)

            if not xrefs or xrefs.size() == 0:
                return "No xrefs for %s: %s" % (xref_type, target)

            result = "Found %d xrefs for %s: %s\n\n" % (xrefs.size(), xref_type, target)
            for xref in xrefs:
                result += xref.getInternalAddress() + " TYPE:" + xref.getReferenceType().toString() + "\n"
            return result

        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def get_manifest_file(self, offset=0, limit=None, grep_pattern=None, context_lines=3):
        try:
            apk_unit = self._get_apk_unit()
            if not apk_unit:
                return "Error: Could not find APK unit. This tool requires an APK file to be loaded."

            manifest_unit = apk_unit.getManifest()
            if not manifest_unit:
                return "Error: Could not retrieve manifest from APK"

            manifest_content = manifest_unit.getDocumentAsText()
            if not manifest_content or len(manifest_content) < 10:
                methods = [m for m in dir(manifest_unit) if not m.startswith('_')]
                return "Error: Could not retrieve manifest content.\nAvailable methods: " + ", ".join(methods[:20])

            return self._apply_content_filters(manifest_content, "AndroidManifest.xml",
                                              offset, limit, grep_pattern, context_lines)
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def get_resource_file(self, file_path, offset=0, limit=None, grep_pattern=None, context_lines=3):
        try:
            if not file_path:
                return "Error: file_path parameter is required"

            apk_unit = self._get_apk_unit()
            if not apk_unit:
                return "Error: Could not find APK unit. This tool requires an APK file to be loaded."

            normalized_path = file_path.lstrip('/')
            container = None
            relative_path = normalized_path

            if normalized_path.startswith("res/"):
                container = apk_unit.getResources()
                relative_path = normalized_path[4:]
            elif normalized_path.startswith("assets/"):
                container = apk_unit.getAssets()
                relative_path = normalized_path[7:]
            else:
                return "Error: Resource directory not found: %s\nTip: Use paths like 'res/layout/activity_main.xml' or 'assets/config.json'" % file_path

            resource_unit = self._find_unit_by_path(container, relative_path)
            if not resource_unit:
                return "Error: Resource file not found: %s\nTip: Use paths like 'res/layout/activity_main.xml' or 'assets/config.json'" % file_path

            content = self._read_unit_content(resource_unit, file_path)
            if content.startswith("Error: Could not read content from resource file"):
                return content
            if content.startswith("Binary file"):
                return content

            file_name = file_path.split('/')[-1]
            return self._apply_content_filters(content, file_name,
                                              offset, limit, grep_pattern, context_lines)
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def _find_unit_by_path(self, container, path):
        parts = path.split('/')
        current = container

        for part in parts:
            if not current:
                return None

            children = current.getChildren()
            if not children:
                return None

            found = False
            for child in children:
                if child.getName() == part:
                    current = child
                    found = True
                    break

            if not found:
                return None

        return current

    def search_resources(self, pattern, offset=0, limit=100):
        import re
        try:
            if not pattern:
                return "Error: pattern parameter is required"

            offset = max(0, offset)
            limit = max(1, limit)

            try:
                regex = re.compile(pattern)
            except Exception as e:
                return "Error: Invalid regex pattern: " + str(e)

            all_matches = [p for p in self.mcp_server.resource_list if regex.search(p)]

            if not all_matches:
                return "No resources found matching pattern: '%s'\n\nTotal available resources: %d" % (
                    pattern, len(self.mcp_server.resource_list)
                )

            total_matches = len(all_matches)
            paginated_matches = all_matches[offset:offset + limit]

            if not paginated_matches:
                return "No resources in this range (offset: %d, limit: %d)\n\nTotal matches for pattern '%s': %d" % (
                    offset, limit, pattern, total_matches
                )

            result = "Found %d resources total matching pattern: '%s'\n" % (total_matches, pattern)
            result += "Showing %d-%d:\n\n" % (offset, min(offset + limit, total_matches))

            res_files = [m for m in paginated_matches if m.startswith("res/")]
            asset_files = [m for m in paginated_matches if m.startswith("assets/")]

            if res_files:
                result += "Resources (%d):\n" % len(res_files)
                for f in res_files:
                    result += "  - %s\n" % f
                result += "\n"

            if asset_files:
                result += "Assets (%d):\n" % len(asset_files)
                for f in asset_files:
                    result += "  - %s\n" % f
                result += "\n"

            if offset + limit < total_matches:
                result += "--- More available ---\n"
                result += "Next page: offset=%d, limit=%d\n" % (offset + limit, limit)
                result += "Remaining: %d resources" % (total_matches - offset - limit)

            return result.rstrip()
        except Exception as e:
            traceback.print_exc()
            return "Error: " + str(e)

    def _read_unit_content(self, unit, file_path):
        from com.pnfsoftware.jeb.core.units import IXmlUnit  # type: ignore
        from java.nio import ByteBuffer  # type: ignore

        if isinstance(unit, IXmlUnit):
            try:
                doc = unit.getDocument()
                if doc and hasattr(doc, 'getDocumentAsText'):
                    content = doc.getDocumentAsText()
                    if content:
                        return str(content)
            except Exception:
                pass

        try:
            input_obj = unit.getInput()
            if input_obj:
                size = input_obj.getCurrentSize()
                channel = input_obj.getChannel()
                if channel:
                    try:
                        buffer = ByteBuffer.allocate(int(size))
                        channel.read(buffer)
                        buffer.flip()

                        from jarray import zeros  # type: ignore
                        java_byte_array = zeros(int(size), 'b')
                        buffer.get(java_byte_array)
                        data = bytes(bytearray([b & 0xff for b in java_byte_array]))

                        try:
                            return data.decode('utf-8')
                        except UnicodeDecodeError:
                            from java.util import Base64  # type: ignore
                            encoded = Base64.getEncoder().encodeToString(java_byte_array)
                            return "Binary file (base64 encoded, %d bytes):\n%s" % (size, str(encoded))
                    finally:
                        if channel:
                            try:
                                channel.close()
                            except Exception as e:
                                print("[MCP] Error closing channel: " + str(e))
        except Exception:
            pass

        return "Error: Could not read content from resource file: " + file_path

    def _success_response(self, request_id, result):
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _tool_result_response(self, request_id, text):
        return self._success_response(request_id, {"content": [{"type": "text", "text": text}]})

    def error_response(self, request_id, code, message):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _get_apk_unit(self):
        return self.mcp_server._get_apk_unit()

    def _get_decompilation_options(self):
        return DecompilationOptions.Builder.newInstance() \
            .flags(IDecompilerUnit.FLAG_NO_INNER_DECOMPILATION | IDecompilerUnit.FLAG_NO_DEFERRED_DECOMPILATION) \
            .maxTimePerMethod(30000) \
            .build()

    def _format_error_list(self, errors, max_display=10):
        if not errors:
            return ""
        msg = "\nErrors (%d):\n" % len(errors)
        for error in errors[:max_display]:
            msg += "  - %s\n" % error
        if len(errors) > max_display:
            msg += "  ... %d more\n" % (len(errors) - max_display)
        return msg

    def _apply_content_filters(self, content, file_name, offset=0, limit=None,
                              grep_pattern=None, context_lines=3, default_size_limit=20000):
        if grep_pattern:
            content = self._apply_grep_filter(content, grep_pattern, context_lines)
            if limit is not None:
                content = self._apply_line_pagination(content, offset, limit, file_name)
        elif limit is not None:
            content = self._apply_line_pagination(content, offset, limit, file_name)
        else:
            content = self._limit_content_size(content, default_size_limit)
        return content


class dJEB_mcp_server(IScript):
    def run(self, ctx):
        self.ctx = ctx
        
        prj = ctx.getMainProject()
        assert prj, 'Need a project'

        # Get the dex unit and decompiler
        unit = ctx.getFocusedUnit()
        if isinstance(unit.getParent(), IDexDecompilerUnit):
            dex_unit = unit.getParent().getParent()
        elif isinstance(unit, IDexUnit):
            dex_unit = unit
        else:
            print("Cannot retrieve the Dex unit")
            return
        
        decomp = DecompilerHelper.getDecompiler(dex_unit)
        if not decomp:
            print('Cannot acquire decompiler for unit')
            return
        
        print("=" * 70)
        print("Starting JEB MCP Server...")
        server = MCPServer(dex_unit, decomp)
        thread = Thread(server)
        thread.setDaemon(True)
        thread.start()

        print("MCP Server running on port %d" % PORT)
        print("=" * 70)
        print("\nTools:")
        print("  - decompile_method")
        print("  - decompile_class")
        print("  - list_classes")
        print("  - batch_rename")
        print("  - batch_rename_local_variables")
        print("  - get_xrefs")
        print("  - get_manifest_file")
        print("  - get_resource_file")
        print("  - search_resources (NEW)")
        print("\nConnect with Claude Desktop")
        print("=" * 70)
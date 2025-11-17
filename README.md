# JEB MCP Server

A Model Context Protocol (MCP) server that bridges Claude Desktop with JEB decompiler for Android APK analysis. This integration enables AI-assisted reverse engineering workflows directly within Claude.

## Features

- **Decompilation**: Decompile methods and classes from DEX to Java source code
- **Code Navigation**: List classes, search resources, and explore cross-references
- **Batch Renaming**: Rename classes, methods, fields, and local variables in bulk
- **Resource Analysis**: Access AndroidManifest.xml, resources, and asset files
- **Cross-References**: Find all references to methods, fields, and strings
- **Class Hierarchy**: Explore class implementations and inheritance

## Architecture

The system consists of two components:

1. **JEB MCP Server** (`dJEB_mcp_server.py`): Runs inside JEB as a Jython script, exposing JEB's API over a socket
2. **Bridge Script** (`jeb_mcp_bridge.py`): Connects Claude Desktop to the JEB server via stdio

```
Claude Desktop <--> jeb_mcp_bridge.py <--> (port 8851) <--> dJEB_mcp_server.py (JEB)
```

## Installation

### Prerequisites

- JEB Decompiler (licensed version)
- Claude Desktop

### Setup

1. **Clone this repository**:
   ```bash
   git clone https://github.com/yourusername/jeb-mcp-server.git
   cd jeb-mcp-server
   ```

2. **Configure Claude Desktop**:

   Edit your Claude Desktop MCP configuration file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

   Add the following configuration:
   ```json
   {
     "mcpServers": {
       "jeb-mcp-server": {
         "command": "python3",
         "args": ["/absolute/path/to/jeb-mcp-server/jeb_mcp_bridge.py"]
       }
     }
   }
   ```

3. **Load the script in JEB**:
   - Open JEB Decompiler
   - Load your target APK file
   - Run the script: `File` → `Scripts` → `Run Script...` → Select `dJEB_mcp_server.py`
   - The server will start listening on port 8851

4. **Restart Claude Desktop** to load the MCP server configuration

## Usage

Once configured, you can interact with JEB through Claude Desktop using natural language. The server provides the following tools:

### Available Tools

| Tool | Description |
|------|-------------|
| `decompile_method` | Decompile a specific method to Java source |
| `decompile_class` | Decompile an entire class to Java source |
| `list_classes` | List all classes with optional filtering and pagination |
| `implements_of_class` | Get all implementations of a class/interface |
| `get_xrefs` | Get cross-references for methods, fields, or strings |
| `batch_rename` | Rename multiple classes, methods, and fields at once |
| `batch_rename_local_variables` | Rename local variables across multiple methods |
| `get_manifest_file` | Retrieve and search AndroidManifest.xml |
| `get_resource_file` | Access resource files (layouts, strings, etc.) |
| `search_resources` | Search for resource files using regex patterns |

## Example Prompts

Here are powerful prompts you can use with the JEB MCP Server:

### 1. Deep-Link Analysis

**Prompt:**
```
Analyze the deep-link handling in this Android application step-by-step.
I want you to:
1. Find all activities that handle intent filters with data schemes
2. For each deep-link handler, trace the URL parsing logic
3. Extract all possible endpoints and their parameters
4. Ignore any analytics or tracking code
5. Create a comprehensive map of all deep-link endpoints with their functionality

Please be thorough and explore all related classes.
```

### 2. Intelligent Class Renaming

**Prompt:**
```
I want to rename the obfuscated class "La/b/c;" and its methods to meaningful names.

Please:
1. Decompile the class and analyze its purpose
2. Find all classes that reference or are referenced by this class
3. Examine the broader context by looking at:
   - Parent classes and interfaces
   - Classes that call its methods
   - Classes instantiated within it
4. Only rename elements you're confident about based on:
   - Method functionality
   - String constants used
   - Android framework patterns
   - Common design patterns
5. Provide the rename mappings with explanations
6. Execute the batch rename operation

Be conservative - only rename what you're certain about.
```

### 3. API Endpoint Extraction

**Prompt:**
```
Extract all REST API endpoints used by this application.

Please:
1. Find all HTTP client usage (Retrofit, OkHttp, HttpURLConnection, etc.)
2. Locate API interface definitions or base URL constants
3. For each endpoint, extract:
   - HTTP method (GET, POST, etc.)
   - Full URL path
   - Request parameters
   - Response handling
4. Group endpoints by feature/module
5. Create an API documentation with examples

Focus on actual API calls, ignore logging or analytics.
```

### 4. Broadcast Receiver Analysis

**Prompt:**
```
Analyze all broadcast receivers in this application.

For each receiver:
1. Identify what intents it listens for
2. Explain what actions it performs
3. Check if it's exported and the security implications
4. Find where broadcasts are sent from within the app
5. Map the complete broadcast communication flow

Document any security concerns with exported receivers.
```


### 5. Cross-Reference Tracing

Follow the execution flow:
```
"Starting from the MainActivity onCreate method, trace all
method calls related to user login, and map the complete
authentication flow with all classes involved."
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development

The codebase consists of:
- **Jython code** (`dJEB_mcp_server.py`): Runs inside JEB's Jython environment
- **Python 3 code** (`jeb_mcp_bridge.py`): Standard Python stdio bridge

When contributing: Maintain compatibility with JEB's Jython 2.7 environment

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- Integrates with [JEB Decompiler](https://www.pnfsoftware.com/) by PNF Software
- Inspired by the need for AI-assisted reverse engineering workflows

## Support

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Note**: This is an unofficial tool and is not affiliated with or endorsed by PNF Software or Anthropic.

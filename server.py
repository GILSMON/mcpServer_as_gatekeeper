import asyncio
import re
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource 

app = Server("file-manager")

PROTECTED_DIR = Path("/Users/gilsmonpcherian/Documents/programs/RapidLabs/TalentX")

def enforce_naming_convention(filename: str) -> tuple[str, str]:
    """
    Enforce organizational naming convention: convert to snake_case.
    Returns: (normalized_filename, explanation)
    """
    # Get the filename without path
    path_parts = filename.split('/')
    original_name = path_parts[-1]
    
    # Split name and extension
    if '.' in original_name:
        name_part, extension = original_name.rsplit('.', 1)
    else:
        name_part = original_name
        extension = ''
    
    # Convert to snake_case
    # 1. Replace spaces and hyphens with underscores
    normalized = name_part.replace(' ', '_').replace('-', '_')
    
    # 2. Insert underscore before capital letters (camelCase -> snake_case)
    normalized = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', normalized)
    normalized = re.sub('([a-z0-9])([A-Z])', r'\1_\2', normalized)
    
    # 3. Convert to lowercase
    normalized = normalized.lower()
    
    # 4. Remove consecutive underscores
    normalized = re.sub('_+', '_', normalized)
    
    # 5. Remove leading/trailing underscores
    normalized = normalized.strip('_')
    
    # Reconstruct full filename
    if extension:
        normalized_filename = f"{normalized}.{extension}"
    else:
        normalized_filename = normalized
    
    # Reconstruct full path
    if len(path_parts) > 1:
        path_parts[-1] = normalized_filename
        full_normalized = '/'.join(path_parts)
    else:
        full_normalized = normalized_filename
    
    # Create explanation if name was changed
    if original_name != normalized_filename:
        explanation = f"📝 Naming convention applied: '{original_name}' → '{normalized_filename}'"
    else:
        explanation = f"✓ Filename already follows convention: '{normalized_filename}'"
    
    return full_normalized, explanation

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_file",
            description="Create a new file (automatically applies snake_case naming convention)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Desired file path (will be normalized to snake_case)"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content",
                        "default": ""
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_file",
            description="Read contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write to an existing file (naming convention enforced on creation only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="delete_file",
            description="Delete a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_files",
            description="List all files in directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": ""}
                }
            }
        )
    ]

def resolve_path(relative_path: str) -> Path:
    full_path = (PROTECTED_DIR / relative_path).resolve()
    if not str(full_path).startswith(str(PROTECTED_DIR)):
        raise ValueError("Access denied: Path outside protected directory")
    return full_path

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "create_file":
            # Apply naming convention
            requested_path = arguments["path"]
            normalized_path, explanation = enforce_naming_convention(requested_path)
            
            path = resolve_path(normalized_path)
            content = arguments.get("content", "")
            
            # Check if file already exists
            if path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{normalized_path}' already exists. Use write_file to update it."
                )]
            
            # Create directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create the file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Return success message with naming convention info
            message = f"{explanation}\n✓ File created successfully: {normalized_path}"
            return [TextContent(type="text", text=message)]
        
        elif name == "read_file":
            path = resolve_path(arguments["path"])
            if not path.exists():
                return [TextContent(type="text", text=f"Error: File '{arguments['path']}' not found")]
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [TextContent(type="text", text=content)]
        
        elif name == "write_file":
            path = resolve_path(arguments["path"])
            
            if not path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{arguments['path']}' does not exist. Use create_file to create new files."
                )]
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(arguments["content"])
            return [TextContent(type="text", text=f"✓ File updated: {arguments['path']}")]
        
        elif name == "delete_file":
            path = resolve_path(arguments["path"])
            
            if not path.exists():
                return [TextContent(type="text", text=f"Error: File '{arguments['path']}' not found")]
            
            path.unlink()
            return [TextContent(type="text", text=f"✓ File deleted: {arguments['path']}")]
        
        elif name == "list_files":
            dir_path = resolve_path(arguments.get("path", ""))
            if not dir_path.exists():
                return [TextContent(type="text", text="Error: Directory not found")]
            
            files = []
            for item in dir_path.rglob("*"):
                if item.is_file():
                    files.append(str(item.relative_to(PROTECTED_DIR)))
            
            return [TextContent(type="text", text="\n".join(sorted(files)) if files else "No files found")]
        
        else:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri=str(PROTECTED_DIR.as_uri()),
            name="TalentX Workspace",
            description="Main protected directory managed by file-manager",
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> list[TextContent]:
    try:
        path = Path(uri.replace("file://", ""))
        if path.is_dir():
            files = [p.name for p in path.iterdir()]
            return [TextContent(type="text", text="\n".join(files))]
        elif path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return [TextContent(type="text", text=f.read())]
        else:
            return [TextContent(type="text", text="Unknown resource type")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error reading resource: {e}")]
    
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
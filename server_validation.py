#!/usr/bin/env python3
"""
MCP Server for Command Validation
Intercepts shell commands and enforces organizational policies
"""

import asyncio
import json
import re
from typing import Any
from mcp.server import Server
from mcp.types import Tool, TextContent, ErrorData
import mcp.server.stdio

# Policy Rules Configuration
POLICY_RULES = {
    "destructive_commands": {
        "patterns": [
            r"\brm\s+-rf\s+/",  # rm -rf /
            r"\brm\s+-rf\s+\*",  # rm -rf *
            r"\bdd\s+.*of=/dev/",  # dd to device
            r"\bmkfs\.",  # filesystem formatting
            r"\b:(){:|:&};:",  # fork bomb
            r"\bchmod\s+-R\s+777",  # dangerous permissions
        ],
        "message": "Destructive command blocked by ORG-SEC-001"
    },
    "network_exfiltration": {
        "patterns": [
            r"curl\s+.*\|\s*bash",  # curl pipe to bash
            r"wget\s+.*\|\s*sh",  # wget pipe to shell
            r"nc\s+-l",  # netcat listener
            r"python.*-m\s+http\.server",  # simple http server
        ],
        "message": "Network exfiltration risk blocked by ORG-SEC-002"
    },
    "system_modification": {
        "patterns": [
            r"\bsudo\s+rm",  # sudo rm
            r"\bapt-get\s+remove",  # package removal
            r"\byum\s+remove",
            r"\bsystemctl\s+stop",  # stopping services
            r"\bkill\s+-9\s+1",  # killing init
        ],
        "message": "System modification requires approval - ORG-OPS-003"
    },
    "sensitive_paths": {
        "patterns": [
            r"/etc/passwd",
            r"/etc/shadow",
            r"\.ssh/id_rsa",
            r"\.aws/credentials",
            r"\.env",
        ],
        "message": "Access to sensitive files blocked - ORG-SEC-004"
    }
}

# Allowlist for safe commands
ALLOWED_COMMANDS = {
    "git", "ls", "cat", "echo", "pwd", "cd", "grep",
    "find", "npm", "yarn", "python", "node", "pip",
    "docker", "kubectl", "terraform", "make", "cargo"
}


class CommandValidator:
    """Validates shell commands against organizational policies"""
    
    def __init__(self):
        self.violation_count = 0
        self.audit_log = []
    
    def validate_command(self, command: str) -> dict:
        """
        Validates a command against all policy rules
        Returns: {"allowed": bool, "reason": str, "policy": str}
        """
        command = command.strip()
        
        # Check if command starts with allowed command
        first_word = command.split()[0] if command.split() else ""
        base_command = first_word.split("/")[-1]  # Handle /usr/bin/git
        
        # Check against policy rules
        for policy_name, policy in POLICY_RULES.items():
            for pattern in policy["patterns"]:
                if re.search(pattern, command, re.IGNORECASE):
                    self.violation_count += 1
                    self.audit_log.append({
                        "command": command,
                        "policy": policy_name,
                        "status": "BLOCKED"
                    })
                    return {
                        "allowed": False,
                        "reason": policy["message"],
                        "policy": policy_name,
                        "pattern_matched": pattern
                    }
        
        # Log allowed command
        self.audit_log.append({
            "command": command,
            "status": "ALLOWED"
        })
        
        return {
            "allowed": True,
            "reason": "Command passed all policy checks",
            "policy": None
        }
    
    def get_stats(self) -> dict:
        """Returns validation statistics"""
        return {
            "total_commands": len(self.audit_log),
            "blocked": self.violation_count,
            "allowed": len(self.audit_log) - self.violation_count,
            "recent_log": self.audit_log[-10:]  # Last 10 commands
        }


# Initialize validator
validator = CommandValidator()

# Create MCP server
server = Server("command-validator")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="validate_command",
            description="Validates a shell command against organizational security policies before execution. Returns validation result with policy details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to validate"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="execute_validated_command",
            description="Validates and executes a shell command if it passes all policy checks. Use this instead of direct shell access.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to validate and execute"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="get_validation_stats",
            description="Get statistics about command validations (blocked vs allowed)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="list_policies",
            description="List all active security policies and their rules",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "validate_command":
        command = arguments.get("command", "")
        result = validator.validate_command(command)
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    elif name == "execute_validated_command":
        command = arguments.get("command", "")
        validation = validator.validate_command(command)
        
        if not validation["allowed"]:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "blocked",
                    "command": command,
                    "reason": validation["reason"],
                    "policy": validation["policy"]
                }, indent=2)
            )]
        
        # In production, you would execute the command here
        # For safety, we'll simulate execution
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "command": command,
                "validation": "passed",
                "output": f"[SIMULATED] Command '{command}' would be executed here"
            }, indent=2)
        )]
    
    elif name == "get_validation_stats":
        stats = validator.get_stats()
        return [TextContent(
            type="text",
            text=json.dumps(stats, indent=2)
        )]
    
    elif name == "list_policies":
        policies = {
            name: {
                "message": policy["message"],
                "pattern_count": len(policy["patterns"])
            }
            for name, policy in POLICY_RULES.items()
        }
        return [TextContent(
            type="text",
            text=json.dumps(policies, indent=2)
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
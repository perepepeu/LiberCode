#!/usr/bin/env python3
"""
DevMate - Terminal Coding Assistant
A pair programmer that lives in your terminal.

Features:
- Read/edit files, run shell commands, Git help
- Persistent memory across sessions
- Multiple modes: build, plan, spec-driven
- Automatic checkpoints
- Project memory, scratch notes, task tracking
- Helper agents for complex tasks
- Stop condition verification
- Easy setup with built-in and custom model providers
"""

import os
import sys
import json
import hashlib
import subprocess
import readline
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import argparse


# ============================================================================
# Configuration & Setup
# ============================================================================

DEV_MATE_DIR = Path.home() / ".devmate"
CONFIG_FILE = DEV_MATE_DIR / "config.json"
PROJECT_CONFIG_FILE = ".devmate.json"


class ModelProvider(Enum):
    BUILTIN = "builtin"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    provider: str = ModelProvider.BUILTIN.value
    api_key: str = ""
    base_url: str = ""
    model_name: str = "devmate-local"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class DevMateConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    auto_checkpoint: bool = True
    checkpoint_interval: int = 5  # actions
    verbose: bool = False
    color_enabled: bool = True
    default_mode: str = "build"


def ensure_config():
    """Ensure config directory and file exist."""
    DEV_MATE_DIR.mkdir(parents=True, exist_ok=True)
    
    if not CONFIG_FILE.exists():
        default_config = DevMateConfig()
        save_config(default_config)
        print_setup_guide()
        return False
    return True


def load_config() -> DevMateConfig:
    """Load global configuration."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            model_data = data.get('model', {})
            return DevMateConfig(
                model=ModelConfig(**model_data) if isinstance(model_data, dict) else ModelConfig(),
                auto_checkpoint=data.get('auto_checkpoint', True),
                checkpoint_interval=data.get('checkpoint_interval', 5),
                verbose=data.get('verbose', False),
                color_enabled=data.get('color_enabled', True),
                default_mode=data.get('default_mode', 'build')
            )
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return DevMateConfig()


def save_config(config: DevMateConfig):
    """Save global configuration."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(asdict(config), f, indent=2)


def load_project_config(project_root: Path) -> dict:
    """Load project-specific configuration."""
    config_path = project_root / PROJECT_CONFIG_FILE
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def print_setup_guide():
    """Print first-run setup guide."""
    print("""
╔═══════════════════════════════════════════════════════════╗
║           Welcome to DevMate - Your Pair Programmer       ║
╚═══════════════════════════════════════════════════════════╝

📋 Quick Setup Guide:

1. Choose a model provider by editing ~/.devmate/config.json

   Built-in (no setup required):
   - Uses local heuristics and patterns
   - Great for file operations, git, and shell commands
   
   OpenAI:
   - Set provider: "openai"
   - Set api_key: "your-key-here"
   - Model: "gpt-4o" or "gpt-4-turbo"
   
   Anthropic:
   - Set provider: "anthropic"  
   - Set api_key: "your-key-here"
   - Model: "claude-sonnet-4-20250514"
   
   Ollama (local models):
   - Set provider: "ollama"
   - Base URL: "http://localhost:11434"
   - Model: "codellama", "deepseek-coder", etc.

2. Create a project config (.devmate.json) for project-specific settings:
   {
     "name": "my-project",
     "mode": "build",
     "memory_tags": ["python", "web", "api"],
     "ignored_dirs": [".git", "node_modules", "__pycache__"]
   }

3. Start coding! DevMate remembers everything across sessions.

Commands: /help for full command list
""")


# ============================================================================
# Colors & Formatting
# ============================================================================

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


def c(text: str, *colors: str, enabled: bool = True) -> str:
    """Apply colors to text."""
    if not enabled:
        return text
    return "".join(colors) + text + Colors.RESET


def box(title: str, content: str, color: str = Colors.BLUE, enabled: bool = True) -> str:
    """Create a boxed message."""
    if not enabled:
        return f"[{title}]\n{content}"
    
    width = max(len(title) + 4, max(len(line) for line in content.split('\n')) + 2)
    lines = [
        f"{color}┌{'─' * width}┐{Colors.RESET}",
        f"{color}│{Colors.RESET} {c(title, Colors.BOLD)} {color}{' ' * (width - len(title) - 2)}│{Colors.RESET}",
        f"{color}├{'─' * width}┤{Colors.RESET}",
    ]
    for line in content.split('\n'):
        padding = width - len(line) - 1
        lines.append(f"{color}│{Colors.RESET} {line}{' ' * padding}│")
    lines.append(f"{color}└{'─' * width}┘{Colors.RESET}")
    return '\n'.join(lines)


# ============================================================================
# Memory System
# ============================================================================

@dataclass
class MemoryEntry:
    timestamp: str
    type: str
    content: str
    tags: List[str] = field(default_factory=list)


@dataclass
class TaskProgress:
    id: str
    title: str
    status: str  # pending, in_progress, blocked, done
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Checkpoint:
    id: str
    timestamp: str
    action_count: int
    context_summary: str
    task_state: Dict[str, Any] = field(default_factory=dict)
    files_modified: List[str] = field(default_factory=list)


class MemoryManager:
    """Manages persistent project memory."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.memory_file = project_root / ".devmate" / "memory.json"
        self.tasks_file = project_root / ".devmate" / "tasks.json"
        self.scratch_file = project_root / ".devmate" / "scratch.md"
        self.checkpoints_dir = project_root / ".devmate" / "checkpoints"
        
        self._ensure_dirs()
        self.entries: List[MemoryEntry] = []
        self.tasks: Dict[str, TaskProgress] = {}
        self.scratch_content = ""
        self.checkpoints: List[Checkpoint] = []
        self._load()
    
    def _ensure_dirs(self):
        (self.project_root / ".devmate").mkdir(exist_ok=True)
        self.checkpoints_dir.mkdir(exist_ok=True)
        
        if not self.scratch_file.exists():
            self.scratch_file.write_text("# Scratch Notes\n\nStart jotting down ideas here...\n")
    
    def _load(self):
        """Load all memory from disk."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self.entries = [MemoryEntry(**e) for e in data.get('entries', [])]
            except:
                pass
        
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = {
                        k: TaskProgress(**v) for k, v in data.items()
                    }
            except:
                pass
        
        if self.scratch_file.exists():
            self.scratch_content = self.scratch_file.read_text()
        
        # Load checkpoints
        for cp_file in sorted(self.checkpoints_dir.glob("checkpoint_*.json")):
            try:
                with open(cp_file, 'r') as f:
                    data = json.load(f)
                    self.checkpoints.append(Checkpoint(**data))
            except:
                pass
    
    def _save(self):
        """Save all memory to disk."""
        with open(self.memory_file, 'w') as f:
            json.dump({
                'entries': [asdict(e) for e in self.entries],
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
        
        with open(self.tasks_file, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.tasks.items()}, f, indent=2)
        
        self.scratch_file.write_text(self.scratch_content)
    
    def add_entry(self, entry_type: str, content: str, tags: List[str] = None):
        """Add a memory entry."""
        entry = MemoryEntry(
            timestamp=datetime.now().isoformat(),
            type=entry_type,
            content=content,
            tags=tags or []
        )
        self.entries.append(entry)
        # Keep last 500 entries
        self.entries = self.entries[-500:]
        self._save()
    
    def search_memory(self, query: str) -> List[MemoryEntry]:
        """Search memory entries."""
        query_lower = query.lower()
        results = []
        for entry in self.entries:
            if query_lower in entry.content.lower() or \
               any(query_lower in tag.lower() for tag in entry.tags):
                results.append(entry)
        return results[-10:]  # Last 10 matches
    
    def create_task(self, title: str, steps: List[str] = None) -> str:
        """Create a new task."""
        task_id = hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:8]
        now = datetime.now().isoformat()
        
        task = TaskProgress(
            id=task_id,
            title=title,
            status="pending",
            steps=[{"description": s, "done": False} for s in (steps or [])],
            current_step=0,
            created_at=now,
            updated_at=now
        )
        self.tasks[task_id] = task
        self._save()
        return task_id
    
    def update_task(self, task_id: str, **kwargs):
        """Update a task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now().isoformat()
            self._save()
    
    def get_active_tasks(self) -> List[TaskProgress]:
        """Get all non-completed tasks."""
        return [t for t in self.tasks.values() if t.status != "done"]
    
    def write_scratch(self, content: str):
        """Write to scratch file."""
        self.scratch_content = content
        self.scratch_file.write_text(content)
    
    def append_scratch(self, content: str):
        """Append to scratch file."""
        self.scratch_content += "\n" + content
        self._save()
    
    def create_checkpoint(self, action_count: int, context_summary: str, 
                         task_state: Dict = None, files_modified: List[str] = None) -> Checkpoint:
        """Create a checkpoint."""
        checkpoint_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
        now = datetime.now().isoformat()
        
        checkpoint = Checkpoint(
            id=checkpoint_id,
            timestamp=now,
            action_count=action_count,
            context_summary=context_summary,
            task_state=task_state or {},
            files_modified=files_modified or []
        )
        
        # Save checkpoint file
        cp_file = self.checkpoints_dir / f"checkpoint_{checkpoint_id}.json"
        with open(cp_file, 'w') as f:
            json.dump(asdict(checkpoint), f, indent=2)
        
        self.checkpoints.append(checkpoint)
        # Keep last 50 checkpoints
        self.checkpoints = self.checkpoints[-50:]
        
        return checkpoint
    
    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint."""
        return self.checkpoints[-1] if self.checkpoints else None
    
    def get_context(self) -> str:
        """Get summarized context for the AI."""
        context_parts = []
        
        # Recent memory
        recent = self.entries[-10:]
        if recent:
            context_parts.append("## Recent Activity")
            for entry in recent:
                context_parts.append(f"- [{entry.type}] {entry.content[:100]}...")
        
        # Active tasks
        active = self.get_active_tasks()
        if active:
            context_parts.append("\n## Active Tasks")
            for task in active:
                progress = sum(1 for s in task.steps if s.get('done'))
                total = len(task.steps)
                context_parts.append(f"- {task.title} ({progress}/{total} steps)")
        
        return "\n".join(context_parts)


# ============================================================================
# File Operations
# ============================================================================

class FileManager:
    """Handles file reading and editing."""
    
    def __init__(self, project_root: Path, ignored_dirs: List[str] = None):
        self.project_root = project_root
        self.ignored_dirs = set(ignored_dirs or ['.git', 'node_modules', '__pycache__', '.devmate'])
    
    def read_file(self, path: str) -> str:
        """Read a file's contents."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_text()
    
    def write_file(self, path: str, content: str):
        """Write content to a file."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    
    def edit_file(self, path: str, old_str: str, new_str: str) -> bool:
        """Edit a file by replacing old_str with new_str."""
        content = self.read_file(path)
        if old_str not in content:
            return False
        new_content = content.replace(old_str, new_str, 1)
        self.write_file(path, new_content)
        return True
    
    def list_files(self, path: str = ".", recursive: bool = False, 
                   include_hidden: bool = False) -> List[str]:
        """List files in a directory."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return []
        
        results = []
        if recursive:
            for item in full_path.rglob("*"):
                if self._should_include(item, include_hidden):
                    results.append(str(item.relative_to(self.project_root)))
        else:
            for item in full_path.iterdir():
                if self._should_include(item, include_hidden):
                    results.append(str(item.relative_to(self.project_root)))
        
        return sorted(results)
    
    def search_files(self, pattern: str, content_search: str = None) -> List[str]:
        """Search for files matching pattern and optionally content."""
        results = []
        for file_path in self.project_root.rglob(pattern):
            if self._should_include(file_path):
                if content_search:
                    try:
                        content = file_path.read_text()
                        if content_search.lower() in content.lower():
                            results.append(str(file_path.relative_to(self.project_root)))
                    except:
                        pass
                else:
                    results.append(str(file_path.relative_to(self.project_root)))
        return results
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to project root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.project_root / p).resolve()
    
    def _should_include(self, path: Path, include_hidden: bool = False) -> bool:
        """Check if a path should be included."""
        parts = path.relative_to(self.project_root).parts
        for part in parts:
            if part in self.ignored_dirs:
                return False
            if not include_hidden and part.startswith('.'):
                return False
        return True


# ============================================================================
# Shell & Git Operations
# ============================================================================

class ShellManager:
    """Handles shell command execution."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
    def run(self, command: str, capture: bool = True, timeout: int = 60) -> tuple:
        """Run a shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                capture_output=capture,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def run_background(self, command: str) -> subprocess.Popen:
        """Run a command in the background."""
        return subprocess.Popen(
            command,
            shell=True,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


class GitManager:
    """Handles Git operations."""
    
    def __init__(self, project_root: Path, shell: ShellManager):
        self.project_root = project_root
        self.shell = shell
    
    def is_repo(self) -> bool:
        """Check if this is a git repository."""
        code, _, _ = self.shell.run("git rev-parse --is-inside-work-tree")
        return code == 0
    
    def status(self) -> str:
        """Get git status."""
        _, stdout, _ = self.shell.run("git status")
        return stdout
    
    def diff(self, staged: bool = False) -> str:
        """Get git diff."""
        cmd = "git diff --cached" if staged else "git diff"
        _, stdout, _ = self.shell.run(cmd)
        return stdout
    
    def log(self, limit: int = 10) -> str:
        """Get git log."""
        _, stdout, _ = self.shell.run(f"git log -{limit} --oneline")
        return stdout
    
    def branch(self) -> str:
        """Get current branch."""
        _, stdout, _ = self.shell.run("git branch --show-current")
        return stdout.strip()
    
    def commit(self, message: str, amend: bool = False) -> tuple:
        """Create a commit."""
        cmd = "git commit" + (" --amend" if amend else "") + f" -m '{message}'"
        return self.shell.run(cmd)
    
    def add(self, files: List[str] = None, all_files: bool = False) -> tuple:
        """Stage files."""
        if all_files:
            return self.shell.run("git add -A")
        elif files:
            return self.shell.run(f"git add {' '.join(files)}")
        return 0, "", ""
    
    def stash(self, message: str = "") -> tuple:
        """Stash changes."""
        cmd = "git stash push" + (f" -m '{message}'" if message else "")
        return self.shell.run(cmd)
    
    def restore_stash(self, index: int = 0) -> tuple:
        """Restore a stash."""
        return self.shell.run(f"git stash pop stash@{{{index}}}")


# ============================================================================
# AI Model Interface
# ============================================================================

class ModelInterface:
    """Interface for different AI model providers."""
    
    def __init__(self, config: ModelConfig):
        self.config = config
    
    def chat(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        """Send a chat request and get a response."""
        if self.config.provider == ModelProvider.BUILTIN.value:
            return self._builtin_response(messages)
        elif self.config.provider == ModelProvider.OPENAI.value:
            return self._openai_response(messages, system_prompt)
        elif self.config.provider == ModelProvider.ANTHROPIC.value:
            return self._anthropic_response(messages, system_prompt)
        elif self.config.provider == ModelProvider.OLLAMA.value:
            return self._ollama_response(messages, system_prompt)
        else:
            return self._custom_response(messages, system_prompt)
    
    def _builtin_response(self, messages: List[Dict[str, str]]) -> str:
        """Built-in heuristic-based responses for basic operations."""
        last_msg = messages[-1]['content'] if messages else ""
        
        # Simple pattern matching for common tasks
        if "list files" in last_msg.lower() or "show files" in last_msg.lower():
            return "I can help list files. Use the `list_files` command or ask me to show the directory structure."
        
        if "read" in last_msg.lower() and "file" in last_msg.lower():
            return "I can read files for you. Specify the file path and I'll show you its contents."
        
        if "edit" in last_msg.lower() or "change" in last_msg.lower():
            return "I can edit files. Tell me what changes you want to make."
        
        if "git" in last_msg.lower():
            return "I can help with Git operations. What would you like to do? (status, commit, push, etc.)"
        
        if "run" in last_msg.lower() or "execute" in last_msg.lower():
            return "I can run shell commands for you. What command would you like to execute?"
        
        return """I'm DevMate, your terminal pair programmer. I can help you with:
- Reading and editing files
- Running shell commands
- Git operations (status, commits, branches, etc.)
- Project planning and task tracking
- Maintaining context across sessions

What would you like to work on?"""
    
    def _openai_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """OpenAI API response."""
        try:
            import urllib.request
            import json
            
            url = "https://api.openai.com/v1/chat/completions"
            
            payload = {
                "model": self.config.model_name or "gpt-4o",
                "messages": [{"role": "system", "content": system_prompt or "You are DevMate, a helpful coding assistant."}] + messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}"
                }
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode())
                return data['choices'][0]['message']['content']
                
        except Exception as e:
            return f"Error calling OpenAI: {e}"
    
    def _anthropic_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """Anthropic API response."""
        try:
            import urllib.request
            import json
            
            url = "https://api.anthropic.com/v1/messages"
            
            # Convert messages format
            anthropic_messages = []
            for msg in messages:
                role = msg.get('role', 'user')
                if role == 'assistant':
                    role = 'assistant'
                anthropic_messages.append({
                    "role": role,
                    "content": msg.get('content', '')
                })
            
            payload = {
                "model": self.config.model_name or "claude-sonnet-4-20250514",
                "max_tokens": self.config.max_tokens,
                "system": system_prompt or "You are DevMate, a helpful coding assistant.",
                "messages": anthropic_messages
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.config.api_key,
                    "anthropic-version": "2023-06-01"
                }
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode())
                return data['content'][0]['text']
                
        except Exception as e:
            return f"Error calling Anthropic: {e}"
    
    def _ollama_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """Ollama local model response."""
        try:
            import urllib.request
            import json
            
            base_url = self.config.base_url or "http://localhost:11434"
            url = f"{base_url}/api/chat"
            
            payload = {
                "model": self.config.model_name or "codellama",
                "messages": [{"role": "system", "content": system_prompt or "You are DevMate, a helpful coding assistant."}] + messages,
                "stream": False
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=300) as response:
                data = json.loads(response.read().decode())
                return data.get('message', {}).get('content', 'No response from Ollama')
                
        except Exception as e:
            return f"Error calling Ollama: {e}"
    
    def _custom_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """Custom API endpoint response."""
        try:
            import urllib.request
            import json
            
            payload = {
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "model": self.config.model_name,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            req = urllib.request.Request(
                self.config.base_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode())
                # Try common response formats
                return (data.get('choices', [{}])[0].get('message', {}).get('content') or
                        data.get('response') or
                        data.get('content') or
                        str(data))
                        
        except Exception as e:
            return f"Error calling custom API: {e}"


# ============================================================================
# Agent Modes
# ============================================================================

class AgentMode(Enum):
    BUILD = "build"       # Full coding mode - read/write/execute
    PLAN = "plan"         # Read-only planning mode
    SPEC = "spec"         # Spec-driven coordinated mode


# ============================================================================
# Helper Agents
# ============================================================================

class HelperAgent:
    """Base class for helper agents."""
    
    def __init__(self, name: str, specialty: str):
        self.name = name
        self.specialty = specialty
    
    def execute(self, task: str, context: Dict) -> str:
        raise NotImplementedError


class CodeReviewAgent(HelperAgent):
    """Agent specialized in code review."""
    
    def __init__(self):
        super().__init__("CodeReviewer", "code-review")
    
    def execute(self, task: str, context: Dict) -> str:
        return f"[CodeReviewAgent] Analyzing code changes...\n\nKey observations:\n- Reviewing code style and conventions\n- Checking for potential bugs\n- Suggesting improvements\n\nDetailed feedback would come from AI model integration."


class TestAgent(HelperAgent):
    """Agent specialized in testing."""
    
    def __init__(self):
        super().__init__("TestRunner", "testing")
    
    def execute(self, task: str, context: Dict) -> str:
        return f"[TestAgent] Setting up test execution...\n\nTest strategy:\n- Unit tests for new functionality\n- Integration tests for API changes\n- Regression tests for existing features\n\nWould execute tests via AI model integration."


class DocsAgent(HelperAgent):
    """Agent specialized in documentation."""
    
    def __init__(self):
        super().__init__("DocWriter", "documentation")
    
    def execute(self, task: str, context: Dict) -> str:
        return f"[DocsAgent] Preparing documentation updates...\n\nDocumentation plan:\n- Update README with new features\n- Add inline code comments\n- Generate API documentation\n\nWould create docs via AI model integration."


# ============================================================================
# Main DevMate Agent
# ============================================================================

class DevMateAgent:
    """The main DevMate pair programming agent."""
    
    SYSTEM_PROMPT = """You are DevMate, an expert pair programmer working directly in the user's terminal.

Your capabilities:
- Read and edit files in the project
- Run shell commands and scripts
- Help with Git operations
- Plan and coordinate complex tasks
- Maintain context across sessions

Communication style:
- Be concise but thorough
- Show code changes clearly
- Explain your reasoning briefly
- Ask clarifying questions when needed
- Confirm before making destructive changes

When suggesting file edits, use this format:
```edit:path/to/file.py
old code here
```
becomes:
```edit:path/to/file.py
new code here
```

For shell commands, prefix with $:
$ command here

Always think step-by-step for complex tasks."""

    def __init__(self, project_root: Path, config: DevMateConfig, mode: AgentMode = AgentMode.BUILD):
        self.project_root = project_root
        self.config = config
        self.mode = mode
        
        self.file_manager = FileManager(project_root)
        self.shell_manager = ShellManager(project_root)
        self.git_manager = GitManager(project_root, self.shell_manager)
        self.memory = MemoryManager(project_root)
        self.model = ModelInterface(config.model)
        
        self.action_count = 0
        self.conversation_history: List[Dict[str, str]] = []
        self.current_task: Optional[str] = None
        self.helper_agents: Dict[str, HelperAgent] = {}
        self.stop_condition: Optional[str] = None
        
        # Register helper agents
        self.register_helper(CodeReviewAgent())
        self.register_helper(TestAgent())
        self.register_helper(DocsAgent())
    
    def register_helper(self, agent: HelperAgent):
        """Register a helper agent."""
        self.helper_agents[agent.specialty] = agent
    
    def spawn_helper(self, specialty: str, task: str) -> str:
        """Spawn a helper agent for a specific task."""
        if specialty not in self.helper_agents:
            return f"No helper agent available for: {specialty}"
        
        agent = self.helper_agents[specialty]
        context = {
            "project_root": str(self.project_root),
            "memory": self.memory.get_context(),
            "conversation": self.conversation_history[-5:]
        }
        return agent.execute(task, context)
    
    def process_command(self, user_input: str) -> str:
        """Process a user command."""
        self.action_count += 1
        
        # Auto-checkpoint
        if self.config.auto_checkpoint and self.action_count % self.config.checkpoint_interval == 0:
            self._auto_checkpoint()
        
        # Handle slash commands
        if user_input.startswith('/'):
            return self._handle_slash_command(user_input)
        
        # Build context
        context = self._build_context()
        
        # Prepare messages
        messages = self.conversation_history[-20:] + [{"role": "user", "content": user_input}]
        
        # Get AI response
        response = self.model.chat(messages, self.SYSTEM_PROMPT)
        
        # Store in history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Remember important info
        self._remember(user_input, response)
        
        # Process any actions in the response
        processed_response = self._process_actions(response)
        
        return processed_response
    
    def _build_context(self) -> str:
        """Build context for the AI."""
        parts = [
            f"Project: {self.project_root.name}",
            f"Mode: {self.mode.value}",
            f"Git branch: {self.git_manager.branch() if self.git_manager.is_repo() else 'N/A'}",
        ]
        
        # Add memory context
        memory_context = self.memory.get_context()
        if memory_context:
            parts.append(memory_context)
        
        # Add active task
        if self.current_task and self.current_task in self.memory.tasks:
            task = self.memory.tasks[self.current_task]
            parts.append(f"\nCurrent Task: {task.title}")
            parts.append(f"Status: {task.status}, Step: {task.current_step + 1}/{len(task.steps)}")
        
        return "\n".join(parts)
    
    def _handle_slash_command(self, command: str) -> str:
        """Handle slash commands."""
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        commands = {
            'help': self._cmd_help,
            'mode': self._cmd_mode,
            'read': self._cmd_read,
            'edit': self._cmd_edit,
            'write': self._cmd_write,
            'list': self._cmd_list,
            'search': self._cmd_search,
            'run': self._cmd_run,
            'git': self._cmd_git,
            'task': self._cmd_task,
            'memory': self._cmd_memory,
            'scratch': self._cmd_scratch,
            'checkpoint': self._cmd_checkpoint,
            'agent': self._cmd_agent,
            'stop': self._cmd_stop,
            'context': self._cmd_context,
            'clear': self._cmd_clear,
            'quit': self._cmd_quit,
        }
        
        if cmd in commands:
            return commands[cmd](args)
        else:
            return f"Unknown command: /{cmd}. Type /help for available commands."
    
    def _cmd_help(self, args: str) -> str:
        """Show help."""
        return """
╔═══════════════════════════════════════════════════════════╗
║                    DevMate Commands                       ║
╚═══════════════════════════════════════════════════════════╝

FILE OPERATIONS:
  /read <path>              Read a file
  /edit <path>              Edit a file (interactive)
  /write <path> <content>   Write content to file
  /list [path]              List files (add -r for recursive)
  /search <pattern>         Search for files

SHELL & GIT:
  /run <command>            Run a shell command
  /git <subcommand>         Git operations (status, log, diff, etc.)

TASKS & MEMORY:
  /task new <title>         Create a new task
  /task list                List active tasks
  /task done <id>           Mark task as done
  /memory <query>           Search memory
  /scratch                  View/edit scratch notes
  /checkpoint               Create/view checkpoints

MODES:
  /mode build               Full coding mode (default)
  /mode plan                Read-only planning
  /mode spec                Spec-driven coordination

AGENTS:
  /agent spawn <type>       Spawn helper agent
  /agent list               List available agents

OTHER:
  /stop <condition>         Set stop condition
  /context                  Show current context
  /clear                    Clear conversation history
  /quit                     Exit DevMate

TIPS:
- Just type naturally for AI assistance
- DevMate remembers context across sessions
- Use tasks to track complex work
"""
    
    def _cmd_mode(self, args: str) -> str:
        """Change mode."""
        modes = {'build': AgentMode.BUILD, 'plan': AgentMode.PLAN, 'spec': AgentMode.SPEC}
        
        if not args or args.lower() not in modes:
            return f"Current mode: {self.mode.value}\nAvailable: build, plan, spec"
        
        self.mode = modes[args.lower()]
        self.memory.add_entry("mode_change", f"Switched to {self.mode.value} mode")
        return f"Mode changed to: {c(self.mode.value, Colors.GREEN)}"
    
    def _cmd_read(self, args: str) -> str:
        """Read a file."""
        if not args:
            return "Usage: /read <file_path>"
        
        try:
            content = self.file_manager.read_file(args)
            lines = content.split('\n')
            header = f"📄 {args} ({len(lines)} lines)"
            return box(header, content, Colors.CYAN, self.config.color_enabled)
        except FileNotFoundError as e:
            return f"Error: {e}"
    
    def _cmd_edit(self, args: str) -> str:
        """Edit a file."""
        if not args:
            return "Usage: /edit <file_path>"
        
        try:
            content = self.file_manager.read_file(args)
            return f"Editing {args}...\n\n{content}\n\n---\nTo edit, describe the changes or use /write"
        except FileNotFoundError as e:
            return f"Error: {e}"
    
    def _cmd_write(self, args: str) -> str:
        """Write to a file."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /write <file_path> <content>"
        
        path, content = parts[0], parts[1]
        try:
            self.file_manager.write_file(path, content)
            self.memory.add_entry("file_write", f"Wrote to {path}", tags=["file"])
            return f"✅ Written to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
    
    def _cmd_list(self, args: str) -> str:
        """List files."""
        recursive = '-r' in args
        path = args.replace('-r', '').strip() or "."
        
        files = self.file_manager.list_files(path, recursive)
        if not files:
            return "No files found."
        
        return f"📁 Files in {path}:\n" + "\n".join(f"  {f}" for f in files[:50])
    
    def _cmd_search(self, args: str) -> str:
        """Search for files."""
        if not args:
            return "Usage: /search <pattern>"
        
        files = self.file_manager.search_files(f"*{args}*")
        if not files:
            return f"No files matching '{args}'"
        
        return f"🔍 Found {len(files)} files:\n" + "\n".join(f"  {f}" for f in files[:50])
    
    def _cmd_run(self, args: str) -> str:
        """Run a shell command."""
        if not args:
            return "Usage: /run <command>"
        
        if self.mode == AgentMode.PLAN:
            return "[PLAN MODE] Would run: " + args
        
        returncode, stdout, stderr = self.shell_manager.run(args)
        
        output = f"$ {args}\n"
        if stdout:
            output += stdout
        if stderr:
            output += c(f"\nstderr:\n{stderr}", Colors.RED, enabled=self.config.color_enabled)
        output += f"\nExit code: {returncode}"
        
        self.memory.add_entry("shell_command", f"Ran: {args} (exit: {returncode})")
        return output
    
    def _cmd_git(self, args: str) -> str:
        """Git operations."""
        if not self.git_manager.is_repo():
            return "Not a git repository."
        
        if not args:
            args = "status"
        
        subcmd = args.split()[0]
        
        if subcmd == "status":
            return self.git_manager.status()
        elif subcmd == "diff":
            return self.git_manager.diff(staged='--cached' in args)
        elif subcmd == "log":
            return self.git_manager.log()
        elif subcmd == "branch":
            return f"Current branch: {self.git_manager.branch()}"
        elif subcmd == "commit":
            # Extract commit message
            match = re.search(r"-m ['\"](.+?)['\"]", args)
            if match:
                code, out, err = self.git_manager.commit(match.group(1))
                return out if code == 0 else err
            return "Usage: /git commit -m 'message'"
        elif subcmd == "add":
            code, out, err = self.git_manager.add(all_files='-A' in args)
            return out if out else (err if err else "Files staged.")
        else:
            code, stdout, stderr = self.shell_manager.run(f"git {args}")
            return stdout if stdout else stderr
    
    def _cmd_task(self, args: str) -> str:
        """Task management."""
        parts = args.split(maxsplit=2)
        if not parts:
            return "Usage: /task <new|list|done|show> [args]"
        
        subcmd = parts[0]
        
        if subcmd == "new":
            title = parts[1] if len(parts) > 1 else "Untitled task"
            task_id = self.memory.create_task(title)
            self.current_task = task_id
            return f"Created task '{title}' (ID: {task_id})"
        
        elif subcmd == "list":
            tasks = self.memory.get_active_tasks()
            if not tasks:
                return "No active tasks."
            
            output = "📋 Active Tasks:\n"
            for task in tasks:
                progress = sum(1 for s in task.steps if s.get('done'))
                total = len(task.steps)
                status_icon = "✓" if task.status == "done" else "○"
                output += f"  {status_icon} [{task.id}] {task.title} ({progress}/{total})\n"
            return output
        
        elif subcmd == "done":
            task_id = parts[1] if len(parts) > 1 else self.current_task
            if task_id and task_id in self.memory.tasks:
                self.memory.update_task(task_id, status="done")
                return f"✓ Task completed: {self.memory.tasks[task_id].title}"
            return "Task not found."
        
        elif subcmd == "show":
            task_id = parts[1] if len(parts) > 1 else self.current_task
            if task_id and task_id in self.memory.tasks:
                task = self.memory.tasks[task_id]
                output = f"Task: {task.title}\nStatus: {task.status}\nSteps:\n"
                for i, step in enumerate(task.steps):
                    icon = "✓" if step.get('done') else "○"
                    marker = "→" if i == task.current_step else " "
                    output += f"  {marker}{icon} {step.get('description', 'Step ' + str(i+1))}\n"
                return output
            return "Task not found."
        
        return "Unknown task command."
    
    def _cmd_memory(self, args: str) -> str:
        """Search memory."""
        if not args:
            # Show recent memory
            entries = self.memory.entries[-10:]
            if not entries:
                return "No memory entries yet."
            
            output = "🧠 Recent Memory:\n"
            for entry in entries:
                output += f"  [{entry.type}] {entry.content[:80]}...\n"
            return output
        
        # Search
        results = self.memory.search_memory(args)
        if not results:
            return f"No memory matches '{args}'"
        
        output = f"🔍 Memory results for '{args}':\n"
        for entry in results:
            output += f"  [{entry.timestamp[:10]}] {entry.content[:100]}...\n"
        return output
    
    def _cmd_scratch(self, args: str) -> str:
        """View/edit scratch notes."""
        if args:
            # Append to scratch
            self.memory.append_scratch(args)
            return "Added to scratch notes."
        
        # Show scratch content
        return self.memory.scratch_content
    
    def _cmd_checkpoint(self, args: str) -> str:
        """Checkpoint management."""
        if args == "new" or not args:
            summary = args[3:] if args.startswith("new ") else "Manual checkpoint"
            cp = self.memory.create_checkpoint(
                self.action_count,
                summary,
                {"task": self.current_task},
                []
            )
            return f"💾 Checkpoint created: {cp.id}"
        
        if args == "list":
            cps = self.memory.checkpoints[-10:]
            if not cps:
                return "No checkpoints."
            
            output = "💾 Checkpoints:\n"
            for cp in reversed(cps):
                output += f"  [{cp.id}] {cp.timestamp[:16]} - {cp.context_summary}\n"
            return output
        
        if args == "last":
            cp = self.memory.get_latest_checkpoint()
            if cp:
                return f"Latest checkpoint:\n  ID: {cp.id}\n  Time: {cp.timestamp}\n  Summary: {cp.context_summary}\n  Actions: {cp.action_count}"
            return "No checkpoints."
        
        return "Usage: /checkpoint [new|list|last]"
    
    def _cmd_agent(self, args: str) -> str:
        """Helper agent management."""
        parts = args.split(maxsplit=1)
        if not parts or parts[0] != "spawn":
            # List agents
            output = "🤖 Available Helper Agents:\n"
            for name, agent in self.helper_agents.items():
                output += f"  • {agent.name} ({agent.specialty})\n"
            output += "\nUsage: /agent spawn <type> <task>"
            return output
        
        if len(parts) < 2:
            return "Usage: /agent spawn <type> <task>"
        
        agent_type = parts[1].split()[0]
        task = parts[1][len(agent_type):].strip()
        
        result = self.spawn_helper(agent_type, task)
        self.memory.add_entry("helper_agent", f"Spawned {agent_type}: {task}")
        return result
    
    def _cmd_stop(self, args: str) -> str:
        """Set stop condition."""
        if not args:
            if self.stop_condition:
                return f"Stop condition: {self.stop_condition}"
            return "No stop condition set."
        
        self.stop_condition = args
        return f"🛑 Stop condition set: {args}"
    
    def _cmd_context(self, args: str) -> str:
        """Show current context."""
        return box("Current Context", self._build_context(), Colors.MAGENTA, self.config.color_enabled)
    
    def _cmd_clear(self, args: str) -> str:
        """Clear conversation history."""
        self.conversation_history = []
        return "Conversation history cleared."
    
    def _cmd_quit(self, args: str) -> str:
        """Quit DevMate."""
        # Final checkpoint
        self._auto_checkpoint("Session ended")
        return "Goodbye! 👋"
    
    def _process_actions(self, response: str) -> str:
        """Process any actions in the AI response."""
        if self.mode == AgentMode.PLAN:
            return c("[PLAN MODE] " + response, Colors.YELLOW, self.config.color_enabled)
        
        # Look for edit blocks
        edit_pattern = r'```edit:([^`]+)\n(.*?)```\n*becomes:\n*```edit:[^`]+\n(.*?)```'
        
        for match in re.finditer(edit_pattern, response, re.DOTALL):
            path = match.group(1).strip()
            old_str = match.group(2).strip()
            new_str = match.group(3).strip()
            
            if self.file_manager.edit_file(path, old_str, new_str):
                self.memory.add_entry("file_edit", f"Edited {path}", tags=["file", "edit"])
            else:
                response += f"\n⚠️ Could not apply edit to {path}"
        
        return response
    
    def _remember(self, user_input: str, response: str):
        """Remember important information."""
        # Detect file operations
        if "/read" in user_input or "/write" in user_input or "/edit" in user_input:
            self.memory.add_entry("file_operation", user_input, tags=["file"])
        
        # Detect commands
        if "/run" in user_input or "/git" in user_input:
            self.memory.add_entry("command", user_input, tags=["shell", "git"])
        
        # Detect task-related
        if "/task" in user_input:
            self.memory.add_entry("task_management", user_input, tags=["task"])
    
    def _auto_checkpoint(self, reason: str = "Auto-checkpoint"):
        """Create automatic checkpoint."""
        self.memory.create_checkpoint(
            self.action_count,
            reason,
            {"task": self.current_task, "history_len": len(self.conversation_history)},
            []
        )
    
    def check_stop_condition(self) -> bool:
        """Check if stop condition is met."""
        if not self.stop_condition:
            return False
        
        # Ask AI to evaluate stop condition
        messages = [
            {"role": "system", "content": f"Evaluate if this condition is met: {self.stop_condition}"},
            {"role": "user", "content": f"Current state:\n{self._build_context()}\n\nIs the stop condition met? Answer YES or NO with brief explanation."}
        ]
        
        response = self.model.chat(messages, "You are evaluating task completion.")
        return "YES" in response.upper()
    
    def run_interactive(self):
        """Run interactive session."""
        print(c("\n╔═══════════════════════════════════════════════════════════╗", Colors.GREEN))
        print(c("║              DevMate - Your Pair Programmer              ║", Colors.GREEN + Colors.BOLD))
        print(c("╚═══════════════════════════════════════════════════════════╝", Colors.GREEN))
        print(c(f"  Project: {self.project_root}", Colors.DIM))
        print(c(f"  Mode: {self.mode.value}", Colors.DIM))
        print(c("  Type /help for commands, or just start coding!\n", Colors.DIM))
        
        # Restore context from last session
        last_cp = self.memory.get_latest_checkpoint()
        if last_cp:
            print(c(f"💾 Restored from checkpoint: {last_cp.id}", Colors.YELLOW))
            print(c(f"   Context: {last_cp.context_summary}\n", Colors.DIM))
        
        while True:
            try:
                user_input = input(c("DevMate> ", Colors.CYAN + Colors.BOLD))
                
                if not user_input.strip():
                    continue
                
                response = self.process_command(user_input)
                print(f"\n{response}\n")
                
                # Check stop condition
                if self.check_stop_condition():
                    print(c("\n🎉 Stop condition met! Task complete.\n", Colors.GREEN))
                    break
                
                # Check for quit
                if user_input.strip().lower() in ['/quit', '/q', 'exit', 'quit']:
                    break
                    
            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                break
        
        print(c("Goodbye! 👋\n", Colors.GREEN))


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DevMate - Your Terminal Pair Programmer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  devmate                    # Start in current directory
  devmate /path/to/project   # Start in specific directory
  devmate --mode plan        # Start in plan mode
  devmate --setup            # Run setup wizard
        """
    )
    
    parser.add_argument("project", nargs="?", default=".", 
                       help="Project directory (default: current)")
    parser.add_argument("--mode", "-m", choices=["build", "plan", "spec"],
                       help="Operating mode")
    parser.add_argument("--setup", action="store_true",
                       help="Run setup wizard")
    parser.add_argument("--no-color", action="store_true",
                       help="Disable colors")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Handle setup
    if args.setup:
        print_setup_guide()
        return
    
    # Initialize
    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"Error: Directory not found: {project_root}")
        sys.exit(1)
    
    # Ensure config exists
    config_exists = ensure_config()
    
    # Load config
    config = load_config()
    config.verbose = args.verbose
    config.color_enabled = not args.no_color
    
    # Load project config
    project_config = load_project_config(project_root)
    if project_config.get('ignored_dirs'):
        config.model.model_name = project_config.get('model', config.model.model_name)
    
    # Determine mode
    mode = AgentMode.BUILD
    if args.mode:
        mode = AgentMode(args.mode)
    elif project_config.get('mode'):
        mode = AgentMode(project_config['mode'])
    elif config.default_mode:
        mode = AgentMode(config.default_mode)
    
    # Create and run agent
    agent = DevMateAgent(project_root, config, mode)
    agent.run_interactive()


if __name__ == "__main__":
    main()

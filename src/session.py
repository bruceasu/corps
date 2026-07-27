import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )

class ChatSession:
    def __init__(self, name: str):
        self.name = name
        self.messages: List[ChatMessage] = []

    def add_message(self, role: str, content: str):
        self.messages.append(ChatMessage(role, content))

    def to_transcript(self) -> str:
        transcript = []
        for msg in self.messages:
            transcript.append(f"{msg.role.upper()}: {msg.content}")
        return "\n\n".join(transcript)

    def rename(self, new_name: str):
        self.name = new_name
        return self

    def to_dict(self):
        return {
            "name": self.name,
            "messages": [msg.to_dict() for msg in self.messages]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        session = cls(name=data["name"])
        session.messages = [ChatMessage.from_dict(m) for m in data.get("messages", [])]
        return session

class SessionManager:
    """Manages session persistence, archiving, and listing."""
    
    def __init__(self, session_dir: Optional[Path] = None):
        if session_dir is None:
            self.session_dir = Path.home() / ".config" / "corps" / "sessions"
        else:
            self.session_dir = session_dir
        self.archive_dir = self.session_dir / "archived"
        self.ensure_dirs()

    def ensure_dirs(self):
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def get_session_path(self, name: str) -> Path:
        return self.session_dir / f"{name}.json"

    def get_archive_path(self, name: str) -> Path:
        return self.archive_dir / f"{name}.json"

    def save_session(self, session: ChatSession) -> Path:
        path = self.get_session_path(session.name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_session(self, name: str) -> ChatSession:
        path = self.get_session_path(name)
        if not path.is_file():
            raise FileNotFoundError(f"Session '{name}' not found.")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ChatSession.from_dict(data)

    def delete_session(self, name: str):
        path = self.get_session_path(name)
        if path.is_file():
            path.unlink()
        else:
            raise FileNotFoundError(f"Session '{name}' not found.")

    def archive_session(self, name: str):
        src = self.get_session_path(name)
        dst = self.get_archive_path(name)
        if src.is_file():
            src.replace(dst)
        else:
            raise FileNotFoundError(f"Session '{name}' not found.")

    def unarchive_session(self, name: str):
        src = self.get_archive_path(name)
        dst = self.get_session_path(name)
        if src.is_file():
            src.replace(dst)
        else:
            raise FileNotFoundError(f"Archived session '{name}' not found.")

    def delete_archive(self, name: str):
        path = self.get_archive_path(name)
        if path.is_file():
            path.unlink()
        else:
            raise FileNotFoundError(f"Archived session '{name}' not found.")

    def list_sessions(self) -> List[Path]:
        return sorted(self.session_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

    def list_archives(self) -> List[Path]:
        return sorted(self.archive_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

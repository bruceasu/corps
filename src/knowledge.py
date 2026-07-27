import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
from collections import Counter

@dataclass
class ProblemKnowledgeRecord:
    timestamp: str = ""
    source: str = ""
    mode: str = ""
    status: str = ""
    problemType: str = ""
    classification: str = ""
    task: str = ""
    target: str = ""
    file: str = ""
    lineRange: str = ""
    inputSnippet: str = ""
    analysis: str = ""
    repairScheme: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

class ProblemKnowledgeStore:
    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = knowledge_dir
        self.records_dir = knowledge_dir / "records"
        self.jsonl_path = knowledge_dir / "records.jsonl"
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.records_dir.mkdir(parents=True, exist_ok=True)

    def record_tool_execution(self, name: str, success: bool, output: str, metadata: Dict[str, Any] = None, error: str = ""):
        record = ProblemKnowledgeRecord(
            timestamp=datetime.now().isoformat(timespec='seconds'),
            source="tool",
            mode="execute",
            status="success" if success else "failure",
            problemType="tool-execution",
            classification=name,
            analysis=output[:2000] if success else "",
            error=error,
            metadata=metadata or {}
        )
        self._persist(record)

    def record_skill_execution(self, name: str, success: bool, context: Dict[str, Any], error: str = ""):
        try:
            analysis = json.dumps(context or {}, ensure_ascii=False)[:4000]
        except Exception:
            analysis = "(failed to serialize context)"
            
        record = ProblemKnowledgeRecord(
            timestamp=datetime.now().isoformat(timespec='seconds'),
            source="skill",
            mode="execute",
            status="success" if success else "failure",
            problemType="skill-execution",
            classification=name,
            analysis=analysis,
            error=error
        )
        self._persist(record)

    def record_chat_session(self, name: str, transcript: str, summary: str = ""):
        record = ProblemKnowledgeRecord(
            timestamp=datetime.now().isoformat(timespec='seconds'),
            source="chat",
            mode="conversation",
            status="success",
            problemType="chat-session",
            classification=name,
            analysis=summary or name,
            repairScheme=transcript[:10000] # Cap transcript size
        )
        self._persist(record)

    def list_all_records(self) -> List[ProblemKnowledgeRecord]:
        if not self.jsonl_path.is_file():
            return []
        records = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        records.append(ProblemKnowledgeRecord(**data))
                    except Exception:
                        continue
        return sorted(records, key=lambda x: x.timestamp, reverse=True)

    def search_records(self, query: str, limit: int = 10) -> List[ProblemKnowledgeRecord]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return self.list_all_records()[:limit]
            
        scored = []
        for record in self.list_all_records():
            score = self._score_record(record, query_tokens)
            if score > 0:
                scored.append((record, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, s in scored[:limit]]

    def _persist(self, record: ProblemKnowledgeRecord):
        # Append to jsonl
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            
        # Save as individual markdown
        slug = self._slugify(record.classification or record.problemType or "record")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        md_path = self.records_dir / f"{ts}-{slug}.md"
        md_path.write_text(self._to_markdown(record), encoding="utf-8")

    def _tokenize(self, text: str) -> Set[str]:
        if not text: return set()
        normalized = re.sub(r'[^a-z0-9]+', ' ', text.lower())
        return {t for t in normalized.split() if len(t) >= 3}

    def _score_record(self, record: ProblemKnowledgeRecord, query_tokens: Set[str]) -> int:
        record_text = f"{record.source} {record.mode} {record.status} {record.problemType} {record.classification} {record.task} {record.target} {record.file} {record.analysis} {record.repairScheme}"
        record_tokens = self._tokenize(record_text)
        score = sum(2 for t in query_tokens if t in record_tokens)
        if record.status.lower() == "success":
            score += 1
        return score

    def _slugify(self, text: str) -> str:
        s = re.sub(r'[^a-z0-9._-]+', '-', text.lower())
        s = re.sub(r'-+', '-', s).strip('.-')
        return s or "record"

    def _to_markdown(self, record: ProblemKnowledgeRecord) -> str:
        lines = [f"# Problem Knowledge Record\n"]
        for k, v in record.to_dict().items():
            if k in ["analysis", "repairScheme", "inputSnippet", "error"] and v:
                lines.append(f"\n## {k.capitalize()}\n\n{v.strip()}\n")
            elif k == "metadata" and v:
                lines.append(f"\n## Metadata\n")
                for mk, mv in v.items():
                    lines.append(f"- {mk}: {mv}")
            elif v:
                lines.append(f"- {k.capitalize()}: {v}")
        return "\n".join(lines)

class RecordFilter:
    def __init__(self, source: str = "", status: str = "", problem_type: str = ""):
        self.source = (source or "").strip().lower()
        self.status = (status or "").strip().lower()
        self.problem_type = (problem_type or "").strip().lower()

    def isActive(self) -> bool:
        return bool(self.source or self.status or self.problem_type)

    def matches(self, record: ProblemKnowledgeRecord) -> bool:
        if self.source and self.source != record.source.lower():
            return False
        if self.status and self.status != record.status.lower():
            return False
        if self.problem_type and self.problem_type != record.problemType.lower():
            return False
        return True

def print_records(records: List[ProblemKnowledgeRecord]):
    if not records:
        print("(no records)")
        return
    for i, record in enumerate(records, 1):
        classification = record.classification or record.problemType or "(uncategorized)"
        print(f"{i}. {record.timestamp} | {record.source} | {record.status} | {classification}")
        if record.task:
            print(f"   task: {record.task[:160]}")
        if record.target:
            print(f"   target: {record.target[:160]}")
        if record.file:
            print(f"   file: {record.file[:160]}")
        if record.repairScheme:
            summary = record.repairScheme.replace('\r', ' ').replace('\n', ' ').strip()[:220]
            print(f"   repair: {summary}")
        if record.analysis:
            summary = record.analysis.replace('\r', ' ').replace('\n', ' ').strip()[:220]
            print(f"   analysis: {summary}")
        print()

def print_count_section(title: str, records: List[ProblemKnowledgeRecord], classifier: Callable[[ProblemKnowledgeRecord], str], top: int):
    print(f"{title}:")
    counts = Counter(classifier(r) for r in records)
    # Sort by count desc, then by key asc
    sorted_counts = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    for key, count in sorted_counts[:top]:
        print(f"  - {key}: {count}")
    print()

def main():
    parser = argparse.ArgumentParser(description="Knowledge CLI - Browse repair experience and tool history.")
    parser.add_argument("command", choices=["list", "search", "summarize"], help="Command to run")
    parser.add_argument("--query", help="Search query (required for search)")
    parser.add_argument("--limit", type=int, default=10, help="Max records to show")
    parser.add_argument("--top", type=int, default=5, help="Top N categories in summarize")
    parser.add_argument("--source", help="Filter by source (tool, skill, fix, etc.)")
    parser.add_argument("--status", help="Filter by status (success, failure)")
    parser.add_argument("--type", help="Filter by problem type")
    parser.add_argument("--config", help="Path to config directory (optional)")

    args = parser.parse_args()

    # Resolve knowledge directory
    base_dir = Path(os.getcwd())
    knowledge_dir = base_dir / "knowledge"
    
    # If CORPS_KNOWLEDGE_DIR is set, use it
    env_knowledge_dir = os.getenv("CORPS_KNOWLEDGE_DIR")
    if env_knowledge_dir:
        knowledge_dir = Path(env_knowledge_dir)
    else:
        # fallback to ~/.config/corps/knowledge
        knowledge_dir = Path.home() / ".config" / "corps" / "knowledge"

    store = ProblemKnowledgeStore(knowledge_dir)
    filter_obj = RecordFilter(args.source, args.status, args.type)

    if args.command == "list":
        records = store.list_all_records()
        filtered = [r for r in records if filter_obj.matches(r)]
        print(f"Knowledge dir: {knowledge_dir}")
        print(f"Mode: list, Limit: {args.limit}")
        if filter_obj.isActive():
            print(f"Filters: source={args.source}, status={args.status}, type={args.type}")
        print()
        print_records(filtered[:args.limit])

    elif args.command == "search":
        if not args.query:
            print("Error: --query is required for search command")
            sys.exit(1)
        # We get more and then filter to stay accurate to the limit
        records = store.search_records(args.query, limit=args.limit * 5)
        filtered = [r for r in records if filter_obj.matches(r)]
        print(f"Knowledge dir: {knowledge_dir}")
        print(f"Mode: search, Query: {args.query}, Limit: {args.limit}")
        print()
        print_records(filtered[:args.limit])

    elif args.command == "summarize":
        records = store.list_all_records()
        filtered = [r for r in records if filter_obj.matches(r)]
        print(f"Knowledge dir: {knowledge_dir}")
        print(f"Mode: summarize, Top: {args.top}")
        print(f"Total records: {len(filtered)}")
        print()
        
        print_count_section("By source", filtered, lambda r: r.source or "(unknown)", args.top)
        print_count_section("By status", filtered, lambda r: r.status or "(unknown)", args.top)
        print_count_section("By problem type", filtered, lambda r: r.problemType or "(unknown)", args.top)
        print_count_section("By classification", filtered, lambda r: r.classification or r.problemType or "(uncategorized)", args.top)

if __name__ == "__main__":
    main()

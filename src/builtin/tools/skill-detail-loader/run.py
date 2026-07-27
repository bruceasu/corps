import argparse
import os
import sys
from pathlib import Path

def add_runtime_path() -> None:
    # Try to find _runtime relative to this script or via env
    scripts_dir = os.getenv("CORPS_PYTHON_SCRIPTS_DIR")
    if scripts_dir:
        runtime_dir = Path(scripts_dir).resolve() / "_runtime"
    else:
        # Based on current structure: src/builtin/tools/skill-detail-loader/run.py
        # _runtime is at src/_runtime
        runtime_dir = Path(__file__).resolve().parents[3] / "_runtime"
    
    if not runtime_dir.exists():
        # Fallback for different envs
        runtime_dir = Path(__file__).resolve().parents[0] / "_runtime"

    sys.path.insert(0, str(runtime_dir))

add_runtime_path()

try:
    from tool_runtime import emit_result, failure, success
except ImportError:
    # Very basic fallback if runtime isn't found
    def emit_result(res): print(res)
    def failure(n, e): return {"ok": False, "toolName": n, "error": e}
    def success(n, o, d): return {"ok": True, "toolName": n, "output": o, "data": d}

def resolve_skills_dirs():
    dirs = []
    # Builtin skills
    builtin = Path(__file__).resolve().parents[2] / "skills"
    if builtin.is_dir():
        dirs.append(builtin)
    
    # User skills from env
    env_skills = os.getenv("CORPS_SKILLS_DIR")
    if env_skills:
        p = Path(env_skills).expanduser().resolve()
        if p.is_dir():
            dirs.append(p)
            
    # Default user skills
    default_user = Path.home() / ".config" / "corps" / "skills"
    if default_user.is_dir():
        dirs.append(default_user)
        
    return dirs

def main():
    parser = argparse.ArgumentParser(description="Load detailed skill documentation.")
    parser.add_argument("--name", required=True, help="Name of the skill")
    args = parser.parse_args()

    skill_name = args.name
    skill_dirs = resolve_skills_dirs()
    
    found_home = None
    for d in skill_dirs:
        maybe = d / skill_name
        if maybe.is_dir():
            found_home = maybe
            break
            
    if not found_home:
        emit_result(failure("skill-detail-loader", f"Skill '{skill_name}' not found in {skill_dirs}"))
        return

    # Try to find documentation
    doc_content = ""
    for candidate in ("SKILL.md", "skill.md", "README.md"):
        doc_file = found_home / candidate
        if doc_file.is_file():
            doc_content = doc_file.read_text(encoding="utf-8")
            break
            
    # Try to find YAML definition
    yaml_content = ""
    for candidate in ("skill.yaml", "skill.yml", "skill.json"):
        yaml_file = found_home / candidate
        if yaml_file.is_file():
            yaml_content = yaml_file.read_text(encoding="utf-8")
            break

    if not doc_content and not yaml_content:
        emit_result(failure("skill-detail-loader", f"Skill '{skill_name}' found at {found_home} but has no documentation or YAML."))
        return

    output = f"## Documentation for Skill: {skill_name}\n\n"
    if doc_content:
        output += doc_content + "\n\n"
    else:
        output += "No detailed SKILL.md found.\n\n"
        
    if yaml_content:
        output += "## Technical Definition (YAML):\n\n```yaml\n" + yaml_content + "\n```"
        
    emit_result(success("skill-detail-loader", output, {
        "name": skill_name,
        "path": str(found_home).replace("\\", "/"),
        "has_doc": bool(doc_content),
        "has_yaml": bool(yaml_content)
    }))

if __name__ == "__main__":
    main()

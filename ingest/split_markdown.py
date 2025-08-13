import argparse
import json
import os
import re
from pathlib import Path

# Simple splitter: split by headings and enforce max chars
MAX_CHARS = 1800  # ~300-400 tokens rough

def iter_md_files(root: Path):
    for p in root.rglob("*.md"):
        if ".git" in p.parts:
            continue
        yield p

def split_text(text: str):
    # Split by headings while keeping them
    parts = re.split(r"(?m)^(#+\s.*)$", text)
    chunks = []
    buf = ""
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i+1] if i+1 < len(parts) else ""
        section = f"{heading}\n{body}".strip()
        # Enforce max length
        while len(section) > MAX_CHARS:
            chunks.append(section[:MAX_CHARS])
            section = section[MAX_CHARS:]
        if section:
            chunks.append(section)
    # Fallback if no headings
    if not chunks:
        t = text.strip()
        while len(t) > MAX_CHARS:
            chunks.append(t[:MAX_CHARS])
            t = t[MAX_CHARS:]
        if t:
            chunks.append(t)
    return chunks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="Path to local repo root")
    ap.add_argument("--out", required=True, help="Output JSONL path")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(out, "w", encoding="utf-8") as fw:
        # Scan both 'days/' and repo root for Markdown files
        targets = [repo / "days", repo]  # add others if needed
        seen = set()
        for target in targets:
            if not target.exists():
                continue
            for md in iter_md_files(target):
                # Skip duplicates when repo == days parent
                if str(md) in seen:
                    continue
                seen.add(str(md))
            text = md.read_text(encoding="utf-8", errors="ignore")
            chunks = split_text(text)
            for idx, ch in enumerate(chunks):
                doc = {
                    "id": f"{md.stem}_{idx}",
                    "text": ch,
                    "metadata": {
                        "path": str(md.relative_to(repo)),
                        "file": md.name,
                        "stem": md.stem,
                    },
                }
                fw.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1
    print(f"✅ Wrote {count} chunks -> {out}")

if __name__ == "__main__":
    main()

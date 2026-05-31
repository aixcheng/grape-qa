import os
import re
import glob

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "texts")
_cache = None  # {name: {name, category, summary, sections}}


def _parse_all():
    global _cache
    if _cache is not None:
        return _cache

    _cache = {}
    if not os.path.exists(DATA_DIR):
        return _cache

    for file_path in glob.glob(os.path.join(DATA_DIR, "*.txt")):
        name = os.path.basename(file_path).replace(".txt", "")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        category = "disease" if "病" in name else "pest"
        lines = content.strip().split("\n")
        summary = ""
        for line in lines:
            line = line.strip()
            if line and not re.match(r"^\d+\.", line):
                summary = line[:120]
                break

        sections = []
        parts = re.split(r"\n(?=\d+\.\s)", content)
        for part in parts:
            m = re.match(r"(\d+)\.\s*(.+?)[：:]", part)
            if m:
                title = m.group(2).strip()
                body = part[m.end():].strip()
                sections.append({"title": title, "content": body})

        _cache[name] = {
            "name": name,
            "category": category,
            "summary": summary,
            "sections": sections,
        }

    return _cache


def list_knowledge(category=None, search=None):
    all_data = _parse_all()
    result = []
    for item in all_data.values():
        if category and item["category"] != category:
            continue
        if search and search.lower() not in item["name"].lower():
            continue
        result.append({
            "name": item["name"],
            "category": item["category"],
            "summary": item["summary"],
        })
    return result


def get_knowledge(name):
    all_data = _parse_all()
    return all_data.get(name)

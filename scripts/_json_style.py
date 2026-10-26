"""Dump JSON in the dataset style: 2-space indent, arrays of scalars inline."""
import json


def dumps(obj, level=0):
    pad = "  " * level
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f'{pad}  {json.dumps(k, ensure_ascii=False)}: {dumps(v, level + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in obj) + "]"
        items = [f"{pad}  {dumps(x, level + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(obj, ensure_ascii=False)


def load_dump(path, edit):
    from pathlib import Path
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    edit(d)
    p.write_text(dumps(d) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import glob, sys
    for f in sorted(glob.glob("core/scanner_mode/datasets/*.json")):
        raw = open(f, encoding="utf-8").read()
        print(f, dumps(json.loads(raw)) + "\n" == raw, dumps(json.loads(raw)) == raw)

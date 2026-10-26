"""Markdown -> PDF for the project's guides:  python scripts/md_to_pdf.py docs/viva_guide.md [out.pdf]

Needs the system Python's `markdown` and `weasyprint` packages (not part of the backend requirements).
"""

import sys
from pathlib import Path

import markdown
from weasyprint import HTML

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
        @bottom-center { content: counter(page) " / " counter(pages); font: 9pt 'Noto Sans', sans-serif; color: #666; }
        @top-right { content: string(doctitle); font: 8.5pt 'Noto Sans', sans-serif; color: #888; } }
html { font: 10.2pt/1.5 'Noto Sans', 'Liberation Sans', sans-serif; color: #1c1c1c; }
h1 { string-set: doctitle content(); font-size: 22pt; margin: 0 0 6pt; color: #8b1a1a; border-bottom: 2px solid #8b1a1a; padding-bottom: 4pt; }
h2 { font-size: 15pt; margin: 20pt 0 6pt; color: #8b1a1a; border-bottom: 1px solid #ddd; padding-bottom: 2pt; break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; color: #333; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 10pt 0 3pt; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
code { font: 8.6pt 'Noto Sans Mono', 'Liberation Mono', monospace; background: #f3f0ea; padding: 0 2pt; border-radius: 2pt; }
pre { font: 8pt/1.35 'Noto Sans Mono', 'Liberation Mono', monospace; background: #f6f4ef; border: 1px solid #e2ddd2; padding: 6pt 8pt;
      white-space: pre-wrap; word-break: break-word; break-inside: avoid; border-radius: 3pt; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 8.8pt; break-inside: auto; }
th { background: #8b1a1a; color: #fff; text-align: left; padding: 3pt 5pt; }
td { border: 1px solid #ddd; padding: 3pt 5pt; vertical-align: top; }
tr:nth-child(even) td { background: #faf8f4; }
tr { break-inside: avoid; }
blockquote { margin: 8pt 0; padding: 5pt 10pt; border-left: 3px solid #8b1a1a; background: #fbf3f3; color: #333; break-inside: avoid; }
hr { border: 0; border-top: 1px solid #ddd; margin: 14pt 0; }
a { color: #8b1a1a; text-decoration: none; }
"""


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".pdf")
    body = markdown.markdown(src.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "sane_lists", "toc"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    HTML(string=html, base_url=str(src.parent)).write_pdf(out)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

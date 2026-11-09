# Re-downloads the evaluation source documents. We do not commit the raw
# files (licensing and size), so run this once to fetch them into
# eval/data/. Needs the backend venv for pypdf (to read the PDFs):
#
#   backend/.venv/bin/python eval/download_data.py
#
# Sources and licenses are listed in eval/README.md.

import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "data", "public")
ML = os.path.join(HERE, "data", "ml")
LARGE = os.path.join(HERE, "data", "large")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tutor-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def wikipedia(title: str, out_path: str):
    # full plain-text extract of an article (CC BY-SA)
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "extracts",
        "explaintext": "1", "redirects": "1", "titles": title,
    })
    data = json.loads(_get(f"https://en.wikipedia.org/w/api.php?{q}"))
    pages = data["query"]["pages"]
    text = next(iter(pages.values())).get("extract", "")
    open(out_path, "w").write(text)
    print(f"  {len(text):>7} chars  {os.path.basename(out_path)}")


def pdf_pages(url: str, out_path: str, first_pages: int | None = None):
    from pypdf import PdfReader
    import io
    raw = _get(url)
    reader = PdfReader(io.BytesIO(raw))
    n = len(reader.pages) if first_pages is None else min(first_pages, len(reader.pages))
    text = "\n\n".join((reader.pages[i].extract_text() or "") for i in range(n))
    open(out_path, "w").write(text)
    print(f"  {len(text):>7} chars  {os.path.basename(out_path)} ({n} pages)")


def openstax(url: str, out_path: str):
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self):
            super().__init__(); self.skip = 0; self.out = []

        def handle_starttag(self, t, a):
            if t in ("script", "style", "nav", "header", "footer", "aside"):
                self.skip += 1

        def handle_endtag(self, t):
            if t in ("script", "style", "nav", "header", "footer", "aside") and self.skip:
                self.skip -= 1

        def handle_data(self, d):
            if not self.skip and len(d.strip()) > 1:
                self.out.append(d.strip())

    p = Text(); p.feed(_get(url).decode("utf-8", "ignore"))
    text = "\n".join(l for l in p.out if len(l) > 40)
    open(out_path, "w").write(text)
    print(f"  {len(text):>7} chars  {os.path.basename(out_path)}")


def main():
    os.makedirs(PUBLIC, exist_ok=True)
    os.makedirs(ML, exist_ok=True)

    print("D1 public (general knowledge):")
    wikipedia("Photosynthesis", os.path.join(PUBLIC, "photosynthesis.txt"))
    wikipedia("Plate tectonics", os.path.join(PUBLIC, "plate_tectonics.txt"))
    wikipedia("French Revolution", os.path.join(PUBLIC, "french_revolution.txt"))
    wikipedia("Supply and demand", os.path.join(PUBLIC, "supply_and_demand.txt"))
    openstax(
        "https://openstax.org/books/biology-2e/pages/8-2-the-light-dependent-reactions-of-photosynthesis",
        os.path.join(PUBLIC, "openstax_photosynthesis.txt"),
    )

    print("D2 ML/CS (stakeholder):")
    wikipedia("Gradient descent", os.path.join(ML, "gradient_descent.txt"))
    wikipedia("Overfitting", os.path.join(ML, "overfitting.txt"))
    wikipedia("Backpropagation", os.path.join(ML, "backpropagation.txt"))
    wikipedia("Support vector machine", os.path.join(ML, "support_vector_machine.txt"))
    pdf_pages("https://arxiv.org/pdf/1609.04747", os.path.join(ML, "ruder_gradient_descent_survey.txt"))
    pdf_pages("https://cs229.stanford.edu/main_notes.pdf", os.path.join(ML, "cs229_supervised_learning.txt"), first_pages=24)

    print("D3 novel (synthetic, written in novel_docs.py):")
    from novel_docs import write_novel
    write_novel()

    print("D4 large (concatenated reader for the big-document task):")
    write_large()


def write_large():
    # Build one big reader by concatenating the ML docs, with the Ruder survey
    # (which covers Adam and other variants) placed LAST so its content sits
    # past the single-call baseline's 150k-char cutoff. Our system and the RAG
    # baseline retrieve, so they reach the tail; the single call truncates and
    # loses it. That is the honest large-document condition.
    order = [
        "overfitting.txt", "backpropagation.txt", "support_vector_machine.txt",
        "gradient_descent.txt", "cs229_supervised_learning.txt",
        "ruder_gradient_descent_survey.txt",
    ]
    os.makedirs(LARGE, exist_ok=True)
    parts = []
    for name in order:
        path = os.path.join(ML, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="ignore") as f:
                parts.append(f"\n\n===== SECTION: {name} =====\n\n" + f.read())
    text = "".join(parts)
    out = os.path.join(LARGE, "big_ml_reader.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {out} ({len(text)} chars)")


if __name__ == "__main__":
    main()

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
SCHOOL = os.path.join(HERE, "data", "school")
COLLEGE = os.path.join(HERE, "data", "college")


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


def d2l_optimization(out_path: str):
    # Concatenate the optimization chapter of Dive into Deep Learning (CC BY-SA
    # 4.0) from the book's GitHub source. These sections are dense with specific
    # learning rates, update rules, and worked examples, so questions must come
    # from the text rather than general knowledge.
    # Scope to the taught topic (Adam and the two methods it combines) so the
    # whole relevant source fits the eval's question/grounding window. The topic
    # section leads, then its components, so a prefix read still covers the topic.
    base = "https://raw.githubusercontent.com/d2l-ai/d2l-en/master/chapter_optimization/"
    sections = ["adam.md", "momentum.md", "rmsprop.md"]
    parts = []
    for s in sections:
        parts.append(f"\n\n===== {s} =====\n\n" + _clean_d2l(_get(base + s).decode("utf-8", "ignore")))
    text = "".join(parts)
    open(out_path, "w").write(text)
    print(f"  {len(text):>7} chars  {os.path.basename(out_path)}")


def _clean_d2l(text: str) -> str:
    # The raw markdown repeats the same algorithm as PyTorch, MXNet, and
    # TensorFlow code, and carries d2lbook directives and math delimiters. That
    # boilerplate dominates the chunks and drowns out the prose, so we keep the
    # explanatory text and formulas and drop the noise. Content is unchanged.
    import re
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)        # drop code blocks
    text = re.sub(r"`{1,2}[^`]*`{1,2}", "", text)                 # inline code / tab markers
    text = re.sub(r":[a-z_]+:`[^`]*`", "", text)                  # :numref:`...` cross-refs
    text = re.sub(r"^\s*:[a-z_]+:.*$", "", text, flags=re.MULTILINE)  # :label: lines
    text = re.sub(r":[a-z_]+:", " ", text)                       # bare inline markers like :cite:
    text = text.replace("$$", " ").replace("$", " ")             # unwrap math, keep formula text
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    os.makedirs(PUBLIC, exist_ok=True)
    os.makedirs(ML, exist_ok=True)
    os.makedirs(SCHOOL, exist_ok=True)
    os.makedirs(COLLEGE, exist_ok=True)

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

    print("D5 school (Grade 9 Mathematics, Siyavula, CC BY 3.0):")
    pdf_pages(
        "https://www.siyavula.com/downloads/books/maths/Gr9A_Mathematics_Learner_Eng.pdf",
        os.path.join(SCHOOL, "siyavula_maths_gr9.txt"), first_pages=110,
    )

    print("D6 college (Dive into Deep Learning optimization chapter, CC BY-SA 4.0):")
    d2l_optimization(os.path.join(COLLEGE, "d2l_optimization.txt"))


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

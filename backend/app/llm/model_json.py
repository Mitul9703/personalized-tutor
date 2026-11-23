# parse JSON written by the model without losing LaTeX.
#
# the agents write markdown with LaTeX math ($\eta$, $\nabla f$, $\frac{1}{2}$)
# inside JSON strings, and models often emit a single backslash where JSON needs
# two. that breaks in two ways:
#   - "\eta", "\alpha", "\mathbb" are invalid JSON escapes, so json.loads fails
#     and the whole tool call is lost (a planner that returns nothing leaves the
#     builder with no source chunks, so every slide comes out "supplementary").
#   - "\nabla", "\frac", "\theta", "\beta" start with valid escapes (\n \f \t \b),
#     so they parse, but silently turn into a newline / form feed / tab plus
#     "abla", "rac", "heta", "eta".
# we double a lone backslash before a letter when it is clearly LaTeX, then parse.

import json
import re

# LaTeX commands that start with a letter JSON treats as an escape (b f n r t u).
# a lone backslash before any other letter is never a valid JSON escape, so it
# is always doubled; for these letters we only double known LaTeX commands, so
# real "\n" newlines and "é" unicode escapes keep working.
_ESCAPE_LETTER_COMMANDS = {
    "nabla", "neq", "ne", "nu", "not", "notin", "ni", "nonumber", "neg", "nleq", "ngeq",
    "frac", "forall", "flat",
    "theta", "Theta", "tau", "times", "text", "textbf", "textit", "textrm", "texttt",
    "top", "to", "tilde", "triangle", "triangledown", "tfrac", "tan", "tanh", "trace",
    "beta", "bar", "bf", "boldsymbol", "bm", "big", "bigl", "bigr", "bigg", "binom",
    "bot", "bullet", "backslash", "begin", "bmatrix",
    "rho", "right", "rangle", "rightarrow", "rceil", "rfloor", "rm", "rvert", "rVert",
    "underline", "upsilon", "uparrow", "underbrace",
}

_TOKEN = re.compile(r"\\\\|\\([A-Za-z]+)")


def _fix(match: re.Match) -> str:
    word = match.group(1)
    if word is None:                      # an already-escaped backslash pair
        return match.group(0)
    if word[0] not in "bfnrtu" or word in _ESCAPE_LETTER_COMMANDS:
        return "\\\\" + word
    return match.group(0)                 # a real JSON escape such as \n or é


def loads(text: str):
    """json.loads for model output, keeping LaTeX backslashes intact."""
    return json.loads(_TOKEN.sub(_fix, text or ""))

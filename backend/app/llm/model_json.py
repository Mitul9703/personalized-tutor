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


# some models also send a LaTeX backslash as a JSON escape that is valid but
# wrong, e.g. "\u0007eta" (bell + "eta") for "\eta". that parses cleanly, so the
# fix above never sees it; we repair the decoded strings instead.
#   - bell, backspace, vertical tab and form feed never belong in study text, so
#     before a letter they always stand for a lost backslash (\b and \f also ate
#     the command's first letter, so we put it back).
#   - tab, newline and carriage return are real text, so inside $...$ math we
#     only repair them before a known command (\theta, \nabla, \right, ...).
_CONTROL_BEFORE_LETTER = re.compile(r"([\x07\x08\x0b\x0c])(?=[A-Za-z])")
_CONTROL_AS = {"\x07": "\\", "\x08": "\\b", "\x0b": "\\v", "\x0c": "\\f"}
_MATH = re.compile(r"\$\$.+?\$\$|\$[^$\n]*?\$|\$[^$]+?\$", re.DOTALL)
_WHITESPACE_COMMANDS = re.compile(
    # "not followed by a letter" rather than \b, so $\theta_t$ (underscore) matches
    r"\t(?=(?:heta|au|imes|ext|extbf|op|ilde|riangle|frac|anh|an)(?![A-Za-z]))"
    r"|\n(?=(?:abla|eq|e|u|ot|otin|i|onumber|eg|leq|geq)(?![A-Za-z]))"
    r"|\r(?=(?:ho|ight|angle|ightarrow|ceil|floor|m|Vert|vert)(?![A-Za-z]))"
)
_WHITESPACE_AS = {"\t": "\\t", "\n": "\\n", "\r": "\\r"}


def _repair_text(s: str) -> str:
    s = _CONTROL_BEFORE_LETTER.sub(lambda m: _CONTROL_AS[m.group(1)], s)
    return _MATH.sub(
        lambda m: _WHITESPACE_COMMANDS.sub(lambda w: _WHITESPACE_AS[w.group(0)], m.group(0)), s
    )


def _repair(value):
    if isinstance(value, str):
        return _repair_text(value)
    if isinstance(value, list):
        return [_repair(v) for v in value]
    if isinstance(value, dict):
        return {k: _repair(v) for k, v in value.items()}
    return value


def loads(text: str):
    """json.loads for model output, keeping LaTeX backslashes intact."""
    return _repair(json.loads(_TOKEN.sub(_fix, text or "")))

# The evaluation set. Each task is a (dataset, document, topic) triple: teach
# the topic, grounded in the document. The same tasks are run for our system
# and for every baseline, so the comparison is fair.

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    return os.path.join(HERE, "data", *parts)


TASKS = [
    # D1 public (general knowledge)
    {"dataset": "public", "doc": _p("public", "photosynthesis.txt"),
     "topic": "how the light-dependent reactions of photosynthesis work"},
    {"dataset": "public", "doc": _p("public", "plate_tectonics.txt"),
     "topic": "what drives the movement of tectonic plates"},
    {"dataset": "public", "doc": _p("public", "french_revolution.txt"),
     "topic": "the main causes of the French Revolution"},
    {"dataset": "public", "doc": _p("public", "supply_and_demand.txt"),
     "topic": "how supply and demand set a market price"},
    {"dataset": "public", "doc": _p("public", "openstax_photosynthesis.txt"),
     "topic": "the light-dependent reactions and the role of chlorophyll"},

    # D2 ML/CS (stakeholder)
    {"dataset": "ml", "doc": _p("ml", "gradient_descent.txt"),
     "topic": "how gradient descent minimizes a loss function"},
    {"dataset": "ml", "doc": _p("ml", "overfitting.txt"),
     "topic": "what overfitting is and how to reduce it"},
    {"dataset": "ml", "doc": _p("ml", "backpropagation.txt"),
     "topic": "how backpropagation computes gradients"},
    {"dataset": "ml", "doc": _p("ml", "support_vector_machine.txt"),
     "topic": "how a support vector machine separates two classes"},
    {"dataset": "ml", "doc": _p("ml", "ruder_gradient_descent_survey.txt"),
     "topic": "gradient descent variants like momentum and Adam"},
    {"dataset": "ml", "doc": _p("ml", "cs229_supervised_learning.txt"),
     "topic": "linear regression and the least squares cost function"},

    # D3 novel (synthetic, unknown to the model) -- for the learning metric,
    # where a famous topic would let the student answer from prior knowledge.
    {"dataset": "novel", "doc": _p("novel", "vernalis_tide.txt"),
     "topic": "what causes the Vernalis Tide and why it matters for fishing"},
    {"dataset": "novel", "doc": _p("novel", "kessler_sort.txt"),
     "topic": "how Kessler partitioning sorts a list"},

    # D4 large -- one big reader. The topic (Nadam) lives in the tail of the
    # document, past the single-call baseline's 150k cutoff, so retrieval is
    # the only way to reach it.
    {"dataset": "large", "doc": _p("large", "big_ml_reader.txt"),
     "topic": "the Nadam optimizer and how it combines Nesterov momentum with Adam"},

    # D5 school -- real Grade 9 school material (Siyavula Mathematics, CC BY 3.0),
    # dense with worked examples and specific numbers, so questions need the text.
    # Topics come from the early chapters (whole numbers, integers) so their
    # content sits within the eval's question/grounding window.
    {"dataset": "school", "doc": _p("school", "siyavula_maths_gr9.txt"),
     "topic": "adding, subtracting and multiplying integers, including the rules for negative numbers"},
    {"dataset": "school", "doc": _p("school", "siyavula_maths_gr9.txt"),
     "topic": "the properties of whole numbers: the identity element and the commutative, associative and distributive laws"},
    {"dataset": "school", "doc": _p("school", "siyavula_maths_gr9.txt"),
     "topic": "multiplying and dividing whole numbers, including long division and checking the answer"},

    # D6 college -- real college course material (Dive into Deep Learning
    # optimization chapter, CC BY-SA 4.0), with specific update rules and numbers.
    {"dataset": "college", "doc": _p("college", "d2l_optimization.txt"),
     "topic": "the Adam optimizer and how it combines momentum and RMSProp"},
    {"dataset": "college", "doc": _p("college", "d2l_optimization.txt"),
     "topic": "momentum and how a leaky average of past gradients smooths and speeds up updates"},
    {"dataset": "college", "doc": _p("college", "d2l_optimization.txt"),
     "topic": "RMSProp and how it adapts the step size per coordinate using a moving average of squared gradients"},
]


def load_doc(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()

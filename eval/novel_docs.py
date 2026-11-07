# Synthetic source documents for the learning metric.
#
# Why these exist: on a famous topic (gradient descent, photosynthesis) the
# simulated student already knows the answers, so no tutorial can show a
# learning gain. The control score hits the ceiling and the metric is blind.
# To measure teaching honestly we need material the model has never seen, so
# the ONLY way it can answer is if the tutorial taught it.
#
# These are clearly-fictional, self-contained topics with specific, definite
# facts (names, numbers, cause and effect). They are labeled synthetic on
# purpose: they are teaching fixtures, not claims about the real world. Edit
# freely; keep each fact specific and unguessable.

import os

HERE = os.path.dirname(os.path.abspath(__file__))
NOVEL_DIR = os.path.join(HERE, "data", "novel")

VERNALIS_TIDE = """The Vernalis Tide (A Fictional Oceanographic Phenomenon)

Note: this document describes an invented phenomenon for teaching purposes.

The Vernalis Tide is a seasonal upwelling that occurs along the eastern shelf
of the fictional Calder Sea. It happens once a year, in the local month of
Brumaire, and lasts between nine and eleven days. It is driven by the collision
of two water masses: the cold, dense Harran Current flowing south, and the warm,
less dense Melish Drift flowing north. Where they meet, the denser Harran water
sinks beneath the Melish water and pushes a band of deep water up toward the
surface. This rising deep water is what gives the tide its name.

The rising water carries a nutrient called pelagite, which sits on the sea floor
for most of the year. When pelagite reaches sunlight near the surface, it
triggers a rapid bloom of a microorganism called Calder plankton. The bloom
turns the surface water a distinctive pale violet, which is how coastal
observers know the tide has begun.

The bloom matters because Calder plankton is the only food source for the
ribbonfish, the main catch of the Calder coast. Ribbonfish spawn exactly during
the bloom, so the timing of the Vernalis Tide sets the entire fishing calendar.
If the Harran Current is weak in a given year, the upwelling is shallow, less
pelagite reaches the surface, the bloom is small, and the ribbonfish catch fails.
Fishers therefore watch the temperature of the Harran Current as an early warning:
a Harran Current warmer than four degrees Celsius predicts a weak tide.
"""

KESSLER_SORT = """Kessler Partitioning (A Fictional Sorting Method)

Note: this document describes an invented algorithm for teaching purposes.

Kessler partitioning is a method for sorting a list of numbers. It was designed
to be easy to run by hand. It works in rounds, and each round has two steps.

In the first step, called the anchor step, you pick the middle element of the
current list and call it the anchor. You do not move the anchor yet.

In the second step, called the sweep step, you walk through the list from left to
right. Every element smaller than the anchor is copied into a left pile, in the
order you meet it. Every element larger than the anchor is copied into a right
pile. Elements equal to the anchor are placed in a separate equal pile. At the
end of the sweep you rebuild the list as: left pile, then equal pile, then right
pile.

You then repeat the whole process on the left pile and on the right pile
separately. The equal pile is never touched again, because every element in it is
already in its final place. The method stops when every pile has one element or
is empty.

The key property of Kessler partitioning is that the equal pile is finalized
after a single round, so lists with many repeated values sort very fast. Its main
weakness is that each round copies elements into new piles instead of swapping in
place, so it uses extra memory equal to the size of the list. Because of this
copying, Kessler partitioning is taught as a teaching tool rather than used in
production systems.
"""

DOCS = {"vernalis_tide.txt": VERNALIS_TIDE, "kessler_sort.txt": KESSLER_SORT}


def write_novel():
    os.makedirs(NOVEL_DIR, exist_ok=True)
    for name, text in DOCS.items():
        with open(os.path.join(NOVEL_DIR, name), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"wrote {len(DOCS)} novel docs to {NOVEL_DIR}")


if __name__ == "__main__":
    write_novel()

"""Tools for rendering a list of verse references/texts PDF via LaTeX.

Works via shelling out to `pdflatex`, uses the `flashcards` document class, 
and relies on the `tabularx` package peing available.
"""
import os
import subprocess
import tempfile
from dataclasses import dataclass

import pystache

from .model import Card, Verse


LATEX_FONT_SIZES = [f"\\{sz}" for sz in "tiny scriptsize footnotesize small normalsize large Large LARGE huge Huge".split()]
FLASHCARD_PAPER_SIZES = ["avery5371", "avery5388"]


@dataclass
class Option:
    info: str
    kind: type = str
    ctrl: str = "text"
    choices: list | None = None
    default: object | None = None

    def validate(self, value) -> object:
        if not isinstance(value, self.kind):
            value = self.kind(value)
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"'{value}' is not in the list of allowed values")
        return value

@dataclass
class GlobalOption(Option):
    flatten: callable = lambda name, value: None


DOC_OPTION_MAP = {
    "paper_size": GlobalOption("Label paper format supported by LaTeX `flashcards` document class.", 
        choices=FLASHCARD_PAPER_SIZES, ctrl="select", default="avery5388", 
        flatten=(lambda name, value: value)),
    "frame": GlobalOption("Draw a border/frame around the card contents.", 
        kind=bool, ctrl="checkbox", default=False, 
        flatten=(lambda name, value: name if value else None)),
    "grid": GlobalOption("Draw lines on the sheet where the card perforation is.", 
        kind=bool, ctrl="checkbox", default=True, 
        flatten=(lambda name, value: name if value else None)),
}

CARD_OPTION_MAP = {
    "paragraphs": Option("Separate each verse into its own paragraph.", 
        kind=bool, ctrl="checkbox", default=True),
    "columns": Option("Typeset verse texts into two columns.", 
        kind=bool, ctrl="checkbox", default=False),
    "ragged_right": Option("Left-align verse texts (ragged-right) instead of centering.", 
        kind=bool, ctrl="checkbox", default=True),
    "title_size": Option("LaTeX font size for reference/title.", 
        choices=LATEX_FONT_SIZES, ctrl="select", default="\\Huge"),
    "text_size": Option("LaTeX font size for verse text.", 
        choices=LATEX_FONT_SIZES, ctrl="select", default="\\normalsize"),
    "num_size": Option("LaTeX font size for verse numbers.",
        choices=LATEX_FONT_SIZES, ctrl="select", default="\\small"),
}


def global_options(options: dict[str, object] | None = None) -> str:
    """Validate/default and render a set of global options to document class attributes."""
    if options is None:
        options = {}
    flats = []
    for okey, odef in DOC_OPTION_MAP.items():
        goval = odef.validate(options.get(okey, odef.default))
        flats.append(odef.flatten(okey, goval))
    return ','.join(filter(None, flats))


def optimized_card(card: Card) -> Card:
    """Make sure the card's options are fully validated/defaulted."""
    for okey, odef in CARD_OPTION_MAP.items():
        card.options[okey] = odef.validate(card.options.get(okey, odef.default))
    return card


CARD_SHEET_TEMPLATE = \
r"""{{=<< >>=}}\documentclass[<<doc_options>>]{flashcards}
\usepackage{multicol}
\begin{document}
<<#cards>>
\begin{flashcard}{<<options.title_size>>{<<title>>}}<<#options.columns>>
\begin{multicols}{2}<</options.columns>><<#options.ragged_right>>
\raggedright<</options.ragged_right>>
<<#verses>><<#options.paragraphs>>\par<</options.paragraphs>>\textsuperscript{\textit{<<options.num_size>>{<<num>>}}}<<options.text_size>>{<<text>>}
<</verses>><<#options.columns>>\end{multicols}
<</options.columns>>
\end{flashcard}
<</cards>>
\end{document}
"""


def render_latex(cards: list[Card], options: dict[str, object] | None = None, filename: str | None = None) -> str:
    """Render a batch of cards as LaTeX and return the filename used.

    Used internally by `render_pdf` (where the `filename` is explicitly set).
    If `filename` is not set, generates one with `mkstemp`.

    `options` is a dictionary of global/document options (allowed to be empty/defaulted).
    """
    if filename is None:
        scratch_fd, filename = tempfile.mkstemp(suffix=".tex")
        os.close(scratch_fd)

    rnd = pystache.Renderer(escape=lambda s: s)
    template = pystache.parse(CARD_SHEET_TEMPLATE)
    context = {
        "doc_options": global_options(options),
        "cards": [optimized_card(c) for c in cards],
    }
    with open(filename, "wt", encoding="utf-8") as fd:
        print(rnd.render(template, context), file=fd)

    return filename


def render_pdf(cards: list[Card], options: dict[str, object] = {}, keep_temp_dir: bool = False) -> str:
    """Render a batch of verse cards into a PDF file and return its path.
    
    Generates a temporary directory in which to generate/render LaTeX files.
    Moves the resulting PDF into a temp file outside that temp directory.
    Removes the temp directory _unless_ `keep_temp_dir` is True.
    """
    
    with tempfile.TemporaryDirectory(delete=(not keep_temp_dir)) as temp_dir:
        render_latex(cards, options=options, filename=os.path.join(temp_dir, "source.tex"))
        subprocess.run(['pdflatex', 'source.tex'], cwd=temp_dir, check=True)
        
        scratch_fd, out_file = tempfile.mkstemp(suffix=".pdf")
        os.close(scratch_fd)
        os.rename(os.path.join(temp_dir, "source.pdf"), out_file)

    return out_file


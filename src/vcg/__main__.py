import sys
import uuid
from dataclasses import dataclass

from flask import Flask, abort, flash, request, render_template, send_file, session

from .bible import BibleBooks, VerseRef, parse_ref
from .render import DOC_OPTION_MAP, CARD_OPTION_MAP, render_pdf, render_latex


app = Flask(__name__)
app.config["SECRET_KEY"] = b"a super secret key no one will ever guess"

bb = BibleBooks.fromfile()
bb_pretty_map = list(bb.pretty_names())

@dataclass
class Verse:
    num: int
    text: str


@dataclass
class Card:
    """A single reference/body verse card datum."""
    title: str          # Combined text-reference for verse as entered by user
    verses: list[Verse] # The actual verses 
    uuid: str           # Deletion key


@app.route("/", methods=["GET", "POST"])
def index():
    cards = session.get("cards", [])
    print("\n".join(map(repr, cards)))
    
    match request.form.get("action"):
        case "Add":
            session["book"] = book = request.form["book"]
            session["chapvers"] = chapvers = request.form["chapvers"]
            view_title = f"{bb.pretty_name(book)} {chapvers}"
            parse_title = f"{book} {chapvers}"
            try:
                verses = [{"num": v.verse, "text": bb[v]} for v in parse_ref(parse_title, bb)]
            except Exception as err:
                flash(f"Error parsing reference '{title}': {err}", "error")
            else:
                cards.append({"title": view_title, "verses": verses, "uuid": str(uuid.uuid4())})
                session["cards"] = cards
                session["chapvers"] = ""
        case "Reset":
            del session["cards"]
            del session["book"]
            del session["chapvers"]
        case "PDF":
            pdf_file = render_pdf(session["cards"])
            return send_file(pdf_file)
        case "LaTeX":
            tex_file = render_latex(session["cards"])
            return send_file(tex_file, mimetype="text/x-tex")
    
    return render_template("index.html", 
        bookmap=bb_pretty_map,
        card_option_map=CARD_OPTION_MAP)

@app.route("/ajax/verse/<uuid>/delete", methods=["POST"])
def delete_verse(uuid: str):
    cards = session.get("cards", [])
    for c in cards:
        if c["uuid"] == uuid:
            cards.remove(c)
            session.modified = True
            return "OK"
    abort(404)


@app.route("/ajax/verse/<uuid>/options", methods=["PUT"])
def set_card_options(uuid: str):
    cards = session.get("cards", [])
    print(request.form)
    for c in cards:
        if c["uuid"] == uuid:
            c["options"] = coptions = c.get("options", {})
            for okey, odef in CARD_OPTION_MAP.items():
                coptions[okey] = odef.validate(request.form.get(okey, odef.kind()))
            session.modified = True
            print(cards)
            return "OK"
    abort(404)

def main(argv: list[str]):
    app.run(host="localhost", port=1769, debug=True)


def entry():
    main(sys.argv)
    sys.exit(0)
    

if __name__ == "__main__":
    entry()

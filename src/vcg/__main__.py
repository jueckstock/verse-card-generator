import os
import sys
import uuid
from dataclasses import dataclass

from cachelib.simple import SimpleCache
from flask import Flask, abort, flash, request, render_template, send_file, session
from flask_htmx import HTMX, make_response
from flask_session.cachelib import CacheLibSessionInterface

from .bible import BibleBooks, VerseRef, parse_ref
from .render import DOC_OPTION_MAP, CARD_OPTION_MAP, render_pdf, render_latex


app = Flask(__name__)
app.config["SECRET_KEY"] = b"a super secret key no one will ever guess"
app.session_interface = CacheLibSessionInterface(client=SimpleCache(default_timeout=0))
htmx = HTMX(app)


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


def get_cache_file() -> tuple[str | None, str | None]:
    cache_file, mime_type = session.get("preview_cache_file"), session.get("preview_mime_type")
    if cache_file:
        if not os.path.exists(cache_file):
            print(f"Ooops, cache file '{cache_file}' no longer exists?? Busting...")
            cache_file = None
            mime_type = None
    return cache_file, mime_type


def set_cache_file(filename: str, mime_type: str):
    if cache_file := session.get("preview_cache_file"):
        print(f"Deleting old cache file '{cache_file}'...")
        os.unlink(cache_file)
    session["preview_cache_file"] = filename
    session["preview_mime_type"] = mime_type


def bust_cache_file():
    if cache_file := session.get("preview_cache_file"):
        if os.path.exists(cache_file):
            os.unlink(cache_file)
        del session["preview_cache_file"]
        del session["preview_mime_type"]


@app.route("/", methods=["GET", "POST"])
def index():
    cards = session.get("cards", [])
    
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
                bust_cache_file()
        case "Reset":
            del session["cards"]
            del session["book"]
            del session["chapvers"]
            bust_cache_file()
    
    return make_response(
        render_template("index.html", 
            bookmap=bb_pretty_map,
            card_option_map=CARD_OPTION_MAP),
        push_url=False,
        trigger={"preview-update": True})


@app.delete("/ajax/card/<uuid>")
def delete_card(uuid: str):
    cards = session.get("cards", [])
    for c in cards:
        if c["uuid"] == uuid:
            cards.remove(c)
            session.modified = True
            bust_cache_file()
            return make_response("OK", push_url=False, trigger={"preview-update": True})
    abort(404)


@app.put("/ajax/card/<uuid>/options")
def set_card_options(uuid: str):
    cards = session.get("cards", [])
    for c in cards:
        if c["uuid"] == uuid:
            c["options"] = coptions = c.get("options", {})
            for okey, odef in CARD_OPTION_MAP.items():
                coptions[okey] = odef.validate(request.form.get(okey, odef.kind()))
            session.modified = True
            bust_cache_file()
            return make_response("OK", push_url=False, trigger={"preview-update": True})
    abort(404)


@app.post("/ajax/preview/config")
def preview_config():
    session["preview_fmt"] = request.form.get("fmt", "PDF")
    session["auto_update"] = True if request.form.get("auto", "off") == "on" else False
    bust_cache_file()
    return render_template("partials/preview-config-form.html")


@app.get("/ajax/preview/<fmt>")
def preview_output(fmt: str):
    return render_template("partials/preview-window.html", fmt=fmt)


@app.get("/ajax/preview-src/<fmt>")
def preview_output_src(fmt: str):
    if len(session.get("cards", [])) == 0:
        return "No preview available..."
   
    cache_file, mime_type = get_cache_file()
    if cache_file:
        print(f"Returning cached file '{cache_file}'")
        return send_file(cache_file, mimetype=mime_type)

    print(f"GENERATING {fmt} file")
    out_file = None
    mime_type = None
    match fmt:
        case "PDF":
            out_file = render_pdf(session["cards"])
        case "LaTeX":
            out_file = render_latex(session["cards"])
            mime_type = "text/x-tex"
        case _:
            abort(400)
    set_cache_file(out_file, mime_type)
    return send_file(out_file, mimetype=mime_type)
 

def main(argv: list[str]):
    app.run(host="localhost", port=1769, debug=True)


def entry():
    main(sys.argv)
    sys.exit(0)
    

if __name__ == "__main__":
    entry()

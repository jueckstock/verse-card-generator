'''Tools for parsing/expanding book/chapter/verse references.
'''
import re
from collections import namedtuple
from typing import Iterable, Optional

from .data import BibleBooks, VerseRef


RX_WS = re.compile(r"\s*")
RX_NAME = re.compile(r"([A-Za-z][A-Za-z0-9]*)\s+")
RX_NUM = re.compile(r"([0-9]+)\s*")

BB = BibleBooks.fromfile()


class ParseStream:
    def __init__(self, s: str):
        self._s = s
        self._pos = 0
        self.eat_ws()

    def eos(self) -> bool:
        return self._pos >= len(self._s) 

    def peek(self, span=1) -> str:
        return self._s[self._pos : self._pos + span]

    def eat(self, pat, return_group=0) -> Optional[str]:
        m = pat.match(self._s, pos=self._pos)
        if m:
            self._pos += len(m.group(0))
            return m.group(return_group)
        else:
            return None

    def eat_ws(self):
        self.eat(RX_WS)

    def read_name(self) -> str:
        name = self.eat(RX_NAME, return_group=1)
        if name is None:
            raise SyntaxError("expected name")
        return name
    
    def read_num(self) -> int:
        num = self.eat(RX_NUM, return_group=1)
        if num is None:
            raise SyntaxError("expected number")
        return int(num)

    def require(self, literal: str):
        if self.peek(len(literal)) != literal:
            raise SyntaxError(f"expected '{literal}'")
        self._pos += len(literal)
        self.eat_ws()

    def accept(self, literal: str) -> bool:
        if self.peek(len(literal)) == literal:
            self._pos += len(literal)
            self.eat_ws()
            return True
        else:
            return False


def parse_ref(ref: str, bb: BibleBooks = BB) -> Iterable[VerseRef]:
    ps = ParseStream(ref)
    book = None
    while not ps.eos():
        if not book:
            book = ps.read_name()
        chap = ps.read_num()
        ps.require(":")
        verse = ps.read_num()
        
        yield VerseRef(book, chap, verse)

        while not ps.eos():
            if ps.accept(","):
                verse = ps.read_num()
                yield VerseRef(book, chap, verse)
            elif ps.accept("-"):
                end_span = ps.read_num()
                if ps.accept(":"):
                    for cnum in range(chap, end_span):
                        last_verse = bb.last_verse(book, cnum)
                        for vnum in range(verse + 1, last_verse + 1):
                            yield VerseRef(book, cnum, vnum)
                        verse = 0
                    end_verse = ps.read_num()
                    chap = end_span
                else:
                    end_verse = end_span

                for vnum in range(verse+1, end_verse+1):
                    yield VerseRef(book, chap, vnum)
            elif ps.accept(";"):
                break
            else:
                raise SyntaxError(f"unexpected '{ps.peek()}'")


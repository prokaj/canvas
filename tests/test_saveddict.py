import json
import os
import tempfile
from contextlib import contextmanager

from canvas.coursedata import SavedDict


@contextmanager
def tmp_working_dir():  # type: ignore
    try:
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            yield tmp
    finally:
        os.chdir(cwd)


section_formats = {
    "canvas": """
\\documentclass[ucsb]{{ltxgy}}
\\useluatrue
\\letszam{{{letszam}}}
\\csoportnev{{{short_name}}}
\\begin{{document}}
    %\\def\\theenumfel{{\\realenumfel}}
    \\newpage
    \\nodue
    \\def\\hw#1 #2{{#2. heti feladatsor}}
    \\feladat{{f}}
    \\def\\PEfont{{\\mathbb}}

    \\begin{{gy}}{{{week}}}{{{date}}}
        \\exercises[\\withoutsol]{{{exs}}}
    \\end{{gy}}
    \\vfill
\\end{{document}}
%%%%%% Local Variables:
%%%%%% mode: latex
%%%%%% TeX-master: t
%%%%%% End:
""",
    "paper": """
\\documentclass[onpaper]{{ltxgy}}
\\useluatrue
\\letszam{{{letszam}}}
\\csoportnev{{{short_name}}}
\\begin{{document}}
    %\\def\\theenumfel{{\\realenumfel}}
    \\feladat{{f}}
    \\def\\PEfont{{\\mathbb}}

    \\begin{{gy}}{{{week}}}{{{date}}}
        \\exercises[\\withoutsol]{{{exs}}}
    \\end{{gy}}
    \\vfill
\\end{{document}}
%%%%%% Local Variables:
%%%%%% mode: latex
%%%%%% TeX-master: t
%%%%%% End:
""",
}


def test_saveddict() -> None:
    with tmp_working_dir() as tmp:
        formats = SavedDict("latex_formats.json", default=section_formats)
        assert len(formats) == 0
        assert repr(formats) == f'SavedDict("{tmp}/latex_formats.json")'
        assert formats["paper"] == section_formats["paper"]
        assert set(formats.keys()) == {"canvas", "paper"}
        assert repr(formats) == repr(section_formats)
        assert not os.path.exists("./latex_formats.json")
        formats.save()
        formats.reset()
        assert os.path.exists("./latex_formats.json")
        with open("./latex_formats.json") as f:
            assert json.load(f) == section_formats
        assert len(formats) == 0
        assert formats["paper"] == section_formats["paper"]
        assert set(formats.keys()) == {"canvas", "paper"}

import json
import logging
import os
import tempfile
from contextlib import contextmanager

from canvasapi.course import Course  # type: ignore

from canvas.coursedata import SavedCourseData, SavedDict


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


def test_saved_course_data(caplog) -> None:  # type: ignore
    with tmp_working_dir() as tmp:
        scd = SavedCourseData(files=".files.json", others=".others.json")  # type: ignore
        assert scd.files == {}  # type: ignore
        assert sorted(scd._dicts()) == sorted([("files", {}), ("others", {})])
        assert (
            repr(scd)
            == f'SavedCourseData(files="{tmp}/.files.json", others="{tmp}/.others.json")'
        )

        d = {"/a/b.pdf": 1, "/c": 2}
        scd.update(files=d)
        assert scd.files == d  # type: ignore

        scd.files["/d"] = 3  # type: ignore
        assert len(scd.files) == 3  # type: ignore
        assert scd.files["/d"] == 3  # type: ignore

        scd.save()
        scd.reset()
        assert os.path.exists(".files.json")
        assert not os.path.exists(".others.json")

        with caplog.at_level(logging.DEBUG, logger="canvas"):
            scd.register_updater("quizzes", lambda course: {"test/2022": 12})
            scd.update_from_canvas(Course(None, {}))
            assert caplog.record_tuples[0] == (
                "canvas",
                logging.WARNING,
                "No updater for files.",
            )

        assert scd._fields == ["files", "others"]
        assert scd.files == {}  # type: ignore
        assert scd.others == {}  # type: ignore

        scd.register_updater("files", lambda course: {"test/2022": 12})
        scd.update_from_canvas(Course(None, {}))
        assert scd.files == {"test/2022": 12}  # type: ignore

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="canvas"):
            scd.register_updater("others", lambda course: None)
            scd.update_from_canvas(Course(None, {}))
            assert caplog.record_tuples[-1] == (
                "canvas",
                logging.WARNING,
                "updater of others returned None. No update is done!",
            )

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="canvas"):
            scd.register_updater("others", lambda course: course.id)
            scd.update_from_canvas(Course(None, {}))
            a, b, c = caplog.record_tuples[-1]
            assert a == "canvas"
            assert b == logging.WARNING
            endofc = "No update is done!"
            lenc = len(endofc)
            assert c[-lenc:] == endofc

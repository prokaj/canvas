import datetime
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import yaml  # type: ignore
from canvasapi.course import Course  # type: ignore
from jinja2 import sandbox

from canvas.pandoc import pandoc_with_options


def noaccent(text: str) -> str:
    btext = unicodedata.normalize("NFKD", text).encode()
    return bytes(x for x in btext if int(x) < 128).decode("utf8")


vocab = {
    "elso ora": "first_section",
    "utolso ora": "last_section",
    "idopont": "time_slot",
    "csoport": "title",
    "rovidnev": "short_name",
    "szunetek": "breaks",
    "feladatok": "exs",
}


def normalize_key(key: str) -> str:
    key = key.strip()
    key = re.sub(r"\s+", " ", key)
    key = noaccent(key).lower()
    key = vocab.get(key, key)
    return key


@dataclass
class Header:
    first_section: datetime.date
    last_section: datetime.date
    breaks: List[datetime.date]
    title: str
    short_name: str
    time_slot: str
    template: str

    def __init__(self, header: dict) -> None:
        for k, v in header.items():
            setattr(self, normalize_key(k), v)

    def next_week(self, date: datetime.date) -> Tuple[datetime.date, int]:
        delta = 7 - ((date - self.first_section).days % 7)
        date = datetime.timedelta(days=delta) + date
        while date in self.breaks:
            date = datetime.timedelta(days=7) + date
        week = 1 + ((date - self.first_section).days // 7)
        return date, week


class Section:
    def __init__(self, section: dict, header: Header, data: dict):
        self.date = data["date"]

        if section is not None:
            for k, v in section.items():
                setattr(self, normalize_key(k), v)

        self.serial = data["serial"]
        self.week = data["week"]
        self.header = header

    def get(self, attr: str, default: Optional[Any] = None) -> Any:
        if hasattr(self, attr):
            return getattr(self, attr)
        return getattr(self.header, attr, default)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def next_week(self) -> Tuple[datetime.date, int]:
        return self.header.next_week(self.date)


def read_section(filename: str) -> Tuple[Header, List[Section]]:
    with open(filename) as f:
        lst = yaml.safe_load_all(f)
        header = Header(next(lst))
        sections = []
        date = header.first_section
        week = 1
        for serial, sec in enumerate(lst, start=1):
            sections.append(
                Section(sec, header, {"date": date, "serial": serial, "week": week})
            )
            date, week = sections[-1].next_week()

    return header, sections


def add_metablock(course: Course, text: str = "") -> str:  # type: ignore
    """`text` is a markdown document whitout preamble!
    A preambule containing coursedata is added.
    It is used in the `href.lua` filter!
    """
    meta = {
        "coursedata": {
            "base_url": f"{course._requester.original_url}/courses/{course.id}/"
        }
    }
    meta["coursedata"].update(course.get_fsdata())
    return "---\n".join(["", yaml.dump(meta), text])


def pandoc_sections(  # type: ignore
    course: Course,
    header: Header,
    sections: List[Section],
    until: Optional[datetime.date] = None,
    **kwargs: Any,
) -> str:
    """It assumes that yaml has a header with a template field.
    The template is Jinja2 template that can be rendered using
    in an enviroment containing: `header`, `sections` and `until`
    """

    if until is None:
        until = header.last_section

    env = sandbox.Environment()
    t = env.from_string(header.template)

    text = t.render(sections=sections, header=header, until=until)

    text = pandoc_with_options(
        text=add_metablock(course, text),
        src_format="markdown+link_attributes",
        out_format="html5",
        filters=["href.lua"],
        **kwargs,
    )

    return text

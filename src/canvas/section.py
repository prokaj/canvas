import datetime
import unicodedata
from dataclasses import dataclass
from typing import Any, Generator, List, Tuple

import yaml  # type: ignore


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
    key = noaccent(key.lower())
    key = vocab.get(key, key)
    return key


@dataclass
class Header:
    first_section: datetime.date
    last_section: datetime.date
    breaks: List[datetime.date]
    title: str
    rovidnev: str
    time_slot: str

    def __init__(self, header: dict) -> None:
        for k, v in header.items():
            setattr(self, normalize_key(k), v)


class Section:
    def __init__(self, section: dict, header: Header, data: dict):
        if section is not None:
            for k, v in section.items():
                setattr(self, normalize_key(k), v)

        self.date = data["date"]
        self.serial = data["serial"]
        self.week = data["week"]
        self.header = header

    def get(self, attr: str, default: Any) -> Any:
        if hasattr(self, attr):
            return getattr(self, attr)
        return getattr(self.header, attr, default)


def data_iter(header: Header) -> Generator:
    date = header.first_section
    serial = 1
    week = 1
    while not hasattr(header, "last_section") or date <= header.last_section:
        yield {"date": date, "serial": serial, "week": week}
        while True:
            date = datetime.timedelta(days=7) + date
            week += 1
            if date not in header.breaks:
                break
        serial += 1


def read_section(filename: str) -> Tuple[Header, List[Section]]:
    with open(filename) as f:
        lst = yaml.safe_load_all(f)
        header = Header(next(lst))
        sections = [
            Section(sec, header, data) for sec, data in zip(lst, data_iter(header))
        ]

    return header, sections

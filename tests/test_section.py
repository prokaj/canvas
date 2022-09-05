import datetime
import os
import tempfile
from contextlib import contextmanager

from canvas import section


@contextmanager
def tmp_working_dir():  # type: ignore
    try:
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            yield tmp
    finally:
        os.chdir(cwd)


def test_noaccent() -> None:
    test_data = {
        "Első óra": "Elso ora",
        "első óra": "elso ora",
        "utolsó óra": "utolso ora",
        "időpont": "idopont",
    }
    for a, b in test_data.items():
        assert section.noaccent(a) == b


def test_normalize_key() -> None:
    test_data = {
        "Első Óra": "first_section",
        "Útolsó   \tÓrÁ": "last_section",
        "Időpont": "time_slot",
        "Csoport": "title",
        "Rövidnév": "short_name",
        "Szünetek": "breaks",
        "Feladatok": "exs",
    }

    for a, b in test_data.items():
        assert section.normalize_key(a) == b


test_yaml = """
---
Első óra: 2022-09-15
Utolsó óra: 2022-12-16
Csoport: Valószínűségszámítás II gyakorlat
időpont: Csütörtök 12.00-13.30
Szünetek: [2022-09-22, 2022-10-29]
rovidnev:
    paper: valszám2
    canvas: Val. szám. II gyak.
letszam: 10

course_id: 28654
pdf_local: ../
pdf_canvas: problems
index_local: mat3.md

let:
    hf:
        prefix: ""
    extra:
        prefix: "A feladat megoldása 4 pontot ér."


description: |
    A szokásostól eltérően zárthelyi dolgozatok nem lesznek.
    **A gyakorlati jegy a házi feladat megoldások eredményén fog alapulni.**

    A házi és szorgalmi feladatok a kurzuson belül a [`Feladatok`](course:assignments) fül alatt érhető el.

---

# 1.gyak 09.15.
description: |
    Analízis limesz tételeinek és a Fubini tétel alkalmazása.
feladatok: |
    2524
    1129 1146[a]

hf: 1331 1413 2073

extra: 1146[b] 1316 1304 1121 1122

not used: |
    2521 2389  1126 1147  1381 2388
    1127 1145 1403
---
# 2.gyak 09.16.

feladatok: |
    1521 1127 398[a] 270 1182[abcdef]
    2375 1169

hf: 1473  1176[ae]
extra: 2488 1174[b]
későbbre:  522 523 1167 2521 2389 1910
not used: |
    1169 1910 ## 2126 2371 1153 1154 870
    136 270 398[a]
...
## any comment here is junk
"""


def test_read_sections() -> None:
    with tmp_working_dir():
        with open("test.yml", "w") as f:
            f.write(test_yaml)
        header, sections = section.read_section("test.yml")
        assert len(sections) == 2
        assert hasattr(header, "first_section")
        assert header.first_section == datetime.date(2022, 9, 15)
        assert sections[1].week == 3
        assert sections[1].date == datetime.date(2022, 9, 29)
        assert sections[1].get("short_name")["paper"] == "valszám2"
        assert sections[0].get("let")["hf"]["prefix"] == ""
        assert sections[0].get("hf") == "1331 1413 2073"

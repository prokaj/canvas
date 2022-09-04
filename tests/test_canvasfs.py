import json
import logging
import os
import tempfile

import pytest
from canvasapi.canvas_object import CanvasObject  # type: ignore
from canvasapi.course import Course  # type: ignore
from canvasapi.folder import Folder  # type: ignore

from canvas.canvasfs import canvasfs as cfs
from canvas.canvasfs import (
    get_canvas_assignments,
    get_canvas_files,
    get_canvas_quizzes,
    result_to_canvasfs,
    update_canvasfs,
)

logger = logging.getLogger("canvas")
logging.basicConfig()


def test_result_to_canvasfs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        logger.info("test_result_to_canvas_fs in %s", tmp)
        files = type(cfs).__dict__["files"]
        cfs.reset()
        assert files._initialized is False

        def dummy(key: str) -> int:
            logger.info("dummy(%s): files._initialized= %d", key, files._initialized)
            return ord(key[-1])

        dummy = result_to_canvasfs(
            which="files", key_fn=lambda key: key, id_fn=lambda value: value
        )(dummy)

        keys = ["a/b/c", "d/e"]
        for k in keys:
            dummy(k)
        assert files._initialized is True
        assert files == {k: dummy(k) for k in keys}


def test_load() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        logger.info("test_load in %s", tmp)

        cfs.reset()
        assert cfs.files == {}
        assert cfs.assignments == {}
        assert cfs.quizzes == {}

        cfs.reset()
        data = {"/a/b.pdf": 123, "/img.svg": 256}
        with open(os.path.abspath(".files.json"), "w") as f:
            json.dump(data, f)
        assert cfs.files == data
        assert cfs.assignments == {}
        assert cfs.quizzes == {}
        cfs.files["/a/b/c/d.pdf"] = 555
        cfs.save_state()
        file_names = {name: getattr(cfs, name)._filename for name in cfs._fields}
        for name, filename in file_names.items():
            with open(os.path.abspath(filename)) as f:
                assert os.path.dirname(f.name) == tmp
                assert json.load(f) == getattr(cfs, name)


@pytest.fixture
def mock_course(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_quizzes(self: Course) -> list:  # type: ignore
        return [CanvasObject(None, {"id": 12, "title": "Exam"})]

    monkeypatch.setattr(Course, "get_quizzes", get_quizzes)

    def get_assignment_group(self: Course, group_id: int) -> CanvasObject:  # type: ignore
        return CanvasObject(None, {"name": "Homework"})

    monkeypatch.setattr(Course, "get_assignment_group", get_assignment_group)

    def get_assignments(self: Course) -> list:  # type: ignore
        return [
            CanvasObject(None, {"id": 13, "assignment_group_id": 15, "name": "1. week"})
        ]

    monkeypatch.setattr(Course, "get_assignments", get_assignments)

    def get_folders(self: Course) -> list:  # type: ignore
        return [
            Folder(
                None,
                {
                    "id": 274838,
                    "name": "course files",
                    "full_name": "course files/problems",
                    "context_id": 14984,
                    "context_type": "Course",
                    "parent_folder_id": None,
                    "lock_at": None,
                    "unlock_at": None,
                    "position": None,
                    "locked": False,
                    "files_count": 1,
                    "folders_count": 0,
                },
            )
        ]

    monkeypatch.setattr(Course, "get_folders", get_folders)

    def get_files(self: Folder) -> list:  # type: ignore
        return [
            CanvasObject(
                None,
                {
                    "id": 1041047,
                    "uuid": "PVifirTcFOpm9TddopwMZmuS66lD3STaPcDewAMh",
                    "folder_id": 274838,
                    "display_name": "mathjax.png",
                    "filename": "1617471708_702__mathjax.png",
                    "upload_status": "success",
                    "content-type": "image/png",
                },
            )
        ]

    monkeypatch.setattr(Folder, "get_files", get_files)


def test_get_canvas_quizzes(mock_course) -> None:  # type: ignore
    course = Course(None, {})
    assert get_canvas_quizzes(course) == {"Exam": 12}
    cfs.update(quizzes=get_canvas_quizzes(course))
    assert cfs.quizzes == {"Exam": 12}

    assert get_canvas_assignments(course) == {"Homework/1. week": 13}
    cfs.update(assignments=get_canvas_assignments(course))
    assert cfs.quizzes == {"Exam": 12}
    assert cfs.assignments == {"Homework/1. week": 13}

    assert get_canvas_files(course) == {"/problems/mathjax.png": 1041047}
    cfs.update(files=get_canvas_files(course))
    assert cfs.quizzes == {"Exam": 12}
    assert cfs.assignments == {"Homework/1. week": 13}
    assert cfs.files == {"/problems/mathjax.png": 1041047}

    cfs.reset()
    update_canvasfs(course)
    assert cfs.quizzes == {"Exam": 12}
    assert cfs.assignments == {"Homework/1. week": 13}
    assert cfs.files == {"/problems/mathjax.png": 1041047}

    fields = []
    cfs._apply(lambda obj, name: fields.append((name, obj)))
    cfs.reset()
    for _name, obj in fields:
        logger.info("test_clear on field `%s`", _name)
        assert obj == {}
        assert obj._initialized is False


def test_cfs_del() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        logger.info("test_cfs_del in %s", tmp)

        fields = []
        cfs._apply(lambda obj, name: fields.append((name, obj)))
        cfs.__del__()
        for _name, obj in fields:
            logger.info("test_cfs_del on field `%s`", _name)
            assert os.path.exists(obj._filename)
            with open(obj._filename) as f:
                assert json.load(f) == obj

from __future__ import annotations

import logging
import os
from functools import lru_cache, partial
from tempfile import TemporaryDirectory
from typing import Any, Callable

from canvasapi.course import Course as Course  # type: ignore

from canvas.saveddict import SavedDict as SavedDict

logger = logging.getLogger("canvas")


def add_to_course(f: Callable) -> None:
    setattr(Course, f.__name__, f)


@add_to_course
def get_fsdata(course: Course) -> SavedDict:  # type: ignore
    course.__dict__.setdefault("_fsdata", SavedDict(".fsdata.json").load())
    return course._fsdata  # type: ignore


@add_to_course
def save(course: Course) -> None:  # type: ignore
    course._fsdata.save()


@add_to_course
def upload_file(course: Course, local_file: str, canvas_file: str) -> Any:  # type: ignore
    local_file = os.path.abspath(local_file)
    canvas_dir, canvas_name = os.path.split(canvas_file)

    with TemporaryDirectory() as tmp:
        tmp_path = f"{tmp}/{canvas_name}"
        os.symlink(local_file, tmp_path)
        success, file = course.upload(
            tmp_path, parent_folder_path=canvas_dir, on_duplicate="overwrite"
        )
    if success:
        fsdata = course.get_fsdata()
        files = fsdata.setdefault("files", {})
        files[canvas_file] = file["id"]
    return file


def get_canvas_files(course: Course) -> dict:  # type: ignore
    data = {}
    for folder in course.get_folders():
        if folder.files_count > 0:
            folder_name = folder.full_name.replace("course files", "")
            for file in folder.get_files():
                data[f"{folder_name}/{file.display_name}"] = file.id

    return data


def get_canvas_assignment_group_name(  # type: ignore
    course: Course, group_id: int
) -> str:
    name: str = course.get_assignment_group(group_id).name
    return name


def get_canvas_assignments(course: Course) -> dict:  # type: ignore
    data = {}
    get_group_name = lru_cache()(partial(get_canvas_assignment_group_name, course))

    for assgn in course.get_assignments():
        idx = f"{get_group_name(group_id=assgn.assignment_group_id)}/{assgn.name}"
        data[idx] = assgn.id

    return data


def get_canvas_quizzes(course: Course) -> dict:  # type: ignore
    data = {}
    for quize in course.get_quizzes():
        data[quize.title] = quize.id

    return data


@add_to_course
def fsdata_from_canvas(course: Course, which=("files", "assignments", "quizzes")) -> None:  # type: ignore
    if len(which) > 0:
        fsdata = course.get_fsdata()
        if "files" in which:
            fsdata.update({"files": get_canvas_files(course)})
        if "assignments" in which:
            fsdata.update({"assignments": get_canvas_assignments(course)})
        if "quizzes" in which:
            fsdata.update({"assignments": get_canvas_quizzes(course)})
        fsdata.save()

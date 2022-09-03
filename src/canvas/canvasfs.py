from __future__ import annotations

import atexit
import json
import logging
import os
from functools import lru_cache, partial, wraps
from typing import Any, Callable

from canvasapi.course import Course  # type: ignore

logger = logging.getLogger("canvas")
logging.basicConfig()
logger.setLevel(logging.DEBUG)


class LazyDict(dict):
    def __init__(self, filename: str) -> None:
        self._filename = filename
        self._initialized = False

    def load(self) -> None:
        if os.path.exists(self._filename):
            with open(self._filename) as f:
                data = json.load(f)
        else:
            data = {}
        super().__init__(data)
        self._initialized = True

    def __get__(self, instance: Any, owner: Any = None) -> LazyDict:
        if not self._initialized:
            self.load()
        return self

    def __set__(self, instance: Any, value: dict) -> None:
        self.clear()
        self.update(value)

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = f"_{name}"
        fields = getattr(owner, "_fields", [])
        fields.append(name)
        owner._fields = fields  # type: ignore

    def save(self) -> None:
        logger.info("saving data=%s", repr(self))
        with open(self._filename, "w") as f:
            json.dump(self, f)

    def __delete__(self, instance: Any) -> None:
        self.save()
        logger.info("%s is being deleted on %s", self._name, str(instance))


class CanvasFS:

    files = LazyDict("./.files.json")
    assignments = LazyDict("./.assignments.json")
    quizzes = LazyDict("./.quizzes.json")

    def __init__(self) -> None:
        atexit.register(self.save_state)

    def save_state(self) -> None:
        self.files.save()
        self.assignments.save()
        self.quizzes.save()

    def clear(self) -> None:
        self.files.clear()
        self.assignments.clear()
        self.quizzes.clear()

    def reset(self, **kwargs: dict) -> None:
        for name in ["files", "assignments", "quizzes"]:
            if name in kwargs and isinstance(kwargs[name], dict):
                setattr(self, name, kwargs[name])

    def __del__(self) -> None:
        self.save_state()
        logger.info("CanvasFS is being deleted")


def result_to_canvasfs(which: str, input_var: str) -> Callable:
    @wraps
    def wrapper(f: Callable) -> Callable:
        def g(*args: list, **kwargs: dict) -> dict:
            idx = kwargs.get(input_var, None)
            value: dict = f(*args, **kwargs)
            ld = getattr(CanvasFS, which)
            ld[idx] = value["id"]
            return value

        return g

    return wrapper


def get_canvas_files(course: Course) -> dict:  # type: ignore
    data = {}
    for folder in course.get_folders():
        if folder.files_count > 0:
            folder_name = folder.full_name.replace("course files/", "")
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


canvasfs = CanvasFS()


def update_canvasfs(course: Course) -> None:  # type: ignore
    canvasfs.files = get_canvas_files(course)
    canvasfs.assignments = get_canvas_assignments(course)
    canvasfs.quizzes = get_canvas_quizzes(course)

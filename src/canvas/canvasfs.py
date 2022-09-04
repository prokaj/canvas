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
        logger.info("loading %s from %s", self._name, self._filename)
        if os.path.exists(self._filename):
            with open(self._filename) as f:
                data = json.load(f)
        else:
            data = {}
        super().__init__(data)
        self._initialized = True

    def __get__(self, instance: Any, owner: Any = None) -> LazyDict:
        logger.info("getting: %s, initialized: %d", self._name, self._initialized)
        if not self._initialized:
            self.load()
        return self

    def __set__(self, instance: Any, value: dict) -> None:
        logger.info("setting %s, initialized: %d", self._name, self._initialized)
        self.clear()
        self.update(value)
        self._initialized = True

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = f"_{name}"
        owner._fields.append(name)  # type: ignore

    def save(self) -> None:
        logger.info("saving data=%s", repr(self))
        with open(self._filename, "w") as f:
            json.dump(self, f)

    def reset(self) -> None:
        logger.info("resetting%s, initialized: %d", self._name, self._initialized)
        self.clear()
        self._initialized = False


class CanvasFS:

    files = LazyDict("./.files.json")
    assignments = LazyDict("./.assignments.json")
    quizzes = LazyDict("./.quizzes.json")
    _fields: list[str] = []

    def __init__(self) -> None:
        atexit.register(self.save_state)

    def _apply(self, fun: Callable) -> None:
        for name in self._fields:
            fun(type(self).__dict__[name], name)

    def save_state(self) -> None:
        self._apply(lambda obj, name: obj.save())

    def update(self, **kwargs: dict) -> None:
        def update(obj: LazyDict, name: str) -> None:
            if name in kwargs and isinstance(kwargs[name], dict):
                obj.__set__(self, kwargs[name])

        self._apply(update)

    def reset(self) -> None:
        self._apply(lambda obj, name: obj.reset())

    def __del__(self) -> None:
        self.save_state()
        logger.info("CanvasFS is being deleted")


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


canvasfs = CanvasFS()


def result_to_canvasfs(
    which: str, key_fn: Callable, id_fn: Callable = lambda value: value["id"]
) -> Callable:
    def wrapper(f: Callable) -> Callable:
        @wraps(f)
        def g(*args: list, **kwargs: dict) -> Any:
            idx = key_fn(*args, **kwargs)
            value = f(*args, **kwargs)
            ld = getattr(canvasfs, which)
            ld[idx] = id_fn(value)
            logger.info(
                "result_to_canvas_wrapper: canvasfs.%s._initialized = %d",
                which,
                ld._initialized,
            )
            return value

        return g

    return wrapper


def update_canvasfs(course: Course) -> None:  # type: ignore
    canvasfs.files = get_canvas_files(course)
    canvasfs.assignments = get_canvas_assignments(course)
    canvasfs.quizzes = get_canvas_quizzes(course)

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from functools import lru_cache, partial, wraps
from typing import Any, Callable, Generator

from canvasapi.course import Course  # type: ignore

logger = logging.getLogger("canvas")


class LazyDict:
    def __init__(self, filename: str) -> None:
        self._filename = filename

    def _load(self) -> dict:
        logger.info("loading %s from %s", self._name, self._filename)
        if os.path.exists(self._filename):
            with open(self._filename) as f:
                data = json.load(f)
                assert isinstance(data, dict)
        else:
            data = {}
        return data  # type: ignore

    def __get__(self, instance: Any, owner: Any = None) -> dict:
        logger.info("getting: %s", self._name)
        instance_dict = instance.__dict__
        if self._name not in instance_dict:
            instance_dict[self._name] = self._load()
        return instance_dict[self._name]  # type: ignore

    def __set__(self, instance: Any, value: dict) -> None:
        logger.info("setting %s", self._name)
        instance.__dict__[self._name] = value

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = f"_{name}"
        owner._fields.append(name)  # type: ignore

    def _save(self, instance: Any) -> None:
        if self._name in instance.__dict__:
            data = instance.__dict__.get(self._name)
            logger.info("saving LazyDict(%s)", self._name)
            with open(self._filename, "w") as f:
                json.dump(data, f)

    def _reset(self, instance: Any) -> None:
        if self._name in instance.__dict__:
            logger.info("resetting %s", self._name)
            instance.__dict__.pop(self._name)


class CanvasFS:
    files = LazyDict("./.files.json")
    assignments = LazyDict("./.assignments.json")
    quizzes = LazyDict("./.quizzes.json")
    _fields: list[str] = []

    def _apply(self, fun: Callable) -> None:
        for name in self._fields:
            fun(type(self).__dict__[name], name)

    def save_state(self) -> None:
        self._apply(lambda obj, name: obj._save(self))

    def update(self, **kwargs: dict) -> None:
        def update(obj: LazyDict, name: str) -> None:
            if name in kwargs and isinstance(kwargs[name], dict):
                obj.__set__(self, kwargs[name])

        self._apply(update)

    def reset(self) -> None:
        self._apply(lambda obj, name: obj._reset(self))

    def resolve(self, ptype: str, path: str) -> int:
        idx: int = getattr(self, ptype)[path]
        return idx


# used by the context manager below!
cfs: list[CanvasFS] = []


@contextmanager
def canvasfs(path: str = ".") -> Generator:
    cwd = os.getcwd()
    os.chdir(path)
    canvasfs = CanvasFS()
    cfs.append(canvasfs)
    try:
        yield canvasfs

    finally:
        cfs.pop()
        canvasfs.save_state()
        os.chdir(cwd)


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


def result_to_canvasfs(
    which: str, key_fn: Callable, id_fn: Callable = lambda value: value["id"]
) -> Callable:
    def wrapper(f: Callable) -> Callable:
        @wraps(f)
        def g(*args: list, **kwargs: dict) -> Any:
            idx = key_fn(*args, **kwargs)
            value = f(*args, **kwargs)
            ld = getattr(cfs[-1], which)
            ld[idx] = id_fn(value)
            logger.info("result_to_canvas_wrapper: canvasfs.%s", which)
            return value

        return g

    return wrapper


def update_canvasfs(course: Course) -> None:  # type: ignore
    if len(cfs) == 0:
        raise IndexError(
            "update_canvasfs must be used within `with canvasfs(): ` context"
        )
    cfs[-1].files = get_canvas_files(course)
    cfs[-1].assignments = get_canvas_assignments(course)
    cfs[-1].quizzes = get_canvas_quizzes(course)

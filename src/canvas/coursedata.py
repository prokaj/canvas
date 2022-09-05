import json
import logging
import os
from typing import Any, Callable, Dict, Generator, Optional

from canvasapi.course import Course  # type: ignore

logger = logging.getLogger("canvas")


class SavedDict(dict):
    def __init__(self, filename: str, default: Optional[dict] = None):
        self._filename = filename
        self._needinit = True
        self._default = default if default is not None else {}

    def __getitem__(self, key: Any) -> Any:
        if self._needinit:
            self.load()
        return super().__getitem__(key)

    def load(self, data: Optional[dict] = None) -> None:
        if data is None:
            if os.path.exists(self._filename):
                with open(self._filename) as f:
                    data = json.load(f)
            else:
                data = self._default
        super().__init__(data)
        self._needinit = False

    def __repr__(self) -> str:
        if self._needinit:
            return f"{type(self).__name__}('{self._filename}')"
        else:
            return super().__repr__()

    def save(self) -> None:
        if not self._needinit:
            with open(self._filename, "w") as f:
                json.dump(self, f)

    def reset(self) -> None:
        self._needinit = True
        self.clear()


class SavedCourseData:
    _updaters: Dict[str, Callable] = {}

    def __init__(self, **kwargs: Dict[str, str]) -> None:
        self._fields = sorted(kwargs.keys())
        for name, filename in kwargs.items():
            setattr(self, name, SavedDict(filename))  # type: ignore

    def _dicts(self) -> Generator:
        for name in self._fields:
            yield name, getattr(self, name)

    def save(self) -> None:
        for _name, ldict in self._dicts():
            ldict.save()

    def reset(self) -> None:
        for _name, ldict in self._dicts():
            ldict.reset()

    def update(self, **kwargs) -> None:  # type: ignore
        for name, data in kwargs.items():
            if name in self._fields and isinstance(data, dict):
                getattr(self, name).load(data)

    def __repr__(self) -> str:
        params = ", ".join(
            f'{name}="{getattr(self, name)._filename}"' for name in self._fields
        )
        return f"{type(self).__name__}({params})"

    @classmethod
    def register_updater(cls, name: str, updater: Callable) -> None:
        cls._updaters[name] = updater

    def update_from_canvas(self, course: Course) -> None:  # type: ignore
        for name, ldict in self._dicts():
            if name not in self._updaters:
                logger.warning("No updater for %s.", name)
            else:
                try:
                    data = self._updaters[name](course)
                    if data is None:
                        logger.warning(
                            "updater of %s returned None. No update is done!", name
                        )
                    else:
                        ldict.load(data)
                except Exception as e:
                    logger.warning(
                        "updater of %s failed with:\n%s\nNo update is done!",
                        name,
                        repr(e),
                    )

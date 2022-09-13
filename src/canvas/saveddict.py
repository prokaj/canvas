from __future__ import annotations

import json
import os
from typing import Any


class SavedDict(dict):
    def __init__(self, filename: str, default: dict | None = None):
        self._filename = os.path.abspath(filename)
        self._needinit = True
        self._default = default if default is not None else {}

    def __getitem__(self, key: Any) -> Any:
        if self._needinit:
            self.load()
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        if self._needinit:
            self.load()
        return super().__setitem__(key, value)

    def load(self, data: dict | None = None) -> SavedDict:
        if data is None:
            if os.path.exists(self._filename):
                with open(self._filename) as f:
                    data = json.load(f)
            else:
                data = self._default
        super().__init__(data)
        self._needinit = False
        return self

    def __repr__(self) -> str:
        if self._needinit:
            return f'{type(self).__name__}("{self._filename}")'
        else:
            return super().__repr__()

    def save(self) -> None:
        if not self._needinit:
            with open(self._filename, "w") as f:
                json.dump(self, f)

    def reset(self) -> None:
        self._needinit = True
        self.clear()

    def update(self, other: dict) -> None:  # type: ignore
        if self._needinit:
            self.load()
        rec_update(self, other)


def rec_update(self: dict, other: dict) -> None:
    for key, value in other.items():
        if (key in self) and isinstance(self[key], dict) and isinstance(value, dict):
            rec_update(self[key], value)
        else:
            self[key] = value

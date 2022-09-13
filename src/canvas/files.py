import os
import tempfile
from typing import Dict, Tuple

import canvasapi  # type: ignore


def get_canvas_folder(  # type: ignore
    course: canvasapi.course.Course, path: str
) -> canvasapi.folder.Folder:
    try:
        folder = list(course.resolve_path(path))[-1]
    except canvasapi.exceptions.ResourceDoesNotExist:
        parent_path, name = os.path.split(path)
        folder = course.create_folder(name, parent_folder_path=parent_path)
    return folder


def normalize_path(path: str, default_dir: str, local: bool = True) -> Tuple[str, str]:
    dirname, basename = os.path.split(path)
    if dirname == "":
        dirname = default_dir
    if local:
        dirname = os.path.abspath(dirname)
    return dirname, basename


def upload_file(  # type: ignore
    course: canvasapi.course.Course, local_file: str, canvas_file: str
) -> Dict:

    local_dir, local_name = normalize_path(
        local_file, course.config.get("local_default_dir", "")
    )
    canvas_dir, canvas_name = normalize_path(
        canvas_file, course.config.get("canvas_default_dir", ""), local=False
    )
    canvas_folder = get_canvas_folder(course, canvas_dir)

    result: dict
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = f"{tmp}/{canvas_name}"
        local_path = f"{local_dir}/{local_name}"
        os.symlink(local_path, tmp_path)
        succes, result = canvas_folder.upload(tmp_path, on_duplicate="overwrite")

    return result

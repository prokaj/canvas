import functools
import logging
import os
import subprocess
from typing import Any, Iterator, List, Tuple

logger = logging.getLogger("canvas")


def all_app_in_path(app_name: str) -> Iterator[str]:
    for d in os.environ["PATH"].split(":") + [f"{os.getenv('HOME')}/local/bin"]:
        p = f"{d}{os.path.sep}{app_name}"
        if os.path.exists(p):
            yield p


def get_app_version(app: str) -> Tuple[int, ...]:
    res = subprocess.run(app + " --version", shell=True, stdout=subprocess.PIPE)
    return tuple(
        map(int, res.stdout.decode("utf-8").split("\n")[0].split()[1].split("."))
    )


@functools.lru_cache()
def pandoc_cmd() -> str:
    pandoc = sorted(
        ((get_app_version(p), p) for p in all_app_in_path("pandoc")), reverse=True
    )
    if not pandoc:
        raise FileNotFoundError("pandoc not found")

    version, path = pandoc[0]
    if version[0] < 2:
        raise FileNotFoundError(
            f'only too old pandoc version ({".".join(map(str,version))}) found: {path}'
        )
    return path


def run_cmd_on_text(cmd: str, text: str, out_encoding: str = "utf-8") -> str:
    proc = subprocess.run(
        cmd,
        shell=True,
        input=text.encode("utf8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        logger.error(cmd)
        logger.error(proc.stderr.decode(out_encoding))
        return ""
    if proc.stderr:
        logger.warning(cmd)
        logger.warning(proc.stderr.decode(out_encoding))
    return proc.stdout.decode(out_encoding)


def pandoc_cmd_with_options(**kwargs: Any) -> str:
    options = {
        "src_format": "markdown",
        "out_format": "html",
        "filters": ["href.lua"],
        "options": ["--mathml"],
    }

    options["options"].extend(kwargs.pop("options", []))  # type: ignore
    options.update(kwargs)

    filters = " ".join(f"-L {filter_name}" for filter_name in options["filters"])

    cmd_line_options = (
        f"-f {options['src_format']} -t {options['out_format']} "
        f"{' '.join(options['options'])} {filters}"
    )

    return f"lua -l expand-macros| {pandoc_cmd()} {cmd_line_options}"


def pandoc_with_options(text: str, **kwargs: Any) -> str:
    cmd = pandoc_cmd_with_options(**kwargs)
    return run_cmd_on_text(cmd, text)


def pandoc_text(txt: str, src_format: str = "", out_format: str = "html") -> str:
    cmd = pandoc_cmd_with_options(
        src_format=src_format,
        out_format=out_format,
    )
    return run_cmd_on_text(cmd, txt)


def pandoc_list(
    lst: List[str],
    src_format: str = "",
    out_format: str = "html",
) -> List[str]:
    sep = "0123456789abcdefghijklmnopqrstuvwxyz"
    txt = f"\n\n{sep}\n\n".join(lst)
    html = pandoc_text(txt, src_format, out_format).split(f"\n<p>{sep}</p>\n")
    return html

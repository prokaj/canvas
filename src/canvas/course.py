import itertools
import random
from typing import Any, Callable, Dict, Generator, List, Union

import canvasapi  # type: ignore
import ipywidgets as widgets  # type: ignore
from IPython import display  # type: ignore


def mk_fel(feladatok: List[List[str]], prefix: str = "") -> List[str]:
    prefix_str = f'--prefix="{prefix}" '
    return list(map(lambda x: prefix_str + " ".join(x), itertools.product(*feladatok)))


def add_title(feladatok: Union[List[str], str]) -> Dict:
    if isinstance(feladatok, list):
        return {chr(65 + i): x for i, x in enumerate(feladatok)}
    return {"A": feladatok}


def split(x: List, n: int) -> Generator[List, None, None]:
    s: float = 0
    delta: float = len(x) / n
    for _ in range(1, n + 1):
        i, j = round(s), round(s + delta)
        yield (x[i:j])
        s += delta


def get_students(course: canvasapi.course, filter: Callable) -> List:  # type: ignore
    return [
        x.user_id for x in course.get_enrollments(type="StudentEnrollment") if filter(x)
    ]


def add_visibility(feladatok: List, students: List) -> Union[List, Dict]:
    if len(feladatok) == 1:
        return dict(fel=feladatok[0], visibility=None)

    random.shuffle(students)
    return [
        {"fel": ex, "visibility": st}
        for ex, st in zip(feladatok, split(students, len(feladatok)))
    ]


def confirm_delete(exs: List, callback: Callable) -> None:
    prompt = "Do you really want to delete `{fname}`?"
    style = {"description_width": "initial"}
    w0 = widgets.ToggleButtons(
        options=["No", "Yes"],
        description="",
        disabled=False,
        button_style="primary",
        style=style,
    )
    out = widgets.Output()

    def iter_fn() -> Generator[None, str, None]:
        for ex in exs:
            w0.description = prompt.format(fname=ex.name)
            ans = yield
            if ans.lower() == "yes":
                with out:
                    callback(ex)
        w0.close()

    ex_iter = iter_fn()

    def widget_cb(w: widgets.widgets, c: widgets.callback, b: Any) -> None:  # type: ignore
        if c.get("event", "") == "click":
            try:
                ex_iter.send(w.get_interact_value())
            except StopIteration:
                pass

    w0.on_msg(widget_cb)
    try:
        next(ex_iter)
    except StopIteration:
        return
    display(widgets.VBox([out, w0]))


def del_assignments(course: canvasapi.Course, title: str) -> None:  # type: ignore
    def cb(x: canvasapi.Assignment) -> None:  # type: ignore
        if x.has_submitted_submissions:
            print(f"not deleting {x.name}, {x.id}. there are submissions!")
        else:
            print(f"deleting {x.name}, {x.id} ")
            x.delete()

    confirm_delete(course.get_assignments(search_term=title), cb)


def publish_assignments(course: canvasapi.Course, title: str) -> None:  # type: ignore
    for x in course.get_assignments(search_term=title):
        print(f"publishing {x.name}, {x.id} ")
        x.edit(assignment=dict(published=True))


all = [mk_fel, add_title, add_visibility, del_assignments, publish_assignments]

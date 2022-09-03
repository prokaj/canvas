import functools
import json
import os
import subprocess
import tempfile
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Union,
)

import canvasapi  # type: ignore
from tqdm.auto import tqdm  # type: ignore
from yaml import safe_load as yaml_safe_load  # type: ignore


def load_dotenv() -> None:
    with open(".env.yml") as f:
        dot_env = yaml_safe_load(f)
    os.environ.update(dot_env)


def all_app_in_path(app_name: str) -> Iterator[str]:
    for d in os.environ["PATH"].split(":") + ["/home/prokaj/local/bin"]:
        p = f"{d}{os.path.sep}{app_name}"
        if os.path.exists(p):
            yield p


def get_app_version(app: str) -> Tuple[int, ...]:
    res = subprocess.run(app + " --version", shell=True, stdout=subprocess.PIPE)
    return tuple(
        map(int, res.stdout.decode("utf-8").split("\n")[0].split()[1].split("."))
    )


@functools.lru_cache
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


def read_setting(root: str = ".") -> Any:
    with open(root + "/canvas.json") as f:
        setting = json.load(f)
    return setting


def get_canvas_old(setting: Union[None, dict] = None) -> canvasapi.Canvas:  # type: ignore
    if setting is None:
        setting = read_setting()
    setting = {
        k: v
        for k, v in setting.items()
        if k in canvasapi.Canvas.__init__.__code__.co_varnames
    }
    return canvasapi.Canvas(**setting)


def get_canvas() -> canvasapi.Canvas:  # type: ignore
    return canvasapi.Canvas(
        access_token=os.environ.get("canvas_access_token", ""),
        base_url=os.environ.get("canvas_base_url", ""),
    )


def get_course(  # type: ignore
    config: Dict, course_name: Optional[str] = None
) -> canvasapi.course.Course:
    course_data = config if course_name is None else config[course_name]
    course = get_canvas().get_course(course_data["course_id"])
    course.config = course_data
    return course


def upload_pdf(  # type: ignore
    course: canvasapi.course.Course,
    filename: str,
    canvasname: Optional[str] = None,
    localdir: Optional[str] = None,
    folder_name: Optional[str] = None,
) -> Optional[canvasapi.file.File]:
    if localdir is None:
        if folder_name is None:
            folder_name = course.local_data["pdf_canvas"]
        localdir = course.local_data["pdf_local"]

    filename_ = localdir + "/" + filename
    if not os.path.exists(filename_):
        print(f"{filename} does not exists in {localdir}")
        return None

    # finding canvas folder
    folders = course.get_folders()
    if folder_name is None:
        folder = folders[0]
    else:
        folders = [f for f in folders if f.name == folder_name]
        folder = (
            folders[0]
            if folders
            else course.get_folders()[0].create_folder(folder_name)
        )

    if (canvasname is not None) and filename != canvasname:
        with tempfile.TemporaryDirectory() as d:
            tmpname = d + "/" + canvasname
            os.symlink(filename_, tmpname)
            file = folder.upload(tmpname, on_duplicate="overwrite")
        return file
    return folder.upload(filename_, on_duplicate="overwrite")


def file_upload(  # type: ignore
    course: canvasapi.course.Course,
    file: str,
    folder_name: Optional[str] = None,
) -> canvasapi.file.File:
    folders = course.get_folders()
    if folder_name is None:
        folder = folders[0]
    else:
        folders = [f for f in folders if f.name == folder_name]
        folder = (
            folders[0]
            if folders
            else course.get_folders()[0].create_folder(folder_name)
        )
    return folder.upload(file, on_duplicate="overwrite")


def get_file(course: canvasapi.course.Course, path: str) -> canvasapi.file.File:  # type: ignore
    path_elements = path.split("/")
    file_name = path_elements.pop()
    path_elements = path_elements[::-1]
    folders = course.get_folders()
    while path_elements:
        folders = folders[0].get_folders()
        folder_name = path_elements.pop()
        folders = [f for f in folders if f.name == folder_name]
    return [f for f in folders[0].get_files() if f.display_name == file_name][0]


def get_file_id(course: canvasapi.course.Course, path: str) -> int:  # type: ignore
    return int(get_file(course, path).id)


def get_path(x: canvasapi.file.File) -> str:  # type: ignore
    return str(x.full_name).replace("course files", "")


def file_key(course: canvasapi.course.Course, f: canvasapi.file.File) -> str:  # type: ignore
    key = f"{course.get_folder(f.folder_id).full_name}/{f.display_name}"
    return key.replace("course files/", "")


def file_url_dict(course: canvasapi.course.Course) -> Dict:  # type: ignore
    files = {
        file_key(f, course): {
            "course_id": course.id,
            "id": f.id,
            "url": download_url(course.id, f.id),
            "preview_url": preview_url(course.id, f.id),
        }
        for f in course.get_files()
    }
    for q in course.get_quizzes():
        key = f"quiz/{q.title}"
        if key in files:
            print(
                f"{key} is already present.\n"
                f'Overwriting {files[key]["url"]} with {q.html_url}.'
            )
        files[key] = {"url": q.html_url}
    return files


def preview_url(course_id: str, file_id: str) -> str:
    return f"https://canvas.elte.hu/courses/{course_id}/files?preview={file_id}"


def download_url(course_id: str, file_id: str) -> str:
    return f"https://canvas.elte.hu/courses/{course_id}/files/{file_id}/download"


def write_lua_table(d: Dict, dict_file: str = "file.dict") -> None:
    with open(dict_file, "w") as f:
        f.write("return")
        lua_table(d, f)


def lua_table(d: Dict, file: TextIO) -> None:
    file.write("{\n")
    for k, v in d.items():
        file.write(f'["{k}"]=')
        if isinstance(v, dict):
            lua_table(v, file)
        else:
            file.write(f'"{v}"')
        file.write(",")
    file.write("}\n")


def make_assignment(
    fel: str,
    due_at: datetime,
    points: int = 10,
    name: str = "1. házi feladat",
    group_name: str = "Csoport",
    visibility: Any = None,
    root: str = "../",
    math: str = "mathml",
    filters: Sequence[str] = ("href_filter"),
) -> Dict:
    lua_filter = " ".join(f"--lua-filter {root}{x}.lua" for x in filters)
    cmd = f"lua {root}extract.lua {fel} | {pandoc_cmd()} -f latex+raw_tex --{math} -t html {lua_filter}"
    # --lua-filter {root}href_filter.lua"

    out = subprocess.run(cmd, shell=True, capture_output=True)
    if out.returncode != 0:
        print("cmd:", cmd)
        print("stdout:", out.stdout.decode("utf-8"))
        print("stderr:", out.stderr.decode("utf-8"))
        print("-" * 20)
        return {}
    html = out.stdout.decode("utf-8")

    htmls = html.split("----0123456789----\n")
    resources = [x.split("\n")[-2:] for x in htmls[:-1]]
    html = htmls[-1]
    return {
        "due_at": due_at.isoformat(),
        "points_possible": points,
        "allowed_extensions": "pdf,png,jpg".split(","),
        "submission_types": ["online_text_entry", "online_upload"],
        "description": html,
        "name": name,
        "assignment_overrides": [
            {
                "due_at": due_at.isoformat(),
                "student_ids": visibility,
                "title": group_name,
            }
        ]
        if visibility is not None
        else None,
        "only_visible_to_overrides": visibility is not None,
        "resources": resources,
    }


restypes = {"image": ("images", "<img src=")}


def upload_resources(assgn: Dict, course: canvasapi.course.Course) -> Dict:  # type: ignore
    resources = assgn.get("resources", {})
    if len(resources):
        html = assgn["description"]
        for fn, rtype in resources:
            canvas_dir, pattern = restypes[rtype]
            ok, v = file_upload(fn, canvas_dir, course)
            if ok:
                html = html.replace(f'{pattern}"{fn}"', f"{pattern}\"{v['url']}\"")
        assgn["description"] = html
    return assgn


def update_front_page(course: canvasapi.course.Course, root: str = "../") -> canvasapi.course.Course:  # type: ignore
    index_md = course.config["index_local"]
    cmd = (
        f"cat  {index_md} |lua {root}preprocess_macros.lua"
        f"|{pandoc_cmd()} --mathml -t html --lua-filter {root}href_filter.lua"
    )
    out = subprocess.run(cmd, shell=True, capture_output=True)
    if out.returncode != 0:
        print(out.stderr)
        return
    html = out.stdout.decode("utf-8")
    return course.edit_front_page(wiki_page={"title": "Kurzusleírás", "body": html})


def pandoc_text(
    txt: str,
    src_format: str = "",
    out_format: str = "html",
    root: str = "../",
) -> str:
    cmd = (
        f"lua {root}preprocess_macros.lua"
        f"| {pandoc_cmd()} -f {src_format} --mathml -t {out_format} --lua-filter={root}href_filter.lua"
    )
    out = subprocess.run(
        cmd,
        shell=True,
        input=txt.encode("utf8"),
        capture_output=True,
    )
    if out.returncode != 0:
        print(out.stderr)
        return ""
    html = out.stdout.decode("utf-8")
    return html


def pandoc_list(
    lst: List[str],
    src_format: str = "",
    out_format: str = "html",
    root: str = "../",
) -> List[str]:
    sep = "0123456789abcdefghijklmnopqrstuvwxyz"
    txt = f"\n\n{sep}\n\n".join(lst)
    html = pandoc_text(txt).split(f"\n<p>{sep}</p>\n")
    return html


qargs = "question_name question_text question_type points_possible".split(" ")
qgargs = "name pick_count question_points".split(" ")
# """calculated_question, essay_question, file_upload_question,
# fill_in_multiple_blanks_question, matching_question
pandoc_ans = ["multiple_answers_question", "multiple_choice_question"]
# multiple_dropdowns_question, numerical_question,
# short_answer_question, text_only_question, true_false_question"""


def pandoc_quiz_data(data: List) -> List:
    text_data = list(text_iter(data))
    html_data = pandoc_list([x["text"] for x in text_data], src_format="latex")
    for x, html in zip(text_data, html_data):
        x["obj"][x["key"]] = html
    return data


def text_iter(data: List) -> Generator[Dict, None, None]:
    for x in data:
        if x.get("type", "") == "quiz":
            yield {"obj": x, "key": "description", "text": x["description"]}
            yield from text_iter(x["questions"])
        elif x.get("type", "") == "quizgroup":
            for q in x["questions"]:
                yield from question_iter(q)
        elif x.get("question_type", None) is not None:
            yield from question_iter(x)


def question_iter(x: Dict) -> Generator[Dict, None, None]:
    yield {"obj": x, "key": "question_text", "text": x["question_text"]}
    if x["question_type"] in pandoc_ans:
        for a in x["answers"]:
            yield from answer_iter(a)


def answer_iter(x: Dict) -> Generator[Dict, None, None]:
    yield {"obj": x, "key": "answer_html", "text": x.pop("answer_text", "")}


def copy_dict(d: Dict, pred: Callable) -> Dict:
    return {k: v for k, v in d.items() if pred(k)}


def all_questions(lst: List) -> Generator[Dict, None, None]:
    for x in lst:
        if "questions" in x:
            yield from all_questions(x["questions"])
        else:
            yield x


def create_quiz(course: canvasapi.course.Course, data: List, progress: Optional[bool] = True) -> Any:  # type: ignore
    def id_fun(x: Any, **kwargs: Any) -> Any:
        return x

    tqdm_ = tqdm if progress else id_fun
    data = pandoc_quiz_data(data)
    # data is a list of quiz dictionaries
    with open("/dev/null", "w") as dev_null:
        for x in data:
            if x.get("type", "") != "quiz":
                continue
            quiz = course.create_quiz(quiz=copy_dict(x, lambda k: k != "questions"))
            q_groups = [x for x in x["questions"] if x.get("type", "") == "quizgroup"]
            for q_group in tqdm_(q_groups, desc="creating groups", file=dev_null):
                q_id = quiz.create_question_group(
                    quiz_groups=[copy_dict(q_group, lambda k: k != "questions")]
                ).id
                for q in q_group["questions"]:
                    q["quiz_group_id"] = q_id
            for q in tqdm_(
                list(all_questions(x["questions"])),
                desc="creating questions",
                file=dev_null,
            ):
                quiz.create_question(question=q)
            points_total = sum(
                q.get("question_points", q.get("points_possible", 0))
                for q in x["questions"]
            )
            sum(q.get("pick_count", 1) for q in x["questions"])
            quiz.edit(
                quiz={
                    "question_count": len(x["questions"]),
                    "points_possible": points_total,
                }
            )
    return quiz


def mk_ans(x: Dict, i: int, use_pandoc: bool = True) -> Dict:
    a = {}
    a["answer_weight"] = x["weight"]
    if use_pandoc:
        a["answer_html"] = pandoc_text(x["text"], src_format="latex")
    else:
        a["answer_text"] = x["text"]
    a["blank_id"] = x["blank_id"][1:-1] if "blank_id" in x else None
    return a


def mk_question_dict(q: Dict, qg_id: Optional[str] = None) -> Dict:
    d = {k: v for k, v in q.items() if k in qargs}
    d["quiz_group_id"] = qg_id
    d["question_text"] = pandoc_text(d["question_text"], src_format="latex")
    use_pandoc = d["question_type"] in pandoc_ans
    d["answers"] = [
        mk_ans(x, i + 1, use_pandoc) for i, x in enumerate(q.get("answers", []))
    ]
    return d


def mk_quiz_dict(q: Dict) -> Dict:
    q0 = q.copy()
    q0["description"] = pandoc_text(q["description"], src_format="latex")
    return q0


def set_points(x: Dict) -> None:
    for y in x["questions"]:
        y["points_possible"] = x["question_points"]


def mk_quiz(qdata: Dict, course: canvasapi.course.Course) -> Any:  # type: ignore
    quiz = course.create_quiz(quiz=mk_quiz_dict(qdata))
    for q in tqdm(qdata["questions"]):
        if q["type"] == "quizgroup":
            quizgroup = quiz.create_question_group(
                quiz_groups=[{k: v for k, v in q.items() if k in qgargs}]
            )
            for q0 in q["questions"]:
                quiz.create_question(question=mk_question_dict(q0, quizgroup.id))
    return quiz


def get_json_data(json_file: str) -> List:
    with open(json_file) as f:
        txt = "".join(f.readlines())
        data = json.loads(txt)

    sdata = []
    for x in data:
        if x.get("type", "") == "quiz":
            current_quiz = x
            current_quiz["questions"] = []
            current_list = current_quiz["questions"]
            sdata.append(current_quiz)
        elif x.get("type", "") == "quizgroup":
            x["questions"] = []
            current_list = x["questions"]
            current_quiz["questions"].append(x)
        else:
            current_list.append(x)
    return sdata


def convert_json_to_quiz(json_file: str, course: canvasapi.course.Course) -> None:  # type: ignore
    for qdata in get_json_data(json_file):
        quiz = mk_quiz(qdata, course)
        print(f'creating quiz: {quiz.id} ("{quiz.title}")')

# import canvas
from canvas.course import split


def test_split() -> None:
    lst = list(range(10))
    assert list(split(lst, 3)) == [[0, 1, 2], [3, 4, 5, 6], [7, 8, 9]]

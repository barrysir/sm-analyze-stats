"""
Throwing together everything that needs to be used by multiple files.
I'll refactor this once it receives more use and I figure out what to do with it
"""

from collections import OrderedDict, namedtuple
from typing import Iterable

import pandas as pd

Mode = namedtuple("Mode", ("mode", "full_name", "single_letter"))
Diff = namedtuple("Diff", ("diff", "single_letter"))

modes = OrderedDict(
    (v.mode, v)
    for v in [
        Mode("dance-single", "Single", "S"),
        Mode("dance-double", "Double", "D"),
    ]
)

diffs = OrderedDict(
    (v.diff, v)
    for v in [
        Diff("Beginner", "B"),
        Diff("Easy", "E"),
        Diff("Medium", "M"),
        Diff("Hard", "H"),
        Diff("Challenge", "X"),
        Diff("Edit", "Z"),
    ]
)


def _pdict(arr: Iterable) -> dict:
    return {v: k for k, v in enumerate(arr)}

_MODE = _pdict(modes.keys())
_DIFFS = _pdict(diffs.keys())


def difficulty_spread_sorter(s: pd.Series) -> pd.Series:
    """
    Sorter function (eg. `df.sort_index(key=(this function))`)
    to sort index columns in difficulty spread order (single/double, B/E/H/M/X/Edit).
    """
    if s.name == "steptype":
        return s.map(lambda x: _MODE.get(x, len(_MODE)))
    elif s.name == "difficulty":
        return s.map(lambda x: _DIFFS.get(x, len(_DIFFS)))
    return s

def pack_name_sorter(s: pd.Series) -> pd.Series:
    """Sorter function to sort columns by pack name"""
    return s.str.lower()

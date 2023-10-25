import argparse
from collections import Counter
import csv
from functools import cached_property
import functools
from pathlib import Path
from typing import Optional, Set, Tuple
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import datetime as dt
from dataclasses import dataclass
from table_stats import TableStats


def strip_prefix(string: str, prefix: str) -> str:
    if string.startswith(prefix):
        return string[len(prefix) :]
    return string


def pack_ordering(s):
    return s.str.lower()


# Note - it can be tempting to get the packname and song by splitting the key.
#     The pack name will be correct but the song name will be subtly wrong because it returns
#     the name of the folder and not the song title itself!
#     TO get the proper song name, you'll have to look at availablesongs (TODO write this better)

import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.cell import Cell
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Fill, PatternFill
from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.worksheet.cell_range import CellRange
import copy


def letter_to_index(c):
    if isinstance(c, str):
        return column_index_from_string(c)
    return c


def copy_columns(ws, column_range, dest_column):
    dest_column = letter_to_index(dest_column)

    # copy cell data and formatting
    for column in ws.iter_cols(column_range.min_col, column_range.max_col):
        for cell in column:
            new_cell = ws.cell(
                row=cell.row, column=dest_column + (cell.column - column_range.min_col), value=cell.value
            )
            if cell.has_style:
                new_cell.font = copy.copy(cell.font)
                new_cell.border = copy.copy(cell.border)
                new_cell.fill = copy.copy(cell.fill)
                new_cell.number_format = copy.copy(cell.number_format)
                new_cell.protection = copy.copy(cell.protection)
                new_cell.alignment = copy.copy(cell.alignment)

    # copy merged cells
    for mcr in set(ws.merged_cells.ranges):
        if not (column_range.min_col <= mcr.min_col <= column_range.max_col):
            continue
        cr = CellRange(mcr.coord)
        cr.shift(col_shift=dest_column - column_range.min_col)
        ws.merge_cells(cr.coord)


from openpyxl.utils.dataframe import dataframe_to_rows


def write_table(df, cell: Cell, index=False, header=False):
    for dr, row in enumerate(dataframe_to_rows(df, index=index, header=header)):
        for dc, value in enumerate(row):
            cell.offset(dr, dc).value = value


def write_row(row: list, cell: Cell):
    for dc, value in enumerate(row):
        cell.offset(0, dc).value = value


import analyzers


def create_general_sheet(ws: Worksheet, stats: TableStats, modes=None):
    if modes is None:
        modes = {"dance-single": "Singles", "dance-double": "Doubles"}

    a = analyzers.chart_counts_for_each_pack(stats, modes)
    write_table(a.reset_index(), ws["A4"])

    ws["A3"].value = len(a)  # set pack count
    write_row(list(a.sum()), ws["B3"])  # set song and chart totals for each mode

    # render difficulty histogram
    # todo: make sure both tables display packs in the right order
    a = analyzers.pack_difficulty_histogram(stats)
    write_table(a.reset_index().drop("pack", axis="columns"), ws["H3"], header=True)


def create_most_played_charts_sheet(ws: Worksheet, stats: TableStats, limit: int = 50):
    all_songs = analyzers.most_played_charts(stats, limit)
    doubles_only = analyzers.most_played_charts(stats, limit, modes=["dance-double"])

    write_table(all_songs, ws["A3"])
    write_table(doubles_only, ws["I3"])

    # todo: set background colour for extra song entries?


def create_most_played_songs_sheet(ws: Worksheet, stats: TableStats, limit: int = 50):
    all_songs = analyzers.most_played_songs(stats, limit)
    doubles_only = analyzers.most_played_songs(stats, limit, modes=["dance-double"])

    write_table(all_songs, ws["A3"])
    write_table(doubles_only, ws["A57"])

    # todo: set background colour for extra song entries?
    # todo: doesn't work for limits > 50, decide what to do


def create_most_played_packs_sheet(ws: Worksheet, stats: TableStats):
    packs_by_playcount = analyzers.most_played_packs(stats)
    song_breakdown = analyzers.most_played_charts_per_pack(stats)

    final_table = packs_by_playcount.join(song_breakdown)
    write_table(final_table.reset_index(), ws["A2"])


def create_recently_played_packs_sheet(ws: Worksheet, stats: TableStats):
    packs = analyzers.recently_played_packs(stats)
    write_table(packs.reset_index(), ws["A2"])


def create_pack_completion_sheet(ws: Worksheet, stats: TableStats):
    completion = analyzers.pack_completion(stats)

    # if the user wants to use different grade boundaries, they can customize the calculations,
    # but they'll have to change the column labeling themselves within the template sheet (this gives them maximal control)
    # todo: pass in only a single array of grade boundaries to reflect that
    # a dict of column names can be passed for convenience but the code will only use arrays
    grade_breakdown = analyzers.pack_score_breakdown(stats, analyzers.GRADE_BY_10)

    table = completion.join(grade_breakdown)
    write_table(table.reset_index(), ws["A3"])


def create_highest_scores_sheet(ws: Worksheet, stats: TableStats):
    # ideas for other ways to split it
    #   - top 5 for each block difficulty
    #   - highest scores (DDR only)
    # there are too many ways to slice the highscore data --
    # I think the only way to make it useful is to make it interactive
    a = analyzers.song_grades_by_meter(stats, analyzers.GRADE_BY_10)
    highest_scores = analyzers.highest_scores(stats, with_ddr=False)
    highest_passes = analyzers.highest_passes(stats, with_ddr=False)

    write_table(a.reset_index(), ws["S2"])
    write_table(highest_scores, ws["A29"])
    write_table(highest_passes, ws["J29"])

    # todo: doubles sheet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="analysis.py",
        description="",
    )

    parser.add_argument("path", help="Path to Stats.xml.")
    parser.add_argument("song_listing", help="Path to file generated by getavailablesongs.py.")
    parser.add_argument("--output", default="output.xlsx", help="Output path.")

    # args = parser.parse_args(['Stats.xml', 'available.csv'])
    args = parser.parse_args()

    s = TableStats()
    s.fill_stats_xml(Path(args.path))
    s.fill_song_listing(Path(args.song_listing))

    wb = load_workbook("template.xlsx")

    def fetch(sheet_name) -> Worksheet:
        print(f"Generating {sheet_name} sheet...")
        return wb[sheet_name]

    ws = fetch("General")
    create_general_sheet(ws, s)

    ws = fetch("Most Played Charts")
    create_most_played_charts_sheet(ws, s)

    ws = fetch("Most Played Songs")
    create_most_played_songs_sheet(ws, s)

    ws = fetch("Most Played Packs")
    create_most_played_packs_sheet(ws, s)

    ws = fetch("Recently Played Packs")
    create_recently_played_packs_sheet(ws, s)

    ws = fetch("Pack Completion")
    create_pack_completion_sheet(ws, s)

    ws = fetch("Highest Scores + Passes")
    create_highest_scores_sheet(ws, s)

    wb.save(args.output)

    # I'm goig to have
    #   a script which outputs every data table (as csvs? json?)
    #       a simple javascript renderer? (drag in a data file: tabs, simple table rendering)
    #       AND a sample google sheets where you can paste in the tables
    #
    #       the javascript renderer is because it takes no work. google sheets requires copy pasting multiple times.
    #       tables could be dynamic size (difficulty histogram)
    #           TODO: make difficulty histogram have a lower end too?
    #                 make it have a step besides 1
    #                 this is getting too wide... just keep it simple
    #
    #       could export to excel, and import into google sheets
    #       making excel spreadsheets is really clunky though...
    #           but it would be equally as hard in javascript
    #           can copy paste data from excel into google sheets

    #   a notebook where you can compute each table individually

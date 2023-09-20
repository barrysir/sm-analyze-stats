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
        return string[len(prefix):]
    return string

def pack_ordering(s):
    return s.str.lower()

# Note - it can be tempting to get the packname and song by splitting the key.
#     The pack name will be correct but the song name will be subtly wrong because it returns
#     the name of the folder and not the song title itself!
#     TO get the proper song name, you'll have to look at availablesongs (TODO write this better)

def most_played_charts(stats: TableStats):
    most_played_charts = stats.song_data(with_mem = False, keep_unavailable = True).sort_values('playcount', ascending=False).head(50)
    
    # Pack / Song / Steptype (Singles / Doubles) / Difficulty (Expert) / Meter (9) / Playcount / Last played
    a = (
        most_played_charts
        .join(stats.song_shorthand)
        .reset_index(level='difficulty')
        [['pack', 'song', 'stepfull', 'difficulty', 'meter', 'playcount', 'lastplayed']]
    )
    return a

def most_played_packs(stats: TableStats, N: int = 10):
    v = stats.song_data(with_mem=False, keep_unavailable=True)

    # calculate the most played packs
    most_played_packs = (
        v.groupby('pack')
        .agg({'playcount': 'sum', 'lastplayed': 'max'})
        .sort_values(by='playcount', ascending=False)
    )

    # calculate the N most played charts per pack
    place = v.sort_values('playcount', ascending=False).groupby('pack').cumcount() + 1
    x = v.assign(place=place)
    x = x[x.place <= N].join(stats.song_shorthand)
    y = x.reset_index().set_index(['pack', 'place'])

    most_played_songs_in_pack = (
        y[['shorthand', 'playcount']]
        .apply(lambda row: "({playcount}) {shorthand}".format(**row), axis=1)
        .unstack('place')
    )

    s = most_played_packs.join(most_played_songs_in_pack).reset_index()
    return s


def recently_played_packs(stats: TableStats):
    last_played_packs = (
        stats.song_data(with_mem=False, keep_unavailable=True)
        .groupby('pack')
        .agg({'lastplayed': 'max'})
        .sort_values(by='lastplayed', ascending=False)
    )
    v = last_played_packs.reset_index()
    return v

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
            new_cell = ws.cell(row=cell.row, column=dest_column + (cell.column - column_range.min_col), value=cell.value)
            if cell.has_style:
                new_cell.font = copy.copy(cell.font)
                new_cell.border = copy.copy(cell.border)
                new_cell.fill = copy.copy(cell.fill)
                new_cell.number_format = copy.copy(cell.number_format)
                new_cell.protection = copy.copy(cell.protection)
                new_cell.alignment = copy.copy(cell.alignment)
    
    # copy merged cells
    for mcr in set(ws.merged_cells.ranges):
        if not(column_range.min_col <= mcr.min_col <= column_range.max_col):
            continue
        cr = CellRange(mcr.coord)
        cr.shift(col_shift=dest_column - column_range.min_col)
        ws.merge_cells(cr.coord)

from openpyxl.utils.dataframe import dataframe_to_rows

def write_table(df, cell: Cell, index=False, header=False):
    for dr,row in enumerate(dataframe_to_rows(df, index=index, header=header)):
        for dc,value in enumerate(row):
            cell.offset(dr,dc).value = value

from openpyxl.worksheet.dimensions import ColumnDimension, DimensionHolder
def find_column(dims: DimensionHolder, col: int):
    for dim in dims.values():
        if dim.min <= col <= dim.max:
            return dim

import analyzers

class DimensionSetter:
    def create_columns(self, cell_range) :
        pass

def create_general_sheet(ws: Worksheet, stats: TableStats, modes = None):
    if modes is None:
        modes = {'dance-single': 'Singles', 'dance-double': 'Doubles'}
    
    # make song/chart count for each mode
    TEMPLATE_RANGE = CellRange("D1:E1")
    for i,label in enumerate(modes.values()):
        dest_col = TEMPLATE_RANGE.min_col + i*2
        # copy template
        if i != 0:
            ws.insert_cols(dest_col, 2)
            copy_columns(ws, TEMPLATE_RANGE, dest_col)
        # change header title
        ws.cell(1, dest_col).value = label
    HISTOGRAM_CELL = ws.cell(3, TEMPLATE_RANGE.min_col + len(modes)*2)
    
    a = analyzers.chart_counts_for_each_pack(stats, modes)
    write_table(a.reset_index(), ws['A4'])

    # todo: set pack count / song and chart totals

    # render difficulty histogram
    # todo: make sure both tables display packs in the right order
    a = analyzers.pack_difficulty_histogram(stats)
    HISTOGRAM_RANGE = CellRange(
        None, 
        HISTOGRAM_CELL.col_idx, HISTOGRAM_CELL.row,
        HISTOGRAM_CELL.col_idx + len(a.columns), HISTOGRAM_CELL.row + len(a)
    )
    print(HISTOGRAM_CELL)
    print(HISTOGRAM_RANGE)
    write_table(a.reset_index().drop('pack', axis='columns'), HISTOGRAM_CELL, header=True)

    col = find_column(ws.column_dimensions, 7)
    col.min = HISTOGRAM_RANGE.min_col
    col.max = HISTOGRAM_RANGE.max_col

    ws.conditional_formatting
    # HISTOGRAM_WIDTH = ws.column_dimensions[get_column_letter(HISTOGRAM_RANGE.min_col)].width
    # for c in range(HISTOGRAM_RANGE.min_col, HISTOGRAM_RANGE.max_col+1):
    #     # ws.column_dimensions[get_column_letter(c)].width = HISTOGRAM_WIDTH
    #     ws.column_dimensions[get_column_letter(c)] = ColumnDimension(ws, width=HISTOGRAM_WIDTH)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='analysis.py',
        description='',
    )

    parser.add_argument('path', help='Path to Stats.xml.')
    parser.add_argument('song_listing', help='Path to file generated by getavailablesongs.py.')
    parser.add_argument('--output', default="output.json", help='Output path.')

    args = parser.parse_args(['Stats.xml', 'available.csv'])

    s = TableStats()
    s.fill_stats_xml(Path(args.path))      # fluent api
    s.fill_song_listing(Path(args.song_listing))

    data = most_played_charts(s)
    # print(data)

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
    #   

    # tree = ET.parse('Stats.xml')
    # root = tree.getroot()
    # songscores = root.find('SongScores')

    # playcount, highscores = allsongnames(songscores)

    # df_playedsongs = pd.DataFrame(playcount, columns=['key', 'steptype', 'difficulty', 'playcount', 'lastplayed'])
    # df_playedsongs = df_playedsongs.set_index(['key', 'steptype', 'difficulty'])

    # df_leaderboards = pd.DataFrame(highscores, columns=['key', 'steptype', 'difficulty', 'place', 'player', 'dp'])
    # df_leaderboards = df_leaderboards.set_index(['key', 'steptype', 'difficulty'])
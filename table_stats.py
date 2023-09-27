
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

class TableStatsConstructing:
    """Mixin for TableStats to hold data parsing functions. (Bad programming practice?)"""
    def fill_stats_xml(self, path_to_stats: Path, packs_to_ignore: Set[str] = set(), track_usb_customs: bool = False, track_slowed_down_plays: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate useful tables from contents of Stats.xml.

        Includes some options to control output data:
            packs_to_ignore: A set of pack names to ignore.
            track_usb_customs: Whether to include USB customs in the data.
                If true, USB customs are stored in a pack named '@mem'.
            track_slowed_down_plays: Whether to include downrated plays in the leaderboard.
                Cop-out flag made for myself to parse out downrated scores as my arcade used to record scores for downrates.

                TODO: might be better to clean this up in the stats file itself.
                    create a remove_ratemodded_scores() function
        
        Returns 2 datatables:
        (1) playstats - Playcount and last played date for every chart.
            index:
                (key, steptype, difficulty)
            columns: 
                playcount (int > 0)
                lastplayed (pd.Timestamp)
            NOTE: this only records songs that have been played at least once.
        (2) leaderboards - Leaderboards (place, player name and score) for every chart.
            index: (key, steptype, difficulty, place)
            columns:
                player (4-character str)
                score (float) - ranging from 0 to 1, so 0.9900 -> 99.00
        """
        stats_xml = ET.parse(path_to_stats)
        root = stats_xml.getroot()
        songscores = root.find('SongScores')

        playdata = []
        leaderboards = []
        for song in songscores:
            songdir = song.get('Dir')   # e.g. 'Songs/DDR A/DANCE ALL NIGHT (DDR EDITION)/'
            
            # deal with AdditionalSongs paths: normalize them to `pack/song/`
            # (packs from AdditionalSongFolders will show as `AdditionalSongs/pack/song/` instead of `pack/song/`)
            # solution(?): take only the last two segments of the path
            # not sure if AdditionalSongs is the only case this will happen,
            # but hopefully this handles anything else that might show up?
            parts = songdir.strip('/').split('/')
            *_, pack, songname = parts
            songdir = f'{pack}/{songname}/'
            
            # ignore any specified packs
            if pack in packs_to_ignore:
                continue
            
            # iterate over every (played) chart in the song
            editcount = 0
            for steps in song.findall('Steps'):
                # grab chart identifiers: steptype and difficulty
                steptype = steps.get('StepsType')   # dance-single, dance-double, ...
                difficulty = steps.get('Difficulty')    # Beginner, Easy, Medium, Hard, Challenge, Edit, ...
                # if there are multiple edits, give them unique names to make processing easier, "Edit", "Edit-1", "Edit-2", etc.
                if difficulty == 'Edit':
                    if editcount >= 1:
                        difficulty = f'{difficulty}-{editcount}'
                    editcount += 1
                    
                # grab playdata info
                numplayed = int(steps.find('HighScoreList/NumTimesPlayed').text)
                lastplayed = pd.Timestamp(steps.find('HighScoreList/LastPlayed').text)
                playdata.append((songdir, steptype, difficulty, numplayed, lastplayed))
                
                # grab leaderboard info
                # ignore USB customs, if flag specified
                if pack != '@mem' or track_usb_customs:
                    chart_lb = []
                    for score in steps.find('HighScoreList').findall('HighScore'):
                        # don't include any scores on slower ratemods, if flag specified
                        if not track_slowed_down_plays:
                            modifiers = score.find('Modifiers').text
                            if 'xMusic' in modifiers:
                                mods = modifiers.split(',')
                                ratemod = next(i for i in mods if 'xMusic' in i)
                                ratemod = ratemod.strip().replace('xMusic', '')
                                ratemod = float(ratemod)
                                if ratemod < 1:
                                    continue
                                
                        chart_lb.append((
                            score.find('Name').text, 
                            float(score.find('PercentDP').text), 
                            datetime.fromisoformat(score.find('DateTime').text)
                        ))

                    chart_lb.sort(key=lambda x: x[1], reverse=True)
                    for i,(name, dp) in enumerate(chart_lb):
                        leaderboards.append((songdir, steptype, difficulty, i+1, name, dp))

        df_playdata = pd.DataFrame(playdata, columns=['key', 'steptype', 'difficulty', 'playcount', 'lastplayed'])
        df_playdata = df_playdata.set_index(['key', 'steptype', 'difficulty'])

        df_leaderboards = pd.DataFrame(leaderboards, columns=['key', 'steptype', 'difficulty', 'place', 'player', 'score', 'timestamp'])
        df_leaderboards = df_leaderboards.set_index(['key', 'steptype', 'difficulty'])

        self.playedsongs = df_playdata
        self.highscores = df_leaderboards
       
    def fill_song_listing(self, path_to_csv: Path, packs_to_ignore: Set[str] = set()) -> pd.DataFrame:
        def loadfromcsv(path):
            with open(path, newline='', encoding='utf8') as csvfile:
                reader = csv.reader(csvfile, delimiter=',', quotechar='"')
                return [row for row in reader]
            
        try:
            availablesongs = loadfromcsv(path_to_csv)
        except FileNotFoundError:
            print(f"Error: couldn't load {path_to_csv}. Report data may be incomplete")
            availablesongs = []
            
        data = []
        encountered = Counter()
        for row in availablesongs:
            # implement IGNORED_PACKS list
            pack,songname = row[0].strip('/').split('/')
            if pack in packs_to_ignore:
                continue
            
            # if a duplicate difficulty is encountered, name it "Edit", "Edit-1", Edit-2", ...
            key = (row[0], row[2], row[3])
            if key in encountered:
                row[3] = f'{row[3]}-{encountered[key]}'
            row[4] = int(row[4])
            encountered[key] += 1
            data.append(row)

        df_availablesongs = pd.DataFrame(data, columns=['key', 'song', 'steptype', 'difficulty', 'meter'])
        df_availablesongs = df_availablesongs.set_index(['key', 'steptype', 'difficulty'])

        self.availablesongs = df_availablesongs
    

@dataclass
class TableStats(TableStatsConstructing):
    """Plain data structure to hold raw and processed data tables for queries to use."""

    # data from Save/Stats.xml
    playedsongs: Optional[pd.DataFrame] = None
    highscores: Optional[pd.DataFrame] = None

    # data from Save/Upload folder
    uploaddata: Optional[pd.DataFrame] = None

    # data from Songs folder
    availablesongs: Optional[pd.DataFrame] = None

    # Lookup table from song key -> pack name and song title.
    # packinfo: Optional[pd.DataFrame] = None

    # Lookup table mapping (song key, steptype, difficulty) -> shorthand text of the chart: "Bloodrush SX12", "Disconnected Disco DX10".
    # song_shorthand: Optional[pd.DataFrame]

    @cached_property
    def song_shorthand(self):
        steptypes = {'dance-single': 'S', 'dance-double': 'D'}
        steptypes_full = {'dance-single': 'Single', 'dance-double': 'Double'}
        difficulties = {'Beginner': 'B', 'Easy': 'E', 'Medium': 'M', 'Hard': 'H', 'Challenge': 'X', 'Edit': 'Z'}

        def shorthand(row):
            # SB, SE, SM, SH, SX
            # (song name) SX10
            # idea (not implemented): display edit name? (song name) SZ69 iunno
            steptype = row.name[1]
            diff = row.name[2].partition('-')[0]
            s = steptypes.get(steptype, None)
            d = difficulties.get(diff, None)
            if s is None or d is None:
                return None
            sfull = steptypes_full.get(steptype, None)
            meter = '' if pd.isna(row.meter) else int(row.meter)
            dtag = f'{s}{d}{meter}'
            return (f'{row.song} {dtag}', dtag, sfull)

        song_shorthand = self.combined.apply(shorthand, axis=1, result_type='expand')
        song_shorthand = song_shorthand.rename(columns=dict(enumerate(['shorthand', 'dtag', 'stepfull'])))
        return song_shorthand

    @cached_property
    def combined(self):
        assert self.playedsongs is not None
        assert self.availablesongs is not None

        # Add entries for songs in availablesongs but not playedsongs.
        # Entry rows filled with 0 playcount and N/A last played.
        combined = self.playedsongs.combine_first(self.availablesongs)
        combined['playcount'] = combined['playcount'].fillna(0).astype(int)

        # sort index for aesthetics (e.g. difficulties show up in Easy, Medium, Hard, Challenge order)
        def pdict(arr):
            return {v:k for k,v in enumerate(arr)}

        MODE = pdict(['dance-single', 'dance-double', 'pump-single', 'pump-double'])
        DIFFS = pdict(['Beginner', 'Easy', 'Medium', 'Hard', 'Challenge'])

        def sorter_difficulty_spread(s):
            if s.name == 'steptype':
                return s.map(lambda x: MODE.get(x, len(MODE)))
            elif s.name == 'difficulty':
                return s.map(lambda x: DIFFS.get(x, len(DIFFS)))
            return s

        combined = combined.sort_index(key=sorter_difficulty_spread)

        # compute pack name and song name for each row
        def split_key(k):
            parts = k.strip('/').split('/')
            pack, *_, inferred_songname = parts
            return (pack, inferred_songname)
            
        # Compute pack name and inferred song name for each key
        # Inferred song name will be used whenever song name is empty
        s = combined.index.get_level_values('key').to_series().drop_duplicates().map(split_key)
        # convert a series of tuples to a dataframe
        s = pd.DataFrame(s.tolist(), columns=['pack', 'song'], index=s.index)
        # update the index to be the same as combined
        v = s.join(pd.DataFrame(index=combined.index))  # update by joining on empty dataframe with index
        # Fill any empty song names with the inferred song name
        v['song'] = combined['song'].combine_first(v['song'])
        # update combined with the computed results
        combined = combined.assign(pack=v['pack'], song=v['song'])

        # store the songname column for later, when calculating the pack_info dataframe
        # drop it from the combined frame cause I don't want the data in this location
        # songnames = combined['songname']
        # combined = combined.drop(columns=['songname'])

        # def inner_loop(row):
        #     k = row.name[0]
        #     parts = k.strip('/').split('/')
        #     pack, *_, inferred_songname = parts
        #     # if songname data doesn't exist, fall back to inferring the song name as the folder name
        #     songname = row.songname
        #     if row.songname is None:
        #         songname = inferred_songname
        #     return (pack, songname)
        
        # pack_info = combined.apply(inner_loop, axis=1, result_type='expand').rename(columns=dict(enumerate(['pack', 'song'])))
        # pack_info

        # # compute packinfo
        # data = []
        # for k,songname in songnames.groupby('key').first().items():

        # self.packinfo = pd.DataFrame(data, columns=['key', 'pack', 'song']).set_index(['key'])

        # There can be songs that have been played but aren't available anymore, e.g. removed packs, USB customs.
        # Leaving these in the combined table can mess up certain queries like chart count and pack completion.
        # Here we'll leave only songs that are available.
        # Note that this also removes the @mem pack
        # TODO: this should be specified within queries, probably
        
        return combined

    def song_data(self, keep_unavailable: bool = True, with_mem: bool = False):
        df = self.combined
        if not with_mem:
            df = df[df.pack != '@mem']
        if not keep_unavailable:
            df = df[df.index.isin(self.availablesongs.index)]
        return df

    def leaderboards(self, keep_unavailable: bool = True, with_mem: bool = False):
        df = self.highscores
        if not with_mem:
            df = df[df.join(self.pack_info).pack != '@mem']
        if not keep_unavailable:
            df = df[df.index.isin(self.availablesongs.index)]
        return df
        

    @cached_property
    def pack_info(self):
        return self.combined.groupby('key').nth(0).reset_index(level=[1,2])[['pack', 'song']]
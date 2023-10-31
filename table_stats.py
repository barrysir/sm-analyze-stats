import csv
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Optional, Set, Tuple

import pandas as pd

import constants


class TableStatsConstructing:
    """Mixin for TableStats to hold data parsing functions. (Bad programming practice?)"""

    def fill_stats_xml(
        self,
        path_to_stats: Path,
        packs_to_ignore: Optional[Set[str]] = None,
        track_usb_customs: bool = False,
        track_slowed_down_plays: bool = False,
    ) -> None:
        """
        Fill data from Stats.xml.

        packs_to_ignore: A set of pack names to ignore.
        track_usb_customs: Whether to include USB customs in the data.
            If true, USB customs are stored in a pack named '@mem'.
        track_slowed_down_plays: Whether to include downrated plays in the generated leaderboards.
            Cop-out flag for myself as my arcade used to record scores for downrates.

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
        if packs_to_ignore is None:
            packs_to_ignore = set()

        stats_xml = ET.parse(path_to_stats)
        root = stats_xml.getroot()
        songscores = root.find("SongScores")

        playdata = []
        leaderboards = []
        for song in songscores:
            songdir = song.get("Dir")  # e.g. 'Songs/DDR A/DANCE ALL NIGHT (DDR EDITION)/'

            # deal with AdditionalSongs paths: normalize them to `pack/song/`
            # (packs from AdditionalSongFolders will show as `AdditionalSongs/pack/song/` instead of `pack/song/`)
            # solution(?): take only the last two segments of the path
            # not sure if AdditionalSongs is the only case this will happen,
            # but hopefully this handles anything else that might show up?
            parts = songdir.strip("/").split("/")
            *_, pack, songname = parts
            songdir = f"{pack}/{songname}/"

            # ignore any specified packs
            if pack in packs_to_ignore:
                continue

            # iterate over every (played) chart in the song
            editcount = 0
            for steps in song.findall("Steps"):
                # grab chart identifiers: steptype and difficulty
                steptype = steps.get("StepsType")  # dance-single, dance-double, ...
                difficulty = steps.get("Difficulty")  # Beginner, Easy, Medium, Hard, Challenge, Edit, ...
                # if there are multiple edits, give them unique names to make processing easier,
                # "Edit", "Edit-1", "Edit-2", etc.
                if difficulty == "Edit":
                    if editcount >= 1:
                        difficulty = f"{difficulty}-{editcount}"
                    editcount += 1

                # grab playdata info
                numplayed = int(steps.find("HighScoreList/NumTimesPlayed").text)
                lastplayed = pd.Timestamp(steps.find("HighScoreList/LastPlayed").text)
                playdata.append((songdir, steptype, difficulty, numplayed, lastplayed))

                # grab leaderboard info
                # ignore USB customs, if flag specified
                if pack != "@mem" or track_usb_customs:
                    chart_lb = []
                    for score in steps.find("HighScoreList").findall("HighScore"):
                        # don't include any scores on slower ratemods, if flag specified
                        if not track_slowed_down_plays:
                            modifiers = score.find("Modifiers").text
                            if "xMusic" in modifiers:
                                mods = modifiers.split(",")
                                ratemod = next(i for i in mods if "xMusic" in i)
                                ratemod = ratemod.strip().replace("xMusic", "")
                                ratemod = float(ratemod)
                                if ratemod < 1:
                                    continue

                        chart_lb.append(
                            (
                                score.find("Name").text,
                                float(score.find("PercentDP").text),
                                datetime.fromisoformat(score.find("DateTime").text),
                            )
                        )

                    chart_lb.sort(key=lambda x: x[1], reverse=True)
                    for i, (name, dp, timestamp) in enumerate(chart_lb):
                        leaderboards.append((songdir, steptype, difficulty, i + 1, name, dp, timestamp))

        df_playdata = pd.DataFrame(playdata, columns=["key", "steptype", "difficulty", "playcount", "lastplayed"])
        df_playdata = df_playdata.set_index(["key", "steptype", "difficulty"])

        df_leaderboards = pd.DataFrame(
            leaderboards, columns=["key", "steptype", "difficulty", "place", "player", "score", "timestamp"]
        )
        df_leaderboards = df_leaderboards.set_index(["key", "steptype", "difficulty"])

        self.playedsongs = df_playdata
        self.highscores = df_leaderboards

    def fill_song_listing(self, path_to_csv: Path, packs_to_ignore: Optional[Set[str]] = None) -> None:
        """Load data from the song listing data file."""

        def loadfromcsv(path: Path) -> list:
            with open(path, newline="", encoding="utf8") as csvfile:
                reader = csv.reader(csvfile, delimiter=",", quotechar='"')
                return [row for row in reader]

        if packs_to_ignore is None:
            packs_to_ignore = set()

        try:
            availablesongs = loadfromcsv(path_to_csv)
        except FileNotFoundError:
            print(f"Error: couldn't load {path_to_csv}. Report data may be incomplete")
            availablesongs = []

        data = []
        encountered = Counter()
        for row in availablesongs:
            # implement IGNORED_PACKS list
            pack, songname = row[0].strip("/").split("/")
            if pack in packs_to_ignore:
                continue

            # if a duplicate difficulty is encountered, name it "Edit", "Edit-1", Edit-2", ...
            key = (row[0], row[2], row[3])
            if key in encountered:
                row[3] = f"{row[3]}-{encountered[key]}"
            row[4] = int(row[4])
            encountered[key] += 1
            data.append(row)

        df_availablesongs = pd.DataFrame(data, columns=["key", "song", "steptype", "difficulty", "meter"])
        df_availablesongs = df_availablesongs.set_index(["key", "steptype", "difficulty"])

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

    @cached_property
    def song_shorthand(self) -> pd.DataFrame:
        """
        Lookup table for various shorthand descriptions of the chart.
        (song key, steptype, difficulty) -> (shorthand, tag, stepfull).
            - shorthand: "Bloodrush SX12", "Disconnected Disco DX10"
            - tag: just the difficulty part: "SX12", "DX10"
            - full: human readable version of the steptype: "Single", "Double"
        """

        def shorthand(row) -> tuple:  # noqa: ANN001
            """Return a string like `(song name) SX10`"""
            # potential future idea: display edit name? (song name) SZ69 iunno
            steptype = row.name[1]
            # this .partition() is to undo the diff name mangling done for edits: "Edit-1", "Edit-2", etc.
            diff = row.name[2].partition("-")[0]
            s = t.single_letter if (t := constants.modes.get(steptype)) else steptype
            d = t.single_letter if (t := constants.diffs.get(diff)) else diff
            sfull = t.full_name if (t := constants.modes.get(steptype)) else steptype
            meter = "" if pd.isna(row.meter) else int(row.meter)
            dtag = f"{s}{d}{meter}"
            return (f"{row.song} {dtag}", dtag, sfull)

        song_shorthand = self.combined.apply(shorthand, axis=1, result_type="expand")
        song_shorthand = song_shorthand.rename(columns=dict(enumerate(["shorthand", "dtag", "stepfull"])))
        return song_shorthand

    @cached_property
    def combined(self) -> pd.DataFrame:
        """(key, steptype, difficulty) -> (pack, song, meter, playcount, lastplayed)"""
        assert self.playedsongs is not None
        assert self.availablesongs is not None

        # Add entries for songs in availablesongs but not playedsongs.
        # Entry rows filled with 0 playcount and N/A last played.
        combined = self.playedsongs.combine_first(self.availablesongs)
        combined["playcount"] = combined["playcount"].fillna(0).astype(int)

        # sort index for aesthetics (e.g. difficulties show up in Easy, Medium, Hard, Challenge order)
        combined = combined.sort_index(key=constants.difficulty_spread_sorter)

        # compute pack name and song name for each row
        def split_key(k: str) -> Tuple[str, str]:
            parts = k.strip("/").split("/")
            pack, *_, inferred_songname = parts
            return (pack, inferred_songname)

        # Compute pack name and inferred song name for each key
        # Inferred song name will be used whenever song name is empty
        s = combined.index.get_level_values("key").to_series().drop_duplicates().map(split_key)
        # convert a series of tuples to a dataframe
        s = pd.DataFrame(s.tolist(), columns=["pack", "song"], index=s.index)
        # update the index to be the same as combined
        v = s.join(pd.DataFrame(index=combined.index))  # update by joining on empty dataframe with index
        # Fill any empty song names with the inferred song name
        v["song"] = combined["song"].combine_first(v["song"])
        # update combined with the computed results
        combined = combined.assign(pack=v["pack"], song=v["song"])

        return combined

    def song_data(self, keep_unavailable: bool = True, with_mem: bool = False) -> pd.DataFrame:
        """
        Grab song list data.
        (key, steptype, difficulty) -> (pack, song, meter, playcount, lastplayed)
        """
        df = self.combined
        if not with_mem:
            df = df[df.pack != "@mem"]
        if not keep_unavailable:
            df = df[df.index.isin(self.availablesongs.index)]
        return df

    def leaderboards(
        self, keep_unavailable: bool = True, with_mem: bool = False, with_ddr: bool = True
    ) -> pd.DataFrame:
        """
        Grab leaderboard data.
        (key, steptype, difficulty) -> (place, player, score, timestamp)
            - place: place in leaderboard, 1 (1st), 4 (4th), 8 (8th), etc.
            - player: 4 character leaderboard name
            - score: number between 0 and 1
        """
        df = self.highscores

        # join pack column so we can filter on it, drop it later
        df = df.join(self.pack_info["pack"])
        if not with_ddr:
            ddr_song_list = df[df.pack.str.contains("DDR") | df.pack.str.contains("DanceDanceRevolution")].index
            df = df[~df.index.isin(ddr_song_list)]
        if not with_mem:
            df = df[df.pack != "@mem"]
        if not keep_unavailable:
            df = df[df.index.isin(self.availablesongs.index)]
        return df.drop("pack", axis="columns")

    @cached_property
    def pack_info(self) -> pd.DataFrame:
        """
        Lookup table from song key -> pack name and song title.
        (key) -> (pack, song)
        """
        return self.combined.groupby("key").nth(0).reset_index(level=[1, 2])[["pack", "song"]]

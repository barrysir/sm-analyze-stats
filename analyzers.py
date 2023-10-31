from typing import Optional, Tuple

import numpy as np
import pandas as pd

import constants
from table_stats import TableStats


def chart_counts_for_each_pack(stats: TableStats, modes: dict[str, str]) -> pd.DataFrame:
    """
    Generate number of charts and songs per pack, in total, and filtered to each given mode.
    (pack name) -> (total song count, total chart count, ... song count per mode, chart count per mode)

    Modes given in {steptype: column_label} format.
    The name of the two columns for each mode will be `{column_label}_charts` and `{column_label}_songs`.
        e.g. modes = {"dance-single": "single"} -> "single_charts" and "single_songs"
    """
    data = stats.song_data(with_mem=False, keep_unavailable=False)

    def one_row_per_song(df: pd.DataFrame) -> pd.DataFrame:
        return df[~df.index.get_level_values("key").duplicated()]

    def songs_and_charts(v: pd.DataFrame, column_prefix: str = "") -> Tuple[pd.Series, pd.Series]:
        """Count number of songs and number of charts in each pack"""
        if column_prefix != "":
            column_prefix = f"{column_prefix}_"
        total_charts = v.groupby("pack").size().rename(f"{column_prefix}charts")
        total_songs = one_row_per_song(v).groupby("pack").size().rename(f"{column_prefix}songs")
        return total_songs, total_charts

    # note: there might be other chart types, like pump-single, pump-double, or weird ones like lights-cabinet
    # to avoid counting unplayable stuff, we'll filter "total charts" to only the requested modes
    total = songs_and_charts(data.loc[pd.IndexSlice[:, list(modes.keys()), :]])
    per_steptype = []
    for steptype, label in modes.items():
        columns = songs_and_charts(data.loc[pd.IndexSlice[:, [steptype], :]], label)
        per_steptype.extend(columns)

    v = pd.concat([*total, *per_steptype], axis=1).fillna(0).sort_index(key=constants.pack_name_sorter)
    return v


def pack_difficulty_histogram(stats: TableStats, upper_limit: int = 27) -> pd.DataFrame:
    """
    Histogram of chart block difficulties in each pack, normalized between 0 and 1.
    (pack) -> (1, 2, 3, ..., 26, 27+, ?)

    Generates columns 1..upper_limit-1, then `upper_limit+`, then ?
    Each column counts the number of charts with that meter.
    The values are then normalized so they sit within [0,1].

    All charts with meter >= upper_limit are grouped into the top folder.
    The side effect of this is to deal with joke difficulties, 69, 420, 31337, etc.
    ? column is for any charts which don't have meter data in the table (unfilled song data).
    """
    data = stats.song_data(with_mem=False, keep_unavailable=False)
    invalid = data[pd.isnull(data.meter) | (data.meter == 0)]
    valid = data[~data.index.isin(invalid.index)]

    # maybe there's a way to do this without stacking and unstacking so much, idk
    normal = (
        valid[valid.meter < upper_limit]
        .groupby(["pack", "meter"])
        .size()
        .unstack()
        .rename(columns=lambda s: str(int(s)))
    )
    above = valid[valid.meter >= upper_limit].groupby(["pack"]).size().rename(f"{upper_limit}+")
    unknown = invalid.groupby(["pack"]).size().rename("?")

    # normalize
    total = pd.concat([normal, above, unknown], axis=1)
    histogram = (total.stack() / total.max(axis="columns")).unstack()
    return histogram


def most_played_charts(stats: TableStats, limit: int = 50, modes: Optional[list] = None) -> pd.DataFrame:
    """
    (pack, song, stepfull, difficulty, meter, playcount, last played) ordered by playcount descending
    Can filter to only certain modes, e.g. doubles only
    """
    data = stats.song_data(with_mem=False, keep_unavailable=True)
    if modes:
        data = data.loc[pd.IndexSlice[:, modes, :]]
    most_played_charts = data.sort_values("playcount", ascending=False).head(limit)

    # Pack / Song / Steptype (Singles / Doubles) / Difficulty (Expert) / Meter (9) / Playcount / Last played
    a = most_played_charts.join(stats.song_shorthand).reset_index(level="difficulty")[
        ["pack", "song", "stepfull", "difficulty", "meter", "playcount", "lastplayed"]
    ]
    return a


def most_played_songs(stats: TableStats, limit: int = 50, modes: Optional[list] = None) -> pd.DataFrame:
    """
    (pack, song, playcount, last played, ...difficulty spread for each mode) sorted by playcount descending
    Includes a spread of the playcounts for each of the songs' charts.
    Can filter to only count charts and generate difficulty spreads from certain modes, e.g. doubles only.
    If then all charts will be considered.
    difficulty spread - columns B/E/M/H/X/Edit, containing count of how many times that chart has been played

    modes - filter data to only consider charts of the given modes.

    """
    combined = stats.song_data(with_mem=False, keep_unavailable=True)
    if modes:
        combined = combined.loc[pd.IndexSlice[:, modes, :]]

    # get list of songs with most plays on them
    playcount_sum = (
        combined.groupby(level="key")
        .agg({"playcount": "sum", "lastplayed": "max"})
        .rename(columns={"playcount": "total"})
        .sort_values("total", ascending=False)
        .head(limit)
    )

    # add pack and song name info, reorder columns so pack/song comes first
    playcount_sum = playcount_sum.join(stats.pack_info)[["pack", "song", "total", "lastplayed"]]

    # now generate the playcount breakdown for the difficulty spread
    # creates columns (dance-single, Beginner), (dance-single, Easy), ... for each played charts
    playcount_breakdown = (
        combined.loc[playcount_sum.index.values, "playcount"].unstack(
            level=[1, 2]
        )  # move stepstype,difficulty to columns
    )

    # some columns might be missing
    # make sure each difficulty has a BEMHX difficulty spread
    for mode in playcount_breakdown.columns.get_level_values(0).unique().to_list():
        for diff in constants.diffs:
            if (mode, diff) not in playcount_breakdown.columns:
                playcount_breakdown[(mode, diff)] = float("nan")

    # order columns in BEHMX order
    playcount_breakdown = playcount_breakdown.sort_index(key=constants.difficulty_spread_sorter, axis=1)

    # join the tables together
    playcount_sum.columns = pd.MultiIndex.from_product([playcount_sum.columns, [""]])
    playcount_breakdown = playcount_sum.join(playcount_breakdown)

    return playcount_breakdown


def most_played_packs(stats: TableStats) -> pd.DataFrame:
    """
    Return the packs with the highest playcount across all songs in the pack
    (pack) -> (playcount, lastplayed) sorted by playcount descending
    """
    v = stats.song_data(with_mem=False, keep_unavailable=True)
    most_played_packs = (
        v.groupby("pack").agg({"playcount": "sum", "lastplayed": "max"}).sort_values(by="playcount", ascending=False)
    )
    return most_played_packs


def most_played_charts_per_pack(stats: TableStats, N: int = 10) -> pd.DataFrame:
    """
    Return the N most played charts in each pack
    The charts are already string formatted for Excel rendering, if you need it in
    a more consumable format feel free to refactor this function

    (pack) -> (columns named 1 to N, containing the N most played charts by playcount descending)
        in event of playcount tie, no sorting behaviour is defined
    """
    v = stats.song_data(with_mem=False, keep_unavailable=True)

    # don't list any songs with 0 playcount, have a blank spot instead
    v = v[v.playcount > 0]

    # give each chart a place within its pack and only keep top N
    place = v.sort_values("playcount", ascending=False).groupby("pack").cumcount() + 1
    x = v.assign(place=place)
    x = x[x.place <= N]

    # join song shorthand
    x = x.join(stats.song_shorthand)

    # there's a lot of columns going around, rearrange the table and crop only the ones we need
    x = x.reset_index().set_index(["pack", "place"])[["shorthand", "playcount"]]

    # render short text for each entry
    x = x.apply(lambda row: "({playcount}) {shorthand}".format(**row), axis=1)

    # move place into the columns
    x = x.unstack("place")
    return x


def recently_played_packs(stats: TableStats) -> pd.DataFrame:
    """
    Return packs sorted by when any song within them was last played, from most to least recent.
    (pack, last played) sorted by last played descending
    """
    last_played_packs = (
        # set keep_unavailable=False, don't want to display any packs which have been removed
        stats.song_data(with_mem=False, keep_unavailable=False)
        .groupby("pack")
        .agg({"lastplayed": "max"})
        .sort_values(by="lastplayed", ascending=False)
    )
    return last_played_packs


def pack_completion(stats: TableStats) -> pd.DataFrame:
    """
    Count number of songs/charts played in each pack and the ratio of played songs/charts.

    (pack) -> (played songs, total songs, ratio songs, played charts, total charts, ratio charts)
    sorted by (ratio_songs, total_songs) descending
    """

    def one_row_per_song(song_data: pd.DataFrame) -> pd.DataFrame:
        return song_data[~song_data.index.get_level_values("key").duplicated()]

    v = stats.song_data(with_mem=False, keep_unavailable=False)
    v_played = v[v.playcount > 0]

    played_charts = v_played.groupby("pack").size()
    total_charts = v.groupby("pack").size()

    played_songs = one_row_per_song(v_played).groupby("pack").size()
    total_songs = one_row_per_song(v).groupby("pack").size()

    percentage_played = (
        pd.DataFrame(index=total_charts.index)
        .assign(
            played_songs=played_songs,
            total_songs=total_songs,
            ratio_songs=played_songs / total_songs,
            played_charts=played_charts,
            total_charts=total_charts,
            ratio_charts=played_charts / total_charts,
        )
        .fillna(0)
        .sort_values(["ratio_songs", "total_songs"], ascending=False)
    )
    return percentage_played


GRADE_BY_10 = {
    1.00: "☆☆☆☆",
    0.99: "☆☆☆",
    0.98: "☆☆",
    0.96: "☆",
    0.90: "90",
    0.80: "80",
    0.70: "70",
    0.60: "60",
    0.50: "50",
    0: "0",
}
GRADE_SIMPLY_LOVE = {
    1.00: "☆☆☆☆",
    0.99: "☆☆☆",
    0.98: "☆☆",
    0.96: "☆",
    0.94: "S+",
    0.92: "S",
    0.89: "S-",
    0.86: "A+",
    0.83: "A",
    0.80: "A-",
    0.76: "B+",
    0.72: "B",
    0.68: "B-",
    0.64: "C+",
    0.60: "C",
    0.55: "C-",
    0: "D",
}


def pack_score_breakdown(stats: TableStats, grade_boundaries: Optional[dict[float, str]] = None) -> pd.DataFrame:
    """
    Count the number of quads, tri-stars, double stars, fails, etc. achieved in each pack
    (grade boundaries are customizable).

    (pack) -> (number of charts in each grade boundary + extra Failed column)

    grade_boundaries - format {grade_threshold: label}. small example: `{0.96: "star", 0.70: "70", 0: "D"}`
        The script will create columns "star", "70", "D" counting the number of scores in each boundary,
        plus an additional "Failed" column counting all played charts with no score (no passes).
    """
    if grade_boundaries is None:
        grade_boundaries = GRADE_BY_10

    # massage grade_boundaries into values for pd.cut
    c = list(grade_boundaries.items())
    c.sort(key=lambda x: x[0])
    values = [i[0] for i in c] + [np.inf]
    labels = [i[1] for i in c]

    # compute the grade of each top score in the leaderboard
    # note: have to be careful that the returned table has a row for every pack
    # because the highscores table might be missing some packs (packs with no scores on any songs)
    # some reindexing trickery is used. you can see this below
    leaderboards = stats.leaderboards(with_mem=False, keep_unavailable=False)
    top_scores_per_chart = leaderboards[~leaderboards.index.duplicated(keep="first")]
    top_grades_per_chart = pd.cut(top_scores_per_chart["score"], values, labels=labels, right=False).rename("grade")

    # count grades
    grade_count_per_pack = top_grades_per_chart.to_frame().join(stats.pack_info).groupby(["pack", "grade"]).size()

    # calculate failed charts
    # grab pack list for reindexing
    v = stats.song_data(with_mem=False, keep_unavailable=False)
    pack_list = v["pack"].unique()

    # first get count of played charts (reindexed to pack list)
    # second get count of chart scores (reindexed to pack list)
    # subtract first - second to get number of failed scores per pack
    v_played = v[v.playcount > 0]
    played_charts = v_played.groupby("pack").size().reindex(index=pack_list, fill_value=0)
    scored_charts = grade_count_per_pack.groupby("pack").sum().reindex(index=pack_list, fill_value=0)
    failed_charts = played_charts - scored_charts

    # smash grade counts into a table format (reindexed to pack list) and add the failed scores column
    asdf = grade_count_per_pack.unstack().sort_index(axis=1, ascending=False).reindex(index=pack_list, fill_value=0)
    output = asdf.join(failed_charts.rename("Failed"))

    return output


def song_grades_by_meter(
    stats: TableStats, grade_boundaries: Optional[dict[float, str]] = None, upper_limit: int = 27
) -> pd.DataFrame:
    """
    Count the number of quads, tri-stars, double stars, fails, etc. achieved across all songs
    of a given difficulty block (grade boundaries are customizable).

    (meter) -> (number of charts in each grade boundary)

    grade_boundaries - format {grade_threshold: label}. small example: `{0.96: "star", 0.70: "70", 0: "D"}`
        The script will create columns "star", "70", "D" counting the number of scores in each boundary.
    """
    if grade_boundaries is None:
        grade_boundaries = GRADE_BY_10

    # massage grade_boundaries into values for pd.cut
    c = list(grade_boundaries.items())
    c.sort(key=lambda x: x[0])
    values = [i[0] for i in c] + [np.inf]
    labels = [i[1] for i in c]

    # compute the grade of each top score in the leaderboard
    # exclude DDR charts because they have their own difficulty meter
    leaderboards = stats.leaderboards(with_mem=False, keep_unavailable=False, with_ddr=False)
    top_scores_per_chart = leaderboards[~leaderboards.index.duplicated(keep="first")]
    top_grades_per_chart = pd.cut(top_scores_per_chart["score"], values, labels=labels, right=False).rename("grade")

    x = (
        top_grades_per_chart.to_frame()
        .join(stats.song_data(with_mem=False, keep_unavailable=False))
        .groupby(["meter", "grade"])
        .size()
    )

    # Filter to only songs below or at the difficulty limit
    x = x.loc[:upper_limit]

    # todo: fill missing difficulties with 0
    return x.unstack()


def highest_scores(stats: TableStats, with_ddr: bool, limit: int = 100) -> pd.DataFrame:
    """
    Return top N highest scores. Ties are sorted by meter descending.

    (pack, song, mode, difficulty, meter, player, score, timestamp)
    sorted by (score, meter) descending

    with_ddr - exclude DDR songs, since their metering system is different
    """
    leaderboards = (
        stats.leaderboards(with_mem=False, keep_unavailable=False, with_ddr=with_ddr)
        .join(stats.song_data(with_mem=False, keep_unavailable=False))
        .join(stats.song_shorthand["stepfull"])
        .sort_values(by=["score", "meter"], ascending=False)
    )
    return leaderboards.head(limit).reset_index()[
        ["pack", "song", "stepfull", "difficulty", "meter", "player", "score", "timestamp"]
    ]


def highest_passes(stats: TableStats, with_ddr: bool, max_diff: int = 27, limit: int = 100) -> pd.DataFrame:
    """
    Return top N highest block passes. Ties are sorted by score descending.

    (pack, song, mode, difficulty, meter, player, score, timestamp)
    sorted by (meter, score) descending

    with_ddr - exclude DDR songs, since their metering system is different
    max_diff - required to exclude passes on joke difficulties, e.g. 69.
    """
    leaderboards = (
        stats.leaderboards(with_mem=False, keep_unavailable=False, with_ddr=with_ddr)
        .join(stats.song_data(with_mem=False, keep_unavailable=False))
        .join(stats.song_shorthand["stepfull"])
        .sort_values(by=["meter", "score"], ascending=False)
    )
    leaderboards = leaderboards[leaderboards.meter <= max_diff]
    return leaderboards.head(limit).reset_index()[
        ["pack", "song", "stepfull", "difficulty", "meter", "player", "score", "timestamp"]
    ]

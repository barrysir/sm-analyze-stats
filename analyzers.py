from typing import Optional

import numpy as np
from table_stats import TableStats
import pandas as pd

def pack_ordering(s):
    return s.str.lower()

def chart_counts_for_each_pack(stats: TableStats, modes: dict[str, str]):
    data = stats.song_data(with_mem = False, keep_unavailable = False)

    def group_by_songs(df):
        return df[~df.index.get_level_values('key').duplicated()]

    def songs_and_charts(v: pd.DataFrame, column_prefix=''):
        if column_prefix != '':
            column_prefix = f'{column_prefix}_'    
        total_charts = v.groupby('pack').size().rename(f'{column_prefix}charts')
        total_songs = group_by_songs(v).groupby('pack').size().rename(f'{column_prefix}songs')
        return total_songs, total_charts

    # note: there might be other chart types, like pump-single, pump-double, or weird ones like lights-cabinet
    # to avoid counting unplayable stuff, we'll filter "total charts" to only the requested modes
    total = songs_and_charts(data.loc[pd.IndexSlice[:, list(modes.keys()), :]])
    per_steptype = []
    for steptype,label in modes.items():
        columns = songs_and_charts(data.loc[pd.IndexSlice[:, [steptype], :]], label)
        per_steptype.extend(columns)

    v = pd.concat([*total, *per_steptype], axis=1).fillna(0).sort_index(key=pack_ordering)
    return v

def pack_difficulty_histogram(stats: TableStats, upper_limit: int = 27):
    data = stats.song_data(with_mem = False, keep_unavailable = False)
    invalid = data[pd.isnull(data.meter) | (data.meter == 0)]
    valid = data[~data.index.isin(invalid.index)]

    # maybe there's a way to do this without stacking and unstacking so much, idk
    normal = valid[valid.meter < upper_limit].groupby(['pack', 'meter']).size().unstack().rename(columns=lambda s: str(int(s)))
    above = valid[valid.meter >= upper_limit].groupby(['pack']).size().rename('27+')
    unknown = invalid.groupby(['pack']).size().rename('?')
    
    # normalize 
    total = pd.concat([normal, above, unknown], axis=1)
    histogram = (total.stack() / total.max(axis='columns')).unstack()
    return histogram

def most_played_charts(stats: TableStats, limit: int = 50, modes: Optional[list] = None):
    data = stats.song_data(with_mem = False, keep_unavailable = True)
    if modes:
        data = data.loc[pd.IndexSlice[:, modes, :]]
    most_played_charts = data.sort_values('playcount', ascending=False).head(limit)
    
    # Pack / Song / Steptype (Singles / Doubles) / Difficulty (Expert) / Meter (9) / Playcount / Last played
    a = (
        most_played_charts
        .join(stats.song_shorthand)
        .reset_index(level='difficulty')
        [['pack', 'song', 'stepfull', 'difficulty', 'meter', 'playcount', 'lastplayed']]
    )
    return a

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

def most_played_songs(stats: TableStats, limit: int = 50, modes: Optional[list] = None):
    combined = stats.song_data(with_mem = False, keep_unavailable = True)
    if modes:
        combined = combined.loc[pd.IndexSlice[:, modes, :]]

    # get list of songs with most plays on them
    playcount_sum = (
        combined.groupby(level="key")
        .agg({'playcount': 'sum', 'lastplayed': 'max'})
        .rename(columns={'playcount': 'total'})
        .sort_values('total', ascending=False)
        .head(50)
    )

    # add pack and song name info, reorder columns so pack/song comes first
    playcount_sum = playcount_sum.join(stats.pack_info)[['pack', 'song', 'total', 'lastplayed']]

    # now generate the playcount breakdown for the difficulty spread
    # creates columns (dance-single, Beginner), (dance-single, Easy), ... for each played charts
    playcount_breakdown = (
        combined.loc[playcount_sum.index.values, 'playcount']
        .unstack(level=[1, 2])  # move stepstype,difficulty to columns
    )

    # some columns might be missing
    # make sure each difficulty has a BEMHX difficulty spread
    for mode in playcount_breakdown.columns.get_level_values(0).unique().to_list():
        for diff in ['Beginner', 'Easy', 'Medium', 'Hard', 'Challenge', 'Edit']:
            if (mode, diff) not in playcount_breakdown.columns:
                playcount_breakdown[(mode, diff)] = float('nan')
    
    # order columns in BEHMX order
    playcount_breakdown = playcount_breakdown.sort_index(key=sorter_difficulty_spread, axis=1)

    # join the tables together
    playcount_sum.columns = pd.MultiIndex.from_product([playcount_sum.columns, ['']])
    playcount_breakdown = playcount_sum.join(playcount_breakdown)
    
    return playcount_breakdown


def most_played_packs(stats: TableStats):
    v = stats.song_data(with_mem=False, keep_unavailable=True)
    most_played_packs = (
        v.groupby('pack')
        .agg({'playcount': 'sum', 'lastplayed': 'max'})
        .sort_values(by='playcount', ascending=False)
    )
    return most_played_packs

def most_played_charts_per_pack(stats: TableStats, N: int = 10):
    v = stats.song_data(with_mem=False, keep_unavailable=True)

    # don't list any songs with 0 playcount, have a blank spot instead
    v = v[v.playcount > 0]

    # give each chart a place within its pack and only keep top N
    place = v.sort_values('playcount', ascending=False).groupby('pack').cumcount() + 1
    x = v.assign(place=place)
    x = x[x.place <= N]
    
    # join song shorthand
    x = x.join(stats.song_shorthand)
    
    # there's a lot of columns going around, rearrange the table and crop only the ones we need
    x = x.reset_index().set_index(['pack', 'place'])[['shorthand', 'playcount']]
    
    # render short text for each entry
    x = x.apply(lambda row: "({playcount}) {shorthand}".format(**row), axis=1)
    
    # move place into the columns
    x = x.unstack('place')
    return x

def recently_played_packs(stats: TableStats):
    # todo: keep_unavailable flag: hide packs from recently played list when they get removed?
    last_played_packs = (
        stats.song_data(with_mem=False, keep_unavailable=False)
        .groupby('pack')
        .agg({'lastplayed': 'max'})
        .sort_values(by='lastplayed', ascending=False)
    )
    return last_played_packs

def pack_completion(stats: TableStats):
    def group_by_songs(df):
        return df[~df.index.get_level_values('key').duplicated()]
    
    v = stats.song_data(with_mem=False, keep_unavailable=False)
    v_played = v[v.playcount > 0]

    played_charts = v_played.groupby('pack').size()
    total_charts = v.groupby('pack').size()

    played_songs = group_by_songs(v_played).groupby('pack').size()
    total_songs = group_by_songs(v).groupby('pack').size()

    percentage_played = (
        pd.DataFrame(index=total_charts.index)
        .assign(
            played_songs = played_songs,
            total_songs = total_songs,
            ratio_songs = played_songs/total_songs,
            played_charts = played_charts,
            total_charts = total_charts,
            ratio_charts = played_charts/total_charts,
        )
        .fillna(0)
        .sort_values(['ratio_songs', 'total_songs'], ascending=False)
    )
    return percentage_played

GRADE_BY_10 = {
    1.00: '☆☆☆☆',
    0.99: '☆☆☆',
    0.98: '☆☆',
    0.96: '☆',
    0.90: '90',
    0.80: '80',
    0.70: '70',
    0.60: '60',
    0.50: '50',
    0: '0',
}
GRADE_SIMPLY_LOVE = {
    1.00: '☆☆☆☆',
    0.99: '☆☆☆',
    0.98: '☆☆',
    0.96: '☆',
    0.94: 'S+',
    0.92: 'S',
    0.89: 'S-',
    0.86: 'A+',
    0.83: 'A',
    0.80: 'A-',
    0.76: 'B+',
    0.72: 'B',
    0.68: 'B-',
    0.64: 'C+',
    0.60: 'C',
    0.55: 'C-',
    0: 'D',
}

def pack_score_breakdown(stats: TableStats, grade_boundaries: Optional[dict[float, str]] = None):
    # have to be careful to have all packs listed in this table because the highscores table might be missing some packs (e.g. packs that haven't been played yet, or with no passes on any songs)
    # to ensure this some reindexing trickery is used

    if grade_boundaries is None:
        grade_boundaries = GRADE_BY_10

    # massage grade_boundaries into values for pd.cut
    c = list(grade_boundaries.items())
    c.sort(key=lambda x: x[0])
    values = [i[0] for i in c] + [np.inf]
    labels = [i[1] for i in c]

    # compute the grade of each top score in the leaderboard
    leaderboards = stats.leaderboards(with_mem=False, keep_unavailable=False)
    top_scores_per_chart = leaderboards[~leaderboards.index.duplicated(keep='first')]
    top_grades_per_chart = pd.cut(
        top_scores_per_chart['score'],
        values,
        labels=labels,
        right=False
    ).rename('grade')

    # count grades
    grade_count_per_pack = top_grades_per_chart.to_frame().join(stats.pack_info).groupby(['pack', 'grade']).size()

    # calculate failed charts
    # grab pack list for reindexing
    v = stats.song_data(with_mem=False, keep_unavailable=False)
    pack_list = v['pack'].unique()
    
    # first get count of played charts (reindexed to pack list)
    # second get count of chart scores (reindexed to pack list)
    # subtract first - second to get number of failed scores per pack
    v_played = v[v.playcount > 0]
    played_charts = v_played.groupby('pack').size().reindex(index=pack_list, fill_value=0)
    scored_charts = grade_count_per_pack.groupby('pack').sum().reindex(index=pack_list, fill_value=0)
    failed_charts = played_charts - scored_charts

    # smash grade counts into a table format (reindexed to pack list) and add the failed scores column
    asdf = grade_count_per_pack.unstack().sort_index(axis=1, ascending=False).reindex(index=pack_list, fill_value=0)
    output = asdf.join(failed_charts.rename('Failed'))

    return output

def song_grades_by_meter(stats: TableStats, grade_boundaries: Optional[dict[float, str]] = None, upper_limit: int = 27):
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
    top_scores_per_chart = leaderboards[~leaderboards.index.duplicated(keep='first')]
    top_grades_per_chart = pd.cut(
        top_scores_per_chart['score'],
        values,
        labels=labels,
        right=False
    ).rename('grade')
    
    x = top_grades_per_chart.to_frame().join(stats.song_data(with_mem=False, keep_unavailable=False)).groupby(['meter', 'grade']).size()

    # Filter to only songs below or at the difficulty limit
    x = x.loc[:upper_limit]
    
    # todo: fill missing difficulties with 0
    return x.unstack()

def highest_scores(stats: TableStats, with_ddr: bool, limit: int = 100):
    leaderboards = stats.leaderboards(with_mem=False, keep_unavailable=False, with_ddr=with_ddr).join(stats.song_data(with_mem=False, keep_unavailable=False)).join(stats.song_shorthand).sort_values(by=['score', 'meter'], ascending=False)
    return (
        leaderboards.head(limit)
        .reset_index()
        [['pack', 'song', 'stepfull', 'difficulty', 'meter', 'player', 'score', 'timestamp']]
    )

def highest_passes(stats: TableStats, with_ddr: bool, max_diff: int = 27, limit: int = 100):
    leaderboards = stats.leaderboards(with_mem=False, keep_unavailable=False, with_ddr=with_ddr).join(stats.song_data(with_mem=False, keep_unavailable=False)).join(stats.song_shorthand).sort_values(by=['meter', 'score'], ascending=False)
    leaderboards = leaderboards[leaderboards.meter <= max_diff]
    return (
        leaderboards.head(limit)
        .reset_index()
        [['pack', 'song', 'stepfull', 'difficulty', 'meter', 'player', 'score', 'timestamp']]
    )
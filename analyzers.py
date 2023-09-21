from typing import Optional
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
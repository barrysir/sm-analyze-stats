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
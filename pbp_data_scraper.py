import pandas as pd
from tqdm import tqdm
import cbbpy.mens_scraper as s

def compute_team_stats(pbp, time_filter='full'):
    df = pbp.copy()

    if 'secs_left_half' not in df.columns or 'half' not in df.columns:
        raise ValueError("Play-by-play data must include 'secs_left_half' and 'half' columns.")

    if time_filter == '2nd_half':
        df = df[df['half'] >= 2]
    elif time_filter == 'last_5':
        df = df[df['secs_left_half'] <= 300]
    elif time_filter == 'last_1':
        df = df[df['secs_left_half'] <= 60]
    elif time_filter == 'last_30':
        df = df[df['secs_left_half'] <= 30]

    if df.empty:
        return {}  

    df['is_fg']        = df['play_type'].str.contains('jumper|layup|dunk|hook|tip', case=False, na=False)
    df['is_three']     = df['is_fg'] & df['play_desc'].str.contains('Three Point', case=False, na=False)
    df['is_two']       = df['is_fg'] & ~df['is_three']
    df['made_fg']      = df['is_fg'] & df['scoring_play']
    df['miss_fg']      = df['is_fg'] & ~df['scoring_play']
    df['is_ft']        = df['play_type'].str.contains('free throw', case=False, na=False)
    df['made_ft']      = df['is_ft'] & df['scoring_play']
    df['miss_ft']      = df['is_ft'] & ~df['scoring_play']
    df['is_turnover']  = df['play_type'].str.contains('turnover', case=False, na=False)
    df['is_rebound']   = df['play_type'].str.contains('rebound', case=False, na=False) & ~df['play_desc'].str.contains('Deadball', case=False, na=False)

    df['possession_start'] = df[['is_three','is_two','is_turnover']].any(axis=1)

    teams = df['home_team'].iloc[0], df['away_team'].iloc[0]
    game_out = {}

    for tm in teams:
        tm_df = df[df['play_team'] == tm]

        poss = df[df['possession_start'] & (df['play_team'] == tm)]
        three_rate = poss['is_three'].mean()
        two_rate   = poss['is_two'  ].mean()
        to_rate    = poss['is_turnover'].mean()

        three_pct = (tm_df['made_fg'] & tm_df['is_three']).sum() / max(1, (tm_df['is_three'] & tm_df['is_fg']).sum())
        two_pct   = (tm_df['made_fg'] & tm_df['is_two'  ]).sum() / max(1, (tm_df['is_two'  ] & tm_df['is_fg']).sum())
        ft_pct    =  tm_df['made_ft'].sum() / max(1, tm_df['is_ft'].sum())

        misses = df[df['miss_fg'] & (df['play_team'] == tm)]
        miss_ids = misses.index
        reb_window = df[df.index.isin(miss_ids + 1)]
        oreb = reb_window['play_team'] == tm
        oreb_pct = oreb.sum() / max(1, reb_window.shape[0])

        ft_misses = df[df['miss_ft']]
        ft_ids = ft_misses.index
        ft_reb = df[df.index.isin(ft_ids + 1)]
        oroft_pct = (ft_reb['play_team'] == tm).sum() / max(1, (ft_reb['play_team'] == tm).count())
        droft_pct = (ft_reb['play_team'] != tm).sum() / max(1, (ft_reb['play_team'] != tm).count())

        game_out[tm] = dict(
            Three_Point_Rate = three_rate,
            Two_Point_Rate   = two_rate,
            Turnover_Rate    = to_rate,
            Three_Point_Pct  = three_pct,
            Two_Point_Pct    = two_pct,
            FT_Pct           = ft_pct,
            OREB_Pct         = oreb_pct,
            OROFT_Pct        = oroft_pct,
            DROFT_Pct        = droft_pct,
        )
    return game_out

def season_team_stats(season_year=2025, out_csv='team_cumulative_stats_2025.csv', time_filter='full'):
    
    _, _, season_pbp = s.get_games_season(season_year, info=False, box=False, pbp=True)
    grouped = season_pbp.groupby('game_id', sort=False)
    running = {}

    print(f'Processing {len(grouped)} games using time filter: "{time_filter}"')
    for gid, gdf in tqdm(grouped, unit='game'):
        game_dict = compute_team_stats(gdf, time_filter=time_filter)
        for tm, vals in game_dict.items():
            running.setdefault(tm, []).append(vals)

    rows = []
    for tm, lst in running.items():
        df_tm = pd.DataFrame(lst)
        season_row = df_tm.mean(numeric_only=True)
        season_row['team'] = tm
        rows.append(season_row)

    season_df = pd.DataFrame(rows).sort_values('team').reset_index(drop=True)
    season_df.to_csv(out_csv, index=False)
    return season_df

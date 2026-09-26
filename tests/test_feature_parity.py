"""src/features/pipeline.py が C03 / C04 の従来挙動を再現することを検証する。

各ノートブックのセルからコードをそのまま写した参照実装を持ち、
実データ（data/processed/*.parquet）で列ごとに突き合わせる。

    python3 tests/test_feature_parity.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from features.pipeline import build_features, C03_CONFIG, C04_CONFIG  # noqa: E402


# --------------------------------------------------------------------------
# 参照実装: C03_model_training.ipynb セル4・セル6 の写し
# --------------------------------------------------------------------------
def reference_c03(races_df, results_df):
    obstacle_races = races_df[races_df['race_name'].str.contains('障害', na=False)]['race_id'].unique()
    flat_results = results_df[~results_df['race_id'].isin(obstacle_races)].copy()
    flat_results = flat_results[~flat_results['surface'].astype(str).str.contains('障害', na=False)]
    flat_results = flat_results[flat_results['jockey_name'] != '藤岡康太']
    flat_results['is_top3'] = (flat_results['finish_position'] <= 3).astype(int)
    flat_results['race_date'] = pd.to_datetime(flat_results['race_date'])
    flat_results['year'] = flat_results['race_date'].dt.year
    flat_results = flat_results.sort_values(by=['horse_id', 'race_date'])

    flat_results['horse_expected_top3_rate'] = flat_results.groupby('horse_id')['is_top3'].transform(
        lambda x: x.shift().expanding().mean())
    global_top3_rate = flat_results['is_top3'].mean()
    flat_results['horse_expected_top3_rate'] = flat_results['horse_expected_top3_rate'].fillna(global_top3_rate * 0.5)

    flat_results['jockey_added_value_in_race'] = flat_results['is_top3'] - flat_results['horse_expected_top3_rate']
    flat_results = flat_results.sort_values(by=['jockey_id', 'race_date'])
    flat_results['jockey_added_value'] = flat_results.groupby('jockey_id')['jockey_added_value_in_race'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0)

    flat_results = flat_results.sort_values(by=['trainer_id', 'race_date'])
    flat_results['trainer_added_value'] = flat_results.groupby('trainer_id')['jockey_added_value_in_race'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0)

    flat_results = flat_results.sort_values(by=['horse_id', 'race_date'])
    flat_results['prev_finish'] = flat_results.groupby('horse_id')['finish_position'].shift(1)
    flat_results['prev_last_3f'] = flat_results.groupby('horse_id')['last_3f'].shift(1)
    flat_results['prev_odds'] = flat_results.groupby('horse_id')['odds'].shift(1)
    flat_results['prev_popularity'] = flat_results.groupby('horse_id')['popularity'].shift(1)
    flat_results['prev_race_date'] = flat_results.groupby('horse_id')['race_date'].shift(1)
    flat_results['days_since_last'] = (flat_results['race_date'] - flat_results['prev_race_date']).dt.days

    flat_results['prev_jockey_id'] = flat_results.groupby('horse_id')['jockey_id'].shift(1)
    flat_results['is_jockey_changed'] = (flat_results['jockey_id'] != flat_results['prev_jockey_id']).astype(int)
    flat_results.loc[flat_results['prev_jockey_id'].isna(), 'is_jockey_changed'] = 0
    flat_results['is_debut'] = flat_results['prev_finish'].isna().astype(int)
    flat_results['surface_encoded'] = flat_results['surface'].map({'芝': 0, 'ダート': 1}).fillna(-1)
    return flat_results


# --------------------------------------------------------------------------
# 参照実装: C04_winning_strategy_simulation.ipynb セル4・セル6 の写し
# --------------------------------------------------------------------------
def reference_c04(races_df, results_df):
    overlap_cols = [c for c in races_df.columns if c in results_df.columns and c != 'race_id']
    df_races_sub = races_df.drop(columns=overlap_cols)
    clean_df = pd.merge(results_df, df_races_sub, on='race_id', how='left')

    clean_df = clean_df[~clean_df['race_name'].str.contains('障害', na=False)]
    clean_df = clean_df[~clean_df['surface'].astype(str).str.contains('障害', na=False)]
    clean_df = clean_df[pd.to_numeric(clean_df['finish_position'], errors='coerce').notna()]
    clean_df['finish_position'] = clean_df['finish_position'].astype(int)
    clean_df['odds'] = pd.to_numeric(clean_df['odds'], errors='coerce')
    clean_df['popularity'] = pd.to_numeric(clean_df['popularity'], errors='coerce')
    clean_df = clean_df[clean_df['odds'].notna() & (clean_df['odds'] > 0)]

    clean_df['race_date'] = pd.to_datetime(clean_df['race_date'])
    clean_df['year'] = clean_df['race_date'].dt.year
    clean_df['is_win'] = (clean_df['finish_position'] == 1).astype(int)
    clean_df['is_top3'] = (clean_df['finish_position'] <= 3).astype(int)
    clean_df = clean_df.sort_values(by=['horse_id', 'race_date'])

    clean_df['horse_prev_win_rate'] = clean_df.groupby('horse_id')['is_win'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0.08)
    clean_df['horse_prev_top3_rate'] = clean_df.groupby('horse_id')['is_top3'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0.24)
    clean_df['prev_finish'] = clean_df.groupby('horse_id')['finish_position'].shift(1).fillna(10)
    clean_df['prev_popularity'] = clean_df.groupby('horse_id')['popularity'].shift(1).fillna(10)
    clean_df['prev_odds'] = clean_df.groupby('horse_id')['odds'].shift(1).fillna(30.0)
    clean_df['last_3f'] = pd.to_numeric(clean_df['last_3f'], errors='coerce')
    clean_df['prev_last_3f'] = clean_df.groupby('horse_id')['last_3f'].shift(1).fillna(36.5)
    clean_df['prev_race_date'] = clean_df.groupby('horse_id')['race_date'].shift(1)
    clean_df['days_since_last'] = (clean_df['race_date'] - clean_df['prev_race_date']).dt.days.fillna(90)
    clean_df['is_debut'] = clean_df.groupby('horse_id').cumcount().apply(lambda x: 1 if x == 0 else 0)

    clean_df['jockey_diff'] = clean_df['is_top3'] - clean_df['horse_prev_top3_rate']
    clean_df = clean_df.sort_values(by=['jockey_id', 'race_date'])
    clean_df['jockey_added_value'] = clean_df.groupby('jockey_id')['jockey_diff'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0.0)

    clean_df['trainer_diff'] = clean_df['is_top3'] - clean_df['horse_prev_top3_rate']
    clean_df = clean_df.sort_values(by=['trainer_id', 'race_date'])
    clean_df['trainer_added_value'] = clean_df.groupby('trainer_id')['trainer_diff'].transform(
        lambda x: x.shift().expanding().mean()).fillna(0.0)

    clean_df['market_implied_win_prob'] = 0.8 / clean_df['odds']
    clean_df['min_odds_in_race'] = clean_df.groupby('race_id')['odds'].transform('min')
    clean_df['odds_ratio_to_fav'] = clean_df['odds'] / (clean_df['min_odds_in_race'] + 1e-5)
    clean_df['pop_odds_mismatch'] = clean_df['popularity'] * 2.5 - np.log(clean_df['odds'] + 1)

    clean_df['surface_code'] = clean_df['surface'].map({'芝': 0, 'ダート': 1, 'ダ': 1}).fillna(0)
    for col in ['impost', 'distance', 'horse_weight', 'horse_number', 'bracket_number']:
        if col in clean_df.columns:
            clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
        else:
            clean_df[col] = 0
    return clean_df


def compare(name, ref, got, cols, key=('race_id', 'horse_number')):
    ref = ref.set_index(list(key)).sort_index()
    got = got.set_index(list(key)).sort_index()
    ok = True
    if len(ref) != len(got):
        print(f"  ✗ 行数が異なる: 参照 {len(ref):,} / モジュール {len(got):,}")
        ok = False
    common = ref.index.intersection(got.index)
    print(f"  共通キー: {len(common):,} 行")
    for c_ref, c_got in cols:
        a, b = ref.loc[common, c_ref], got.loc[common, c_got]
        if pd.api.types.is_numeric_dtype(a):
            diff = ~np.isclose(a.astype(float), b.astype(float), rtol=1e-9, atol=1e-12, equal_nan=True)
        else:
            diff = a.ne(b) & ~(a.isna() & b.isna())
        n = int(diff.sum())
        mark = "✓" if n == 0 else "✗"
        if n:
            ok = False
        print(f"  {mark} {c_ref:28s} 不一致 {n:,} 行")
    return ok



def build_masters(df):
    """C03 セル8 のマスタ生成コードの写し。

    `sort_values('race_date').groupby(...).tail(1)` は同一日に複数レースがあると
    どの行を選ぶかが行順に依存する（騎手の 356/574 が該当）。
    build_features が行順を固定していないと、ここで結果が変わる。
    """
    horse = df.sort_values('race_date').groupby('horse_id').tail(1)[
        ['horse_id', 'horse_name', 'horse_expected_top3_rate', 'finish_position',
         'last_3f', 'odds', 'popularity', 'race_date', 'jockey_id']
    ].rename(columns={'finish_position': 'prev_finish', 'last_3f': 'prev_last_3f',
                      'odds': 'prev_odds', 'popularity': 'prev_popularity',
                      'race_date': 'prev_race_date', 'jockey_id': 'prev_jockey_id'})
    jockey = df.sort_values('race_date').groupby('jockey_id').tail(1)[
        ['jockey_id', 'jockey_name', 'jockey_added_value']]
    trainer = df.sort_values('race_date').groupby('trainer_id').tail(1)[
        ['trainer_id', 'trainer_name', 'trainer_added_value']]
    return {'horse': horse, 'jockey': jockey, 'trainer': trainer}


def compare_masters(ref_df, got_df):
    """マスタCSVの中身が完全に一致するか（行順含む）。"""
    ok = True
    a, b = build_masters(ref_df), build_masters(got_df)
    for k in a:
        same = a[k].reset_index(drop=True).equals(b[k].reset_index(drop=True))
        print(f"  {'✓' if same else '✗'} master_{k:8s} {'一致' if same else '不一致'}"
              f"  ({len(a[k]):,} 行)")
        ok &= same
    return ok


def main():
    races = pd.read_parquet(ROOT / 'data/processed/races.parquet')
    results = pd.read_parquet(ROOT / 'data/processed/results.parquet')

    all_ok = True

    print("=" * 62)
    print("C03 との同値性")
    print("=" * 62)
    ref = reference_c03(races, results)
    got = build_features(races, results, C03_CONFIG)
    cols = [(c, c) for c in [
        'is_top3', 'horse_expected_top3_rate', 'jockey_added_value', 'trainer_added_value',
        'prev_finish', 'prev_last_3f', 'prev_odds', 'prev_popularity', 'days_since_last',
        'is_jockey_changed', 'is_debut', 'surface_encoded', 'year']]
    all_ok &= compare('C03', ref, got, cols)
    print("\n  --- C03 セル8 のマスタ生成（行順依存の退行検知）---")
    all_ok &= compare_masters(ref, got)

    print()
    print("=" * 62)
    print("C04 との同値性")
    print("=" * 62)
    ref4 = reference_c04(races, results)
    got4 = build_features(races, results, C04_CONFIG)
    cols4 = [
        ('is_top3', 'is_top3'), ('is_win', 'is_win'),
        ('horse_prev_top3_rate', 'horse_expected_top3_rate'),
        ('horse_prev_top3_rate', 'horse_prev_top3_rate'),   # 別名が同値であること
        ('horse_prev_win_rate', 'horse_prev_win_rate'),
        ('jockey_added_value', 'jockey_added_value'),
        ('trainer_added_value', 'trainer_added_value'),
        ('prev_finish', 'prev_finish'), ('prev_last_3f', 'prev_last_3f'),
        ('prev_odds', 'prev_odds'), ('prev_popularity', 'prev_popularity'),
        ('days_since_last', 'days_since_last'), ('is_debut', 'is_debut'),
        ('surface_code', 'surface_code'),
        ('market_implied_win_prob', 'market_implied_win_prob'),
        ('odds_ratio_to_fav', 'odds_ratio_to_fav'),
        ('pop_odds_mismatch', 'pop_odds_mismatch'),
        ('impost', 'impost'), ('distance', 'distance'),
        ('horse_weight', 'horse_weight'),
    ]
    all_ok &= compare('C04', ref4, got4, cols4)

    print()
    print("=" * 62)
    print("結果:", "✅ 全一致" if all_ok else "❌ 不一致あり")
    print("=" * 62)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())

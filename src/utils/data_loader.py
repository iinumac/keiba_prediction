"""
データアクセスユーティリティ

GitHubからParquetファイルを読み込み、馬や騎手のデータを取得する
"""

import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict

# GitHub RAW URL
GITHUB_BASE_URL = "https://raw.githubusercontent.com/iinumac/keiba_prediction/main/data/processed"

# キャッシュ用
_races_df: Optional[pd.DataFrame] = None
_results_df: Optional[pd.DataFrame] = None


def load_races(from_github: bool = True, local_path: Optional[Path] = None) -> pd.DataFrame:
    """
    レースデータを読み込み（キャッシュあり）
    
    Args:
        from_github: Trueの場合GitHubから、Falseの場合ローカルから読み込み
        local_path: ローカルのParquetファイルパス
    
    Returns:
        pd.DataFrame: レースデータ
    """
    global _races_df
    
    if _races_df is not None:
        return _races_df
    
    if from_github:
        url = f"{GITHUB_BASE_URL}/races.parquet"
        _races_df = pd.read_parquet(url)
    else:
        if local_path is None:
            local_path = Path(__file__).parent.parent.parent / "data" / "processed" / "races.parquet"
        _races_df = pd.read_parquet(local_path)
    
    return _races_df


def load_results(from_github: bool = True, local_path: Optional[Path] = None) -> pd.DataFrame:
    """
    出走馬データを読み込み（キャッシュあり）
    
    Args:
        from_github: Trueの場合GitHubから、Falseの場合ローカルから読み込み
        local_path: ローカルのParquetファイルパス
    
    Returns:
        pd.DataFrame: 出走馬データ
    """
    global _results_df
    
    if _results_df is not None:
        return _results_df
    
    if from_github:
        url = f"{GITHUB_BASE_URL}/results.parquet"
        _results_df = pd.read_parquet(url)
    else:
        if local_path is None:
            local_path = Path(__file__).parent.parent.parent / "data" / "processed" / "results.parquet"
        _results_df = pd.read_parquet(local_path)
    
    return _results_df


def clear_cache():
    """キャッシュをクリア"""
    global _races_df, _results_df
    _races_df = None
    _results_df = None


def get_horse_history(
    horse_id: str,
    before_date: Optional[str] = None,
    from_github: bool = True
) -> pd.DataFrame:
    """
    馬の過去成績を取得
    
    Args:
        horse_id: 馬ID
        before_date: この日付より前のレースのみ取得（YYYY-MM-DD形式）
        from_github: GitHubから読み込むか
    
    Returns:
        pd.DataFrame: 過去成績（race_date降順）
    """
    results_df = load_results(from_github=from_github)
    
    horse_data = results_df[results_df['horse_id'] == horse_id].copy()
    
    if before_date and 'race_date' in horse_data.columns:
        horse_data = horse_data[horse_data['race_date'] < before_date]
    
    if 'race_date' in horse_data.columns:
        horse_data = horse_data.sort_values('race_date', ascending=False)
    
    return horse_data


def get_jockey_stats(
    jockey_id: str,
    before_date: Optional[str] = None,
    from_github: bool = True
) -> Dict:
    """
    騎手の成績統計を取得
    
    Args:
        jockey_id: 騎手ID
        before_date: この日付より前のデータで集計
        from_github: GitHubから読み込むか
    
    Returns:
        dict: 統計情報
    """
    results_df = load_results(from_github=from_github)
    
    jockey_data = results_df[results_df['jockey_id'] == jockey_id].copy()
    
    if before_date and 'race_date' in jockey_data.columns:
        jockey_data = jockey_data[jockey_data['race_date'] < before_date]
    
    finished = jockey_data[jockey_data['finish_position'].notna()]
    
    if len(finished) == 0:
        return {
            'jockey_id': jockey_id,
            'race_count': 0,
            'win_rate': None,
            'place_rate': None,
        }
    
    return {
        'jockey_id': jockey_id,
        'race_count': len(finished),
        'win_count': int((finished['finish_position'] == 1).sum()),
        'place_count': int((finished['finish_position'] <= 3).sum()),
        'win_rate': float((finished['finish_position'] == 1).sum() / len(finished)),
        'place_rate': float((finished['finish_position'] <= 3).sum() / len(finished)),
    }


def get_trainer_stats(
    trainer_id: str,
    before_date: Optional[str] = None,
    from_github: bool = True
) -> Dict:
    """
    調教師の成績統計を取得
    
    Args:
        trainer_id: 調教師ID
        before_date: この日付より前のデータで集計
        from_github: GitHubから読み込むか
    
    Returns:
        dict: 統計情報
    """
    results_df = load_results(from_github=from_github)
    
    trainer_data = results_df[results_df['trainer_id'] == trainer_id].copy()
    
    if before_date and 'race_date' in trainer_data.columns:
        trainer_data = trainer_data[trainer_data['race_date'] < before_date]
    
    finished = trainer_data[trainer_data['finish_position'].notna()]
    
    if len(finished) == 0:
        return {
            'trainer_id': trainer_id,
            'race_count': 0,
            'win_rate': None,
            'place_rate': None,
        }
    
    return {
        'trainer_id': trainer_id,
        'race_count': len(finished),
        'win_count': int((finished['finish_position'] == 1).sum()),
        'place_count': int((finished['finish_position'] <= 3).sum()),
        'win_rate': float((finished['finish_position'] == 1).sum() / len(finished)),
        'place_rate': float((finished['finish_position'] <= 3).sum() / len(finished)),
    }


def search_horse_by_name(
    name: str,
    from_github: bool = True
) -> pd.DataFrame:
    """
    馬名で検索
    
    Args:
        name: 馬名（部分一致）
        from_github: GitHubから読み込むか
    
    Returns:
        pd.DataFrame: 該当する馬のユニークリスト
    """
    results_df = load_results(from_github=from_github)
    
    matched = results_df[results_df['horse_name'].str.contains(name, na=False)]
    
    if len(matched) == 0:
        return pd.DataFrame(columns=['horse_id', 'horse_name'])
    
    unique_horses = matched[['horse_id', 'horse_name']].drop_duplicates()
    return unique_horses

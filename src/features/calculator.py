"""
特徴量計算モジュール

過去成績データから予測用特徴量を計算する
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


def calculate_horse_features(
    horse_id: str,
    history_df: pd.DataFrame,
    current_race_level_score: int,
    current_race_date: Optional[str] = None
) -> Dict:
    """
    馬の過去成績から特徴量を計算
    
    Args:
        horse_id: 馬ID
        history_df: 過去レース結果のDataFrame
        current_race_level_score: 今回レースのレベルスコア
        current_race_date: 今回レース日（これ以前のレースのみ使用）
    
    Returns:
        dict: 特徴量辞書
    """
    # 該当馬の過去成績を抽出
    horse_history = history_df[history_df['horse_id'] == horse_id].copy()
    
    # 今回レース日より前のレースのみ使用
    if current_race_date and 'race_date' in horse_history.columns:
        horse_history = horse_history[horse_history['race_date'] < current_race_date]
    
    if len(horse_history) == 0:
        return {
            'horse_id': horse_id,
            'race_count': 0,
            'weighted_avg_finish': None,
            'avg_finish': None,
            'win_rate': None,
            'place_rate': None,
            'high_level_count': 0,
            'high_level_best': None,
            'high_level_place_rate': None,
            'level_gap': None,
            'same_level_count': 0,
            'same_level_best': None,
            'same_level_place_rate': None,
        }
    
    features = {
        'horse_id': horse_id,
        'race_count': len(horse_history),
    }
    
    # 着順が記録されているレースのみ
    finished = horse_history[horse_history['finish_position'].notna()].copy()
    
    if len(finished) == 0:
        features.update({
            'weighted_avg_finish': None,
            'avg_finish': None,
            'win_rate': None,
            'place_rate': None,
            'high_level_count': 0,
            'high_level_best': None,
            'high_level_place_rate': None,
            'level_gap': None,
            'same_level_count': 0,
            'same_level_best': None,
            'same_level_place_rate': None,
        })
        return features
    
    # レベル加重平均着順
    if 'level_score' in finished.columns:
        weighted_sum = (finished['finish_position'] * finished['level_score']).sum()
        weight_total = finished['level_score'].sum()
        features['weighted_avg_finish'] = weighted_sum / weight_total if weight_total > 0 else None
    else:
        features['weighted_avg_finish'] = None
    
    # 平均着順
    features['avg_finish'] = finished['finish_position'].mean()
    
    # 勝率・複勝率
    features['win_rate'] = (finished['finish_position'] == 1).sum() / len(finished)
    features['place_rate'] = (finished['finish_position'] <= 3).sum() / len(finished)
    
    # 高レベル（レベルスコア5以上=A以上）での成績
    if 'level_score' in finished.columns:
        high_level = finished[finished['level_score'] >= 5]
        if len(high_level) > 0:
            features['high_level_count'] = len(high_level)
            features['high_level_best'] = int(high_level['finish_position'].min())
            features['high_level_place_rate'] = (high_level['finish_position'] <= 3).sum() / len(high_level)
        else:
            features['high_level_count'] = 0
            features['high_level_best'] = None
            features['high_level_place_rate'] = None
        
        # 今回レースレベルとの差
        avg_level = finished['level_score'].mean()
        features['level_gap'] = current_race_level_score - avg_level
        
        # 同レベルでの成績
        same_level = finished[finished['level_score'] == current_race_level_score]
        if len(same_level) > 0:
            features['same_level_count'] = len(same_level)
            features['same_level_best'] = int(same_level['finish_position'].min())
            features['same_level_place_rate'] = (same_level['finish_position'] <= 3).sum() / len(same_level)
        else:
            features['same_level_count'] = 0
            features['same_level_best'] = None
            features['same_level_place_rate'] = None
    else:
        features['high_level_count'] = 0
        features['high_level_best'] = None
        features['high_level_place_rate'] = None
        features['level_gap'] = None
        features['same_level_count'] = 0
        features['same_level_best'] = None
        features['same_level_place_rate'] = None
    
    return features


def calculate_jockey_features(
    jockey_id: str,
    history_df: pd.DataFrame,
    current_race_date: Optional[str] = None
) -> Dict:
    """
    騎手の過去成績から特徴量を計算
    
    Args:
        jockey_id: 騎手ID
        history_df: 過去レース結果のDataFrame
        current_race_date: 今回レース日
    
    Returns:
        dict: 特徴量辞書
    """
    jockey_history = history_df[history_df['jockey_id'] == jockey_id].copy()
    
    if current_race_date and 'race_date' in jockey_history.columns:
        jockey_history = jockey_history[jockey_history['race_date'] < current_race_date]
    
    if len(jockey_history) == 0:
        return {
            'jockey_id': jockey_id,
            'jockey_race_count': 0,
            'jockey_win_rate': None,
            'jockey_place_rate': None,
        }
    
    finished = jockey_history[jockey_history['finish_position'].notna()]
    
    if len(finished) == 0:
        return {
            'jockey_id': jockey_id,
            'jockey_race_count': len(jockey_history),
            'jockey_win_rate': None,
            'jockey_place_rate': None,
        }
    
    return {
        'jockey_id': jockey_id,
        'jockey_race_count': len(finished),
        'jockey_win_rate': (finished['finish_position'] == 1).sum() / len(finished),
        'jockey_place_rate': (finished['finish_position'] <= 3).sum() / len(finished),
    }


def build_feature_dataset(
    race_entries: pd.DataFrame,
    history_df: pd.DataFrame,
    race_level_score: int,
    race_date: str
) -> pd.DataFrame:
    """
    出馬表から特徴量データセットを構築
    
    Args:
        race_entries: 出馬表DataFrame（horse_id, jockey_idを含む）
        history_df: 過去レース結果のDataFrame
        race_level_score: 今回レースのレベルスコア
        race_date: 今回レース日
    
    Returns:
        pd.DataFrame: 特徴量データセット
    """
    features_list = []
    
    for _, entry in race_entries.iterrows():
        horse_id = entry.get('horse_id')
        jockey_id = entry.get('jockey_id')
        
        # 馬の特徴量
        horse_features = calculate_horse_features(
            horse_id, history_df, race_level_score, race_date
        )
        
        # 騎手の特徴量
        jockey_features = calculate_jockey_features(
            jockey_id, history_df, race_date
        )
        
        # 結合
        combined = {**entry.to_dict(), **horse_features, **jockey_features}
        features_list.append(combined)
    
    return pd.DataFrame(features_list)

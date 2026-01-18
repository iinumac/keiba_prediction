import sys
from pathlib import Path
import pandas as pd
import numpy as np
import warnings
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import pickle

warnings.filterwarnings('ignore')

# 1. 環境設定
PROJECT_ROOT = Path('.')
if str(PROJECT_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / 'src'))

RESULTS_PARQUET = PROJECT_ROOT / 'data' / 'processed' / 'results.parquet'
MODEL_DIR = PROJECT_ROOT / 'models'
MODEL_DIR.mkdir(exist_ok=True)

print(f"データパス: {RESULTS_PARQUET}")

# 2. データ読み込み
results_df = pd.read_parquet(RESULTS_PARQUET)
print(f"出走馬データ数: {len(results_df):,}")

# 3. 前処理・特徴量エンジニアリング
results_df['race_date'] = pd.to_datetime(results_df['race_date'])
results_df['year'] = results_df['race_date'].dt.year
results_df = results_df[results_df['is_finished'] == True].copy()
results_df['jockey_id'] = results_df['jockey_id'].fillna('unknown')
results_df['trainer_id'] = results_df['trainer_id'].fillna('unknown')
results_df = results_df.sort_values(['horse_id', 'race_date']).reset_index(drop=True)

print("前走情報を計算中...")
results_df['prev_finish'] = results_df.groupby('horse_id')['finish_position'].shift(1)
results_df['prev_last_3f'] = results_df.groupby('horse_id')['last_3f'].shift(1)
results_df['prev_odds'] = results_df.groupby('horse_id')['odds'].shift(1)
results_df['prev_race_date'] = results_df.groupby('horse_id')['race_date'].shift(1)
results_df['days_since_last'] = (results_df['race_date'] - results_df['prev_race_date']).dt.days

results_df['prev2_finish'] = results_df.groupby('horse_id')['finish_position'].shift(2)
results_df['prev3_finish'] = results_df.groupby('horse_id')['finish_position'].shift(3)
results_df['prev2_last_3f'] = results_df.groupby('horse_id')['last_3f'].shift(2)
results_df['prev3_last_3f'] = results_df.groupby('horse_id')['last_3f'].shift(3)

results_df['avg_finish_last3'] = results_df[['prev_finish', 'prev2_finish', 'prev3_finish']].mean(axis=1)
results_df['avg_last3f_last3'] = results_df[['prev_last_3f', 'prev2_last_3f', 'prev3_last_3f']].mean(axis=1)

results_df['is_debut'] = results_df['prev_finish'].isna().astype(int)

print("馬の累積統計を計算中...")
results_df['horse_cumulative_races'] = results_df.groupby('horse_id').cumcount()
results_df['_win'] = (results_df.groupby('horse_id')['finish_position'].shift(1) == 1).astype(int)
results_df['_place'] = (results_df.groupby('horse_id')['finish_position'].shift(1) <= 3).astype(int)
results_df['horse_cumulative_wins'] = results_df.groupby('horse_id')['_win'].cumsum()
results_df['horse_cumulative_place'] = results_df.groupby('horse_id')['_place'].cumsum()
results_df['horse_win_rate'] = results_df['horse_cumulative_wins'] / results_df['horse_cumulative_races'].replace(0, np.nan)
results_df['horse_place_rate'] = results_df['horse_cumulative_place'] / results_df['horse_cumulative_races'].replace(0, np.nan)
results_df.drop(columns=['_win', '_place'], inplace=True)

print("騎手・調教師の累積成績を計算中...")
results_df = results_df.sort_values('race_date').reset_index(drop=True)

results_df['jockey_cumulative_races'] = results_df.groupby('jockey_id').cumcount()
results_df['_jwin'] = (results_df.groupby('jockey_id')['finish_position'].shift(1) == 1).astype(int)
results_df['_jplace'] = (results_df.groupby('jockey_id')['finish_position'].shift(1) <= 3).astype(int)
results_df['jockey_cumulative_wins'] = results_df.groupby('jockey_id')['_jwin'].cumsum()
results_df['jockey_cumulative_place'] = results_df.groupby('jockey_id')['_jplace'].cumsum()
results_df['jockey_win_rate'] = results_df['jockey_cumulative_wins'] / results_df['jockey_cumulative_races'].replace(0, np.nan)
results_df['jockey_place_rate'] = results_df['jockey_cumulative_place'] / results_df['jockey_cumulative_races'].replace(0, np.nan)
results_df.drop(columns=['_jwin', '_jplace'], inplace=True)

results_df['trainer_cumulative_races'] = results_df.groupby('trainer_id').cumcount()
results_df['_twin'] = (results_df.groupby('trainer_id')['finish_position'].shift(1) == 1).astype(int)
results_df['_tplace'] = (results_df.groupby('trainer_id')['finish_position'].shift(1) <= 3).astype(int)
results_df['trainer_cumulative_wins'] = results_df.groupby('trainer_id')['_twin'].cumsum()
results_df['trainer_cumulative_place'] = results_df.groupby('trainer_id')['_tplace'].cumsum()
results_df['trainer_win_rate'] = results_df['trainer_cumulative_wins'] / results_df['trainer_cumulative_races'].replace(0, np.nan)
results_df['trainer_place_rate'] = results_df['trainer_cumulative_place'] / results_df['trainer_cumulative_races'].replace(0, np.nan)
results_df.drop(columns=['_twin', '_tplace'], inplace=True)

# 4. データ分割 (フィルタリング追加)
TRAIN_END_YEAR = 2024

print("\n[フィルタリング適用]")
print(f"全データ: {len(results_df):,}")
# 新馬・初出走を除外
results_df = results_df[results_df['is_debut'] == 0].copy()
print(f"既走馬のみ: {len(results_df):,}")

train_df = results_df[results_df['year'] <= TRAIN_END_YEAR].copy()
test_df = results_df[results_df['year'] > TRAIN_END_YEAR].copy()

train_df['surface_encoded'] = train_df['surface'].map({'芝': 0, 'ダート': 1}).fillna(-1)
test_df['surface_encoded'] = test_df['surface'].map({'芝': 0, 'ダート': 1}).fillna(-1)
train_df['target'] = (train_df['finish_position'] <= 3).astype(int)
test_df['target'] = (test_df['finish_position'] <= 3).astype(int)

print(f"Train: {len(train_df):,}")
print(f"Test: {len(test_df):,}")

# 5. モデル学習
FEATURE_COLS_NO_ODDS = [
    'distance', 'surface_encoded', 'level_score',
    'horse_number', 'gate_number', 'impost',
    'prev_finish', 'prev_last_3f', 'days_since_last', 'is_debut',
    'prev2_finish', 'prev3_finish',
    'avg_finish_last3', 'avg_last3f_last3',
    'horse_cumulative_races', 'horse_win_rate', 'horse_place_rate',
    'jockey_cumulative_races', 'jockey_win_rate', 'jockey_place_rate',
    'trainer_cumulative_races', 'trainer_win_rate', 'trainer_place_rate',
]
FEATURE_COLS_WITH_ODDS = FEATURE_COLS_NO_ODDS + ['popularity', 'odds']

for col in FEATURE_COLS_WITH_ODDS:
    if col in train_df.columns:
        train_df[col] = train_df[col].fillna(0)
        test_df[col] = test_df[col].fillna(0)

train_clean = train_df.dropna(subset=['target'])
test_clean = test_df.dropna(subset=['target'])

def train_and_evaluate(train_data, test_data, feature_cols, model_name):
    print(f"\n{'='*50}")
    print(f"🎯 {model_name}")
    print(f"{'='*50}")
    
    X_train = train_data[feature_cols]
    y_train = train_data['target']
    X_test = test_data[feature_cols]
    y_test = test_data['target']
    
    X_tr, X_val, y_tr, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=42)
    
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'learning_rate': 0.05,
        'num_leaves': 15,
        'min_data_in_leaf': 100,
        'feature_fraction': 0.7,
        'bagging_fraction': 0.7,
        'bagging_freq': 5,
        'lambda_l1': 0.1,
        'lambda_l2': 0.1,
        'verbose': -1,
        'random_state': 42,
    }
    
    model = lgb.train(
        params,
        lgb.Dataset(X_tr, label=y_tr),
        num_boost_round=1000,
        valid_sets=[lgb.Dataset(X_tr, label=y_tr), lgb.Dataset(X_val, label=y_val)],
        valid_names=['train', 'valid'],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)] # Log 0 to suppress
    )
    
    y_pred = model.predict(X_test)
    auc = roc_auc_score(y_test, y_pred)
    print(f"\n📊 Test AUC: {auc:.4f}")
    
    test_with_pred = test_data.copy()
    test_with_pred['pred_proba'] = y_pred
    
    # 評価
    # グループ化して計算
    # race_id ごとの処理 (progress barなしで)
    
    # Hit Rate (Top 3)
    def check_hit(g):
        return (g.nlargest(3, 'pred_proba')['finish_position'] <= 3).any()
    
    race_hit = test_with_pred.groupby('race_id').apply(check_hit)
    
    # Return (Win)
    def check_return(g):
        top1 = g.nlargest(1, 'pred_proba').iloc[0]
        if top1['finish_position'] == 1:
            return top1['odds'] * 100
        return 0
        
    returns = test_with_pred.groupby('race_id').apply(check_return)
    return_rate = returns.sum() / (len(returns) * 100) * 100
    
    # Sanrenpuku
    def check_sanren(g):
        return len(set(g.nsmallest(3, 'finish_position')['horse_id']) & 
                   set(g.nlargest(5, 'pred_proba')['horse_id'])) >= 3

    sanren = test_with_pred.groupby('race_id').apply(check_sanren)
    
    return {'auc': auc, 'hit_rate': race_hit.mean(), 'return_rate': return_rate, 'sanren_rate': sanren.mean()}

result_no_odds = train_and_evaluate(train_clean, test_clean, FEATURE_COLS_NO_ODDS, "オッズなしモデル")
result_with_odds = train_and_evaluate(train_clean, test_clean, FEATURE_COLS_WITH_ODDS, "オッズありモデル")

print("\n" + "="*60)
print("📊 モデル比較 (新馬戦除外版)")
print("="*60)
print(pd.DataFrame({
    '指標': ['AUC', '上位3頭的中率', '三連複的中率', '単勝回収率'],
    'オッズなし': [f"{result_no_odds['auc']:.4f}", f"{result_no_odds['hit_rate']:.1%}", 
                   f"{result_no_odds['sanren_rate']:.1%}", f"{result_no_odds['return_rate']:.1f}%"],
    'オッズあり': [f"{result_with_odds['auc']:.4f}", f"{result_with_odds['hit_rate']:.1%}",
                   f"{result_with_odds['sanren_rate']:.1%}", f"{result_with_odds['return_rate']:.1f}%"]
}).to_string(index=False))

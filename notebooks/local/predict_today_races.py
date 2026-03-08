import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import lightgbm as lgb
from bs4 import BeautifulSoup
import re
import warnings

warnings.filterwarnings('ignore')

# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
from utils.data_loader import load_results

DATA_DIR = PROJECT_ROOT / 'data'
MODEL_DIR = PROJECT_ROOT / 'models'
MODEL_NO_ODDS_PATH = MODEL_DIR / 'model_no_odds.pkl'
MODEL_WITH_ODDS_PATH = MODEL_DIR / 'model_with_odds.pkl'
TODAY_DIR = Path('notebooks/local/today')

def parse_jra_html(html_paths):
    """
    Parses JRA HTML files to extract race and horse data.
    """
    races_data = []
    
    for html_path in html_paths:
        if not html_path.exists():
            print(f"File not found: {html_path}")
            continue
            
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            
        # Find all race containers
        race_lis = soup.select('li[id^="syutsuba_"]')
        
        for race_li in race_lis:
            race_info = {}
            
            # Extract basic race info
            race_header = race_li.select_one('.race_header')
            if not race_header:
                continue

            # Race Number
            race_num_img = race_header.select_one('.race_number img')
            if race_num_img:
                race_num_match = re.search(r'(\d+)', race_num_img.get('alt', ''))
                race_info['race_num'] = int(race_num_match.group(1)) if race_num_match else None
            
            # Race Date & Location (from header text or file context - using date line)
            date_div = race_header.select_one('.date_line .date')
            if date_div:
                date_text = date_div.text.strip()
                # Extract date YYYY年MM月DD日
                date_match = re.search(r'(\d+)年(\d+)月(\d+)日', date_text)
                if date_match:
                    race_info['date'] = pd.to_datetime(f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}")
                
                # Venue extraction might need refinement, assuming Nakayama from file inspection
                # "1回中山7日" -> "中山"
                if '中山' in date_text: race_info['venue'] = '中山'
                elif '東京' in date_text: race_info['venue'] = '東京'
                elif '京都' in date_text: race_info['venue'] = '京都'
                elif '阪神' in date_text: race_info['venue'] = '阪神'
                # Add others as needed or default/parse properly
            
            # Course Info
            course_div = race_header.select_one('.type .course')
            if course_div:
                course_text = course_div.text.strip()
                # "1,800メートル（ダート・右）"
                dist_match = re.search(r'([\d,]+)メートル', course_text)
                if dist_match:
                    race_info['distance'] = int(dist_match.group(1).replace(',', ''))
                
                if '芝' in course_text: race_info['surface'] = '芝'
                elif 'ダート' in course_text: race_info['surface'] = 'ダート'
                else: race_info['surface'] = 'Unknown'

            # Horses
            horses = []
            table_rows = race_li.select('table.basic.narrow-xy.striped tbody tr')
            for row in table_rows:
                horse_data = {}
                
                # Gate & Number
                waku_img = row.select_one('.waku img')
                if waku_img:
                    waku_match = re.search(r'枠(\d+)', waku_img.get('alt', ''))
                    horse_data['gate_number'] = int(waku_match.group(1)) if waku_match else None
                
                num_td = row.select_one('.num')
                if num_td:
                    horse_data['horse_number'] = int(re.search(r'\d+', num_td.text).group())
                
                # Horse Name
                horse_a = row.select_one('.horse a')
                if horse_a:
                    horse_data['horse_name'] = horse_a.text.strip()
                
                # Sex & Age "牡3"
                age_td = row.select_one('.age')
                if age_td:
                    age_text = age_td.text.strip()
                    horse_data['sex'] = age_text[0]
                    horse_data['age'] = int(re.search(r'\d+', age_text).group())
                
                # Impost (Weight)
                weight_td = row.select_one('.weight')
                if weight_td:
                    horse_data['impost'] = float(re.search(r'[\d.]+', weight_td.text).group())
                
                # Jockey
                jockey_a = row.select_one('.jockey a')
                if jockey_a:
                    horse_data['jockey_name'] = jockey_a.text.strip().replace(' ', '').replace('　', '')
                
                # Trainer
                trainer_a = row.select_one('.trainer a')
                if trainer_a:
                    horse_data['trainer_name'] = trainer_a.text.strip().replace(' ', '').replace('　', '')
                
                # Odds
                odds_td = row.select_one('.odds')
                if odds_td:
                    odds_text = odds_td.text.strip()
                    try:
                        horse_data['odds'] = float(odds_text)
                    except ValueError:
                        horse_data['odds'] = 0.0 # Default if missing or '---'
                
                # Popularity is usually not in shutuba table until results, or maybe calculated from odds. 
                # We will calculate popularity rank later.
                
                horses.append(horse_data)
            
            race_info['horses'] = horses
            races_data.append(race_info)
            
    return races_data

def load_data_and_create_maps():
    """
    Loads historical data and creates name-to-ID mappings.
    """
    print("Loading historical data from GitHub (online)...")
    df = load_results(from_github=True)
    
    # Create mappings (Latest ID for a name is generally best, or consistent one)
    # Using the most frequent ID for a name to be safe, or just distinct.
    # Actually, JRA names are clean, usually.
    
    # Horse Map
    horse_map = df.sort_values('race_date').groupby('horse_name')['horse_id'].last().to_dict()
    
    # Jockey Map
    jockey_map = df.sort_values('race_date').groupby('jockey_name')['jockey_id'].last().to_dict()
    
    # Trainer Map
    trainer_map = df.sort_values('race_date').groupby('trainer_name')['trainer_id'].last().to_dict()
    
    return df, horse_map, jockey_map, trainer_map


def calculate_features(current_races, historical_df, horse_map, jockey_map, trainer_map):
    """
    Combines current races with historical data to calculate features.
    """
    # Convert current races to DataFrame
    rows = []
    for race in current_races:
        for horse in race['horses']:
            row = horse.copy()
            row['race_id'] = f"TODAY_{race['race_num']}_{race['venue']}" # Temporary ID
            row['race_date'] = race['date']
            row['venue_name'] = race['venue']
            row['race_num'] = race['race_num']
            row['distance'] = race['distance']
            row['surface'] = race['surface']
            # Map IDs
            row['horse_id'] = horse_map.get(row['horse_name'], 'unknown_horse')
            row['jockey_id'] = jockey_map.get(row['jockey_name'], 'unknown_jockey')
            row['trainer_id'] = trainer_map.get(row['trainer_name'], 'unknown_trainer')
            
            # Default values for missing cols to match historical schema if needed
            row['finish_position'] = np.nan
            row['last_3f'] = np.nan
            
            rows.append(row)
            

    today_df = pd.DataFrame(rows)
    
    # Initialize missing columns potentially needed for merge or later steps
    if 'level_score' not in today_df.columns:
        today_df['level_score'] = 0 # Default (or np.nan)
    if 'popularity' not in today_df.columns:
        today_df['popularity'] = np.nan # Will be calculated later

    # Surface encoding
    today_df['surface_encoded'] = today_df['surface'].map({'芝': 0, 'ダート': 1}).fillna(-1)
    
    # Columns required for feature calculation
    required_cols = [
        'horse_id', 'race_date', 'finish_position', 'last_3f', 'odds', 
        'jockey_id', 'trainer_id', 'race_id'
    ]
    
    # Filter historical data
    hist_subset = historical_df[required_cols].copy()
    
    # Combine
    combined_df = pd.concat([hist_subset, today_df[required_cols]], ignore_index=True)
    combined_df['race_date'] = pd.to_datetime(combined_df['race_date'])
    combined_df = combined_df.sort_values(['horse_id', 'race_date']).reset_index(drop=True)
    
    # --- Feature Engineering (Same logic as L01) ---
    print("Calculating features...")
    
    # Lag Features
    combined_df['prev_finish'] = combined_df.groupby('horse_id')['finish_position'].shift(1)
    combined_df['prev_last_3f'] = combined_df.groupby('horse_id')['last_3f'].shift(1)
    combined_df['prev_odds'] = combined_df.groupby('horse_id')['odds'].shift(1)
    combined_df['prev_race_date'] = combined_df.groupby('horse_id')['race_date'].shift(1)
    combined_df['days_since_last'] = (combined_df['race_date'] - combined_df['prev_race_date']).dt.days
    
    combined_df['prev2_finish'] = combined_df.groupby('horse_id')['finish_position'].shift(2)
    combined_df['prev3_finish'] = combined_df.groupby('horse_id')['finish_position'].shift(3)
    combined_df['prev2_last_3f'] = combined_df.groupby('horse_id')['last_3f'].shift(2)
    combined_df['prev3_last_3f'] = combined_df.groupby('horse_id')['last_3f'].shift(3)
    
    combined_df['avg_finish_last3'] = combined_df[['prev_finish', 'prev2_finish', 'prev3_finish']].mean(axis=1)
    combined_df['avg_last3f_last3'] = combined_df[['prev_last_3f', 'prev2_last_3f', 'prev3_last_3f']].mean(axis=1)
    
    combined_df['is_debut'] = combined_df['prev_finish'].isna().astype(int)
    
    # Cumulative Stats
    # Note: excluding the current race from calculation by shifting
    combined_df['horse_cumulative_races'] = combined_df.groupby('horse_id').cumcount()
    combined_df['_win'] = (combined_df.groupby('horse_id')['finish_position'].shift(1) == 1).astype(int)
    combined_df['_place'] = (combined_df.groupby('horse_id')['finish_position'].shift(1) <= 3).astype(int)
    combined_df['horse_cumulative_wins'] = combined_df.groupby('horse_id')['_win'].cumsum()
    combined_df['horse_cumulative_place'] = combined_df.groupby('horse_id')['_place'].cumsum()
    combined_df['horse_win_rate'] = combined_df['horse_cumulative_wins'] / combined_df['horse_cumulative_races'].replace(0, np.nan)
    combined_df['horse_place_rate'] = combined_df['horse_cumulative_place'] / combined_df['horse_cumulative_races'].replace(0, np.nan)
    
    # Check Jockey/Trainer stats - Need global sort by date again to ensure correct order if not already
    combined_df = combined_df.sort_values('race_date').reset_index(drop=True)
    
    # Jockey
    combined_df['jockey_cumulative_races'] = combined_df.groupby('jockey_id').cumcount()
    combined_df['_jwin'] = (combined_df.groupby('jockey_id')['finish_position'].shift(1) == 1).astype(int)
    combined_df['_jplace'] = (combined_df.groupby('jockey_id')['finish_position'].shift(1) <= 3).astype(int)
    combined_df['jockey_cumulative_wins'] = combined_df.groupby('jockey_id')['_jwin'].cumsum()
    combined_df['jockey_cumulative_place'] = combined_df.groupby('jockey_id')['_jplace'].cumsum()
    combined_df['jockey_win_rate'] = combined_df['jockey_cumulative_wins'] / combined_df['jockey_cumulative_races'].replace(0, np.nan)
    combined_df['jockey_place_rate'] = combined_df['jockey_cumulative_place'] / combined_df['jockey_cumulative_races'].replace(0, np.nan)
    
    # Trainer
    combined_df['trainer_cumulative_races'] = combined_df.groupby('trainer_id').cumcount()
    combined_df['_twin'] = (combined_df.groupby('trainer_id')['finish_position'].shift(1) == 1).astype(int)
    combined_df['_tplace'] = (combined_df.groupby('trainer_id')['finish_position'].shift(1) <= 3).astype(int)
    combined_df['trainer_cumulative_wins'] = combined_df.groupby('trainer_id')['_twin'].cumsum()
    combined_df['trainer_cumulative_place'] = combined_df.groupby('trainer_id')['_tplace'].cumsum()
    combined_df['trainer_win_rate'] = combined_df['trainer_cumulative_wins'] / combined_df['trainer_cumulative_races'].replace(0, np.nan)
    combined_df['trainer_place_rate'] = combined_df['trainer_cumulative_place'] / combined_df['trainer_cumulative_races'].replace(0, np.nan)

    # Extract today's rows
    # We can identify them by the race_ids we created (starting with TODAY_)
    today_features = combined_df[combined_df['race_id'].astype(str).str.startswith('TODAY_')].copy()
    
    # Merge back original info (names, gate number, impost, etc) that wasn't in required_cols
    # "today_df" has the full info. We can merge on index if we are careful, or just on horse_id + race_id
    today_features = pd.merge(
        today_features, 
        today_df[['race_id', 'horse_id', 'horse_name', 'horse_number', 'gate_number', 'impost', 'level_score', 'popularity']], 
        on=['race_id', 'horse_id'], 
        how='left'
    )
    
    # Level score might be missing in today_df (not parsed). 
    # If it's a feature, we might need it. The L01 has 'level_score'.
    # In 'today_df', we didn't extract 'level_score' from HTML (it's hard to get directly).
    # We might need to impute or set to a default (e.g. 0 or mean).
    if 'level_score' not in today_features.columns or today_features['level_score'].isna().all():
        today_features['level_score'] = 0 # Default
        
    # Popularity also missing mostly.
    if 'popularity' not in today_features.columns or today_features['popularity'].isna().all():
         # Simple rank by odds if available
        today_features['popularity'] = today_features.groupby('race_id')['odds'].rank(method='min')

    return today_features


def predict_and_display(features_df, model_no_odds, model_with_odds):
    """
    Runs predictions and prints the output. Also saves to report.md.
    """
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
    
    # Fill NAs
    for col in FEATURE_COLS_WITH_ODDS:
        if col in features_df.columns:
            features_df[col] = features_df[col].fillna(0)
        else:
            features_df[col] = 0

    print("Predicting...")
    # Predict
    features_df['pred_no_odds'] = model_no_odds.predict(features_df[FEATURE_COLS_NO_ODDS])
    features_df['pred_with_odds'] = model_with_odds.predict(features_df[FEATURE_COLS_WITH_ODDS])
    
    # Group by race and display
    features_df['race_num'] = features_df['race_id'].apply(lambda x: int(x.split('_')[1]))
    features_df['venue'] = features_df['race_id'].apply(lambda x: x.split('_')[2])
    
    grouped = features_df.groupby(['venue', 'race_num'])
    
    report_lines = []
    report_lines.append("# 本日のレース予想\n")
    
    for (venue, race_num), group in sorted(grouped, key=lambda x: x[0][1]):
        header = f"## {venue} {race_num}R"
        print(f"\n{'='*30}")
        print(f"{venue} {race_num}R")
        print(f"{'='*30}")
        
        report_lines.append(header)
        
        # Top 5 No Odds
        top_no_odds = group.nlargest(5, 'pred_no_odds')
        
        # Top 5 With Odds
        top_with_odds = group.nlargest(5, 'pred_with_odds')
        

        candidates = []
        seen_horses = set()
        
        # Add top 5 from No Odds
        for _, row in top_no_odds.iterrows():
            candidates.append({
                'name': row['horse_name'],
                'num': int(row['horse_number']),
                'model': 'No Odds',
                'rank': 'Top5',
                'prob': row['pred_no_odds'],
                'odds': row['odds']
            })
            seen_horses.add(row['horse_name'])
            
        # Add top 5 from With Odds if not seen
        for _, row in top_with_odds.iterrows():
            if row['horse_name'] not in seen_horses:
                candidates.append({
                    'name': row['horse_name'],
                    'num': int(row['horse_number']),
                    'model': 'With Odds',
                    'rank': 'Top5',
                    'prob': row['pred_with_odds'],
                    'odds': row['odds']
                })
                seen_horses.add(row['horse_name'])
            else:
                for cand in candidates:
                    if cand['name'] == row['horse_name']:
                        cand['model'] = 'Both'
                        cand['prob_odds'] = row['pred_with_odds']

        # Format Output
        print(f"推奨馬 (全{len(candidates)}頭)")
        print(f"{'No':<4} {'馬名':<16} {'モデル':<10} {'オッズ':<6} {'予測スコア(NO)':<12}")
        print("-" * 60)
        
        report_lines.append(f"\n推奨馬 (全{len(candidates)}頭)")
        report_lines.append("| No | 馬名 | モデル | オッズ | 予測スコア(NO) |")
        report_lines.append("|---|---|---|---|---|")
        
        for cand in candidates:
            score = cand['prob']
            print(f"{cand['num']:<4} {cand['name']:<16} {cand['model']:<10} {cand['odds']:<6.1f} {score:.4f}")
            report_lines.append(f"| {cand['num']} | {cand['name']} | {cand['model']} | {cand['odds']:.1f} | {score:.4f} |")
        
        report_lines.append("\n")

    # Save to report.md
    report_path = TODAY_DIR / 'report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"\nReport saved to {report_path}")

def main():
    # 1. Parse HTML
    html_files = [TODAY_DIR / 'shutuba1.html', TODAY_DIR / 'shutuba2.html']
    current_races = parse_jra_html(html_files)
    print(f"Parsed {len(current_races)} races.")
    
    if not current_races:
        print("No races found.")
        return

    # 2. Load Historical Data & Maps
    hist_df, val_horse_map, val_jockey_map, val_trainer_map = load_data_and_create_maps()
    
    # 3. Calculate Features
    features_df = calculate_features(
        current_races, hist_df, 
        val_horse_map, val_jockey_map, val_trainer_map
    )
    
    # 4. Load Models
    print("Loading models...")
    with open(MODEL_NO_ODDS_PATH, 'rb') as f:
        model_no_odds = pickle.load(f)
    with open(MODEL_WITH_ODDS_PATH, 'rb') as f:
        model_with_odds = pickle.load(f)
        
    # 5. Predict & Display
    predict_and_display(features_df, model_no_odds, model_with_odds)

if __name__ == "__main__":
    main()

import os
import sys
import argparse
from pathlib import Path
import re
import pandas as pd
import numpy as np
import pickle
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

# JRAHTMLから情報をパースする処理
def extract_date(soup):
    date_line = soup.find('div', class_='date_line')
    if date_line:
        text = date_line.text
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            return pd.to_datetime(f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}")
    return pd.Timestamp.today()

def extract_level_score(prize_text):
    # prize_text ex: "590" (万円)
    try:
        prize = float(prize_text)
        if prize >= 10000: return 6
        elif prize >= 5000: return 5
        elif prize >= 3000: return 4
        elif prize >= 1500: return 3
        elif prize >= 750: return 2
        else: return 1
    except:
        return 1

def clean_horse_name(name):
    name = re.sub(r'\s+', '', name)
    name = re.sub(r'[▲△☆◇★騎]', '', name)
    return name

def clean_person_name(name):
    name = re.sub(r'\s+', '', name)
    name = re.sub(r'[▲△☆◇★騎]', '', name)
    name = re.sub(r'^[A-Z]\.', '', name)
    return name[:4]

def parse_html(html_path):
    with open(html_path, 'rb') as f:
        raw = f.read()
    try:
        html = raw.decode('utf-8')
    except UnicodeDecodeError:
        html = raw.decode('Shift_JIS', errors='ignore')

    soup = BeautifulSoup(html, 'html.parser')
    race_date = extract_date(soup)
    
    races = []
    tables = soup.find_all('table', class_='striped')
    print(f"[DEBUG] found tables: {len(tables)}")
    
    for table in tables:
        li_parent = table.find_parent('li')
        if li_parent and 'id' in li_parent.attrs:
            race_id_str = li_parent['id']
            race_num = int(race_id_str.replace('syutsuba_', '').replace('R', ''))
        else:
            race_num = 1
            
        context = li_parent if li_parent else table.parent
        name_node = context.find(class_='race_name')
        race_name = name_node.text.strip() if name_node else ''
        
        course_node = context.find(class_='course')
        course_text = course_node.text if course_node else ''
        
        # 距離と芝/ダート
        distance = 1200
        m_dist = re.search(r'([\d,]+)メートル', course_text)
        if m_dist:
            distance = int(m_dist.group(1).replace(',', ''))
            
        surface_encoded = 0 if '芝' in course_text else 1 # ダート=1
        
        # 賞金からレベルスコア
        level_score = 1
        prize_node = context.find('ul', class_='prize')
        if prize_node:
            first_prize = prize_node.find('li')
            if first_prize:
                num_node = first_prize.find(class_='num')
                if num_node:
                    level_score = extract_level_score(num_node.text.replace(',', ''))
            
        horses = []
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) < 9:
                print(f"[DEBUG] Row has less than 9 columns: {len(cols)}")
                continue
            
            # 馬番
            horse_number_txt = cols[1].text.strip()
            if horse_number_txt == '除外' or horse_number_txt == '取消':
                continue
            horse_number = int(horse_number_txt)
            
            # 馬IDと名前
            a_tag = cols[2].find('a')
            horse_name = clean_horse_name(cols[2].text)
            horse_id = None
            if a_tag and a_tag.get('href'):
                m_id = re.search(r'pw01dud00(\d+)', a_tag.get('href'))
                if m_id:
                    horse_id = m_id.group(1)

            if not horse_id:
                continue
                
            # 斤量
            impost_txt = re.search(r'([\d\.]+)', cols[5].text)
            impost = float(impost_txt.group(1)) if impost_txt else 55.0
            
            # 騎手、調教師
            jockey_name = clean_person_name(cols[6].text)
            trainer_name = clean_person_name(cols[7].text)
            
            # オッズ
            odds_txt = cols[8].text.strip()
            if odds_txt in ['除外', '取消', '***']:
                continue # オッズがない馬は予測不能とするか、別途処理
            odds = float(odds_txt)
            
            horses.append({
                'race_num': race_num,
                'race_name': race_name,
                'distance': distance,
                'surface_encoded': surface_encoded,
                'level_score': level_score,
                'horse_number': horse_number,
                'horse_id': str(horse_id),
                'horse_name': horse_name,
                'impost': impost,
                'jockey_name': jockey_name,
                'trainer_name': trainer_name,
                'odds': odds,
                'race_date': race_date
            })
            
        if horses:
            # 人気順を算出（オッズの昇順）
            horses.sort(key=lambda x: x['odds'])
            for rank, h in enumerate(horses, 1):
                h['popularity'] = rank
            # 元の並びに戻す（オプション）
            horses.sort(key=lambda x: x['horse_number'])
            races.extend(horses)
            
    return pd.DataFrame(races)

def main(html_path):
    print(f"📖 HTML情報の読み込み: {html_path}")
    df_html = parse_html(html_path)
    if df_html.empty:
        print("出走データが見つかりませんでした。")
        return
        
    print(f"📦 マスターデータの読み込み...")
    master_horse = pd.read_csv(PROJECT_ROOT / 'data' / 'processed' / 'master_horse.csv', dtype={'horse_id': str, 'prev_jockey_id': str})
    master_jockey = pd.read_csv(PROJECT_ROOT / 'data' / 'processed' / 'master_jockey.csv', dtype={'jockey_id': str})
    master_trainer = pd.read_csv(PROJECT_ROOT / 'data' / 'processed' / 'master_trainer.csv', dtype={'trainer_id': str})
    
    # 欠損補完用
    global_top3_rate = master_horse['horse_expected_top3_rate'].mean()
    
    # 結合処理
    # 馬情報
    master_horse['prev_race_date'] = pd.to_datetime(master_horse['prev_race_date'])
    cols_to_use = ['horse_id', 'horse_expected_top3_rate', 'prev_finish', 'prev_last_3f', 'prev_race_date', 'prev_jockey_id']
    df = pd.merge(df_html, master_horse[cols_to_use], on='horse_id', how='left')
    
    df['horse_expected_top3_rate'] = df['horse_expected_top3_rate'].fillna(global_top3_rate)
    df['days_since_last'] = (df['race_date'] - df['prev_race_date']).dt.days
    df['days_since_last'] = df['days_since_last'].fillna(180) # 適当な初期値
    
    # 騎手情報、調教師情報（名前ベースで結合）
    # マスター側も一応cleanするが、原則そのまま。
    master_jockey['jockey_name_clean'] = master_jockey['jockey_name'].apply(clean_person_name)
    master_trainer['trainer_name_clean'] = master_trainer['trainer_name'].apply(clean_person_name)
    
    df = pd.merge(df, master_jockey[['jockey_name_clean', 'jockey_added_value', 'jockey_id']], 
                  left_on='jockey_name', right_on='jockey_name_clean', how='left')
    df['jockey_added_value'] = df['jockey_added_value'].fillna(0)
    
    df = pd.merge(df, master_trainer[['trainer_name_clean', 'trainer_added_value']], 
                  left_on='trainer_name', right_on='trainer_name_clean', how='left')
    df['trainer_added_value'] = df['trainer_added_value'].fillna(0)
    
    # 乗替フラグ（名前から引いた jocky_id != prev_jockey_id）
    df['is_jockey_changed'] = (df['jockey_id'] != df['prev_jockey_id']).astype(int)
    # 昔の情報がない場合は乗り替わりなし(0)とする
    df.loc[df['prev_jockey_id'].isna(), 'is_jockey_changed'] = 0

    print("🧠 AIモデル推論中...")
    model_with_odds_path = PROJECT_ROOT / 'models' / 'model_with_odds.pkl'
    model_no_odds_path = PROJECT_ROOT / 'models' / 'model_no_odds.pkl'
    
    with open(model_with_odds_path, 'rb') as f:
        model_with_odds = pickle.load(f)
    with open(model_no_odds_path, 'rb') as f:
        model_no_odds = pickle.load(f)
        
    # オッズありの特徴量
    features_with_odds = ['distance', 'surface_encoded', 'level_score', 'impost', 
                          'horse_expected_top3_rate', 'jockey_added_value', 'trainer_added_value', 
                          'prev_finish', 'prev_last_3f', 'days_since_last', 'is_jockey_changed', 
                          'popularity', 'odds']
                          
    # オッズなしの特徴量
    features_no_odds = ['distance', 'surface_encoded', 'level_score', 'impost', 
                        'horse_expected_top3_rate', 'jockey_added_value', 'trainer_added_value', 
                        'prev_finish', 'prev_last_3f', 'days_since_last', 'is_jockey_changed']
                
    X_with_odds = df[features_with_odds].copy()
    X_no_odds = df[features_no_odds].copy()
    
    for X in [X_with_odds, X_no_odds]:
        X['prev_finish'] = X['prev_finish'].fillna(0)
        X['prev_last_3f'] = X['prev_last_3f'].fillna(0)
    
    df['score_with_odds'] = model_with_odds.predict(X_with_odds)
    df['score_no_odds'] = model_no_odds.predict(X_no_odds)
    
    # 総合スコア（例えばオッズなしモデルのスコアをベースに、オッズありも少し加味するなどできますが、
    # ここでは「オッズなしモデル」のスコアでソートして、オッズに頼らない実力評価をメインに見せます）
    df['pred_score'] = df['score_no_odds']
    
    # 結果表示
    for r_num, grp in df.groupby('race_num'):
        race_name = grp['race_name'].iloc[0]
        print(f"\\n{'='*40}")
        print(f"【{r_num}R】{race_name}")
        print(f"{'='*40}")
        
        # オッズなしモデルのスコアで降順ソート
        res = grp.sort_values('pred_score', ascending=False)
        print(f"{'馬番':>2} | {'印':<1} | {'純粋実力スコア':>8} | {'オッズ込スコア':>8} | {'オッズ':>5} | {'馬名':<15} | {'騎手':<8}")
        print("-" * 75)
        
        for i, (_, row) in enumerate(res.iterrows()):
            mark = "◎" if i==0 else "○" if i==1 else "▲" if i==2 else "△" if i<5 else "  "
            jname = clean_person_name(row['jockey_name'])
            
            # 純粋実力スコア（オッズなし）は高いのに、オッズが高い（人気がない）馬は「穴」として表示
            value_mark = "🔥" if (i < 5 and row['odds'] > 10.0) else "  "
            
            print(f"{int(row['horse_number']):>2} | {mark:<1} | {row['score_no_odds']:>8.4f}{value_mark} | {row['score_with_odds']:>8.4f} | {row['odds']:>5.1f} | {row['horse_name']:<15} | {jname:<8}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('html_path', help="JRA当日の出馬表HTMLファイルパス")
    args = parser.parse_args()
    main(args.html_path)

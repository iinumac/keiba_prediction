"""
HTMLパーサーモジュール

netkeibaのレース結果HTMLをパースして構造化データを抽出する
"""

import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple


def classify_race_level(prize_money: float) -> Tuple[str, int]:
    """
    1着賞金からレースレベルを分類
    
    Args:
        prize_money: 1着賞金（万円）
    
    Returns:
        (level, score): レベル（S/A/B/C/D/E）とスコア（6-1）
    """
    if prize_money >= 10000:
        return 'S', 6  # G1
    elif prize_money >= 5000:
        return 'A', 5  # G2
    elif prize_money >= 3000:
        return 'B', 4  # G3, リステッド
    elif prize_money >= 1500:
        return 'C', 3  # オープン, 3勝クラス
    elif prize_money >= 750:
        return 'D', 2  # 2勝, 1勝クラス
    else:
        return 'E', 1  # 新馬, 未勝利


def parse_race_html(html_path: Path) -> Dict:
    """
    レースHTMLをパースして構造化データを抽出
    
    Args:
        html_path: HTMLファイルパス
    
    Returns:
        dict: {
            'race_info': レース情報の辞書,
            'horses': 出走馬リスト
        }
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    race_id = Path(html_path).stem
    race_info = {'race_id': race_id}
    
    # レース詳細
    race_data = soup.find('dl', class_='racedata')
    if race_data:
        h1 = race_data.find('h1')
        race_info['race_name'] = h1.text.strip() if h1 else ''
        
        span = race_data.find('span')
        if span:
            info_text = span.text.strip()
            
            # 距離・コース
            match = re.search(r'(芝|ダート)(右|左)?(外)?(内)?(直)?(\\d+)m', info_text)
            if match:
                race_info['surface'] = match.group(1)
                race_info['direction'] = match.group(2) or ''
                race_info['course_type'] = match.group(3) or match.group(4) or match.group(5) or ''
                race_info['distance'] = int(match.group(6))
            
            # 天候
            weather_match = re.search(r'天候 : (\\S+)', info_text)
            if weather_match:
                race_info['weather'] = weather_match.group(1)
            
            # 馬場状態
            condition_match = re.search(r'(芝|ダート) : (\\S+)', info_text)
            if condition_match:
                race_info['track_condition'] = condition_match.group(2)
    
    # 日付
    date_elem = soup.find('p', class_='smalltxt')
    if date_elem:
        date_match = re.search(r'(\\d{4})年(\\d{2})月(\\d{2})日', date_elem.text)
        if date_match:
            race_info['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    
    # 出走馬情報
    horses = []
    result_table = soup.find('table', class_='race_table_01')
    
    if result_table:
        for row in result_table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if len(cells) < 10:
                continue
            
            horse = {'race_id': race_id}
            
            # 着順
            finish = cells[0].text.strip()
            horse['finish_position'] = int(finish) if finish.isdigit() else None
            
            # 枠番・馬番
            gate = cells[1].text.strip()
            horse['gate_number'] = int(gate) if gate.isdigit() else None
            
            num = cells[2].text.strip()
            horse['horse_number'] = int(num) if num.isdigit() else None
            
            # 馬名・馬ID
            horse_link = cells[3].find('a')
            if horse_link:
                horse['horse_name'] = horse_link.text.strip()
                href = horse_link.get('href', '')
                match = re.search(r'/horse/(\\d+)/', href)
                if match:
                    horse['horse_id'] = match.group(1)
            
            # 性齢
            sex_age = cells[4].text.strip()
            if sex_age:
                horse['sex'] = sex_age[0] if sex_age else ''
                horse['age'] = int(sex_age[1:]) if len(sex_age) > 1 and sex_age[1:].isdigit() else None
            
            # 斤量
            try:
                horse['weight'] = float(cells[5].text.strip())
            except ValueError:
                horse['weight'] = None
            
            # 騎手
            jockey_link = cells[6].find('a')
            if jockey_link:
                horse['jockey_name'] = jockey_link.text.strip()
                href = jockey_link.get('href', '')
                match = re.search(r'/jockey/result/recent/(\\d+)/', href)
                if match:
                    horse['jockey_id'] = match.group(1)
            
            # タイム
            horse['time'] = cells[7].text.strip()
            
            # 着差
            horse['margin'] = cells[8].text.strip()
            
            # 賞金（最後から1つ目のセル）
            prize_text = cells[-1].text.strip()
            try:
                horse['prize_money'] = float(prize_text)
            except ValueError:
                horse['prize_money'] = 0.0
            
            horses.append(horse)
    
    # レースレベルを1着賞金から判定
    if horses:
        first_place = [h for h in horses if h.get('finish_position') == 1]
        if first_place:
            first_prize = first_place[0].get('prize_money', 0)
            race_info['first_prize'] = first_prize
            level, score = classify_race_level(first_prize)
            race_info['race_level'] = level
            race_info['level_score'] = score
    
    return {'race_info': race_info, 'horses': horses}


def parse_multiple_html(html_dir: Path, years: Optional[List[int]] = None) -> Tuple[List[Dict], List[Dict]]:
    """
    複数HTMLファイルを一括パース
    
    Args:
        html_dir: HTMLディレクトリ
        years: 対象年リスト（Noneで全年）
    
    Returns:
        (race_list, horse_list): レース情報リストと馬情報リスト
    """
    race_list = []
    horse_list = []
    
    if years is None:
        year_dirs = sorted(html_dir.glob('*'))
    else:
        year_dirs = [html_dir / str(y) for y in years if (html_dir / str(y)).exists()]
    
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue
        
        for html_file in sorted(year_dir.glob('*.html')):
            try:
                result = parse_race_html(html_file)
                race_list.append(result['race_info'])
                
                # 各馬にレースレベル情報を追加
                for horse in result['horses']:
                    horse['race_level'] = result['race_info'].get('race_level')
                    horse['level_score'] = result['race_info'].get('level_score')
                    horse['race_date'] = result['race_info'].get('date')
                    horse_list.append(horse)
            except Exception as e:
                print(f"Error parsing {html_file}: {e}")
    
    return race_list, horse_list

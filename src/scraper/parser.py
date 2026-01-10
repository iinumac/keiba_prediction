"""
HTMLパーサーモジュール（拡張版）

netkeibaのレース結果HTMLをパースして全データを抽出する
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


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """
    タイム文字列を秒数に変換
    
    Args:
        time_str: "1:08.8" 形式のタイム
    
    Returns:
        秒数（float）または None
    """
    if not time_str:
        return None
    
    try:
        match = re.match(r'(\d+):(\d+)\.(\d+)', time_str)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            decimals = int(match.group(3))
            return minutes * 60 + seconds + decimals / 10
    except:
        pass
    
    return None


def parse_horse_weight(weight_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    馬体重文字列をパース
    
    Args:
        weight_str: "462(-2)" 形式
    
    Returns:
        (体重, 増減) のタプル
    """
    if not weight_str:
        return None, None
    
    try:
        match = re.match(r'(\d+)\(([\+\-]?\d+)\)', weight_str.strip())
        if match:
            weight = int(match.group(1))
            change = int(match.group(2))
            return weight, change
    except:
        pass
    
    return None, None


def parse_passing_order(passing_str: str) -> Optional[List[int]]:
    """
    通過順をパース
    
    Args:
        passing_str: "1-1" や "3-3-2-1" 形式
    
    Returns:
        通過順リスト
    """
    if not passing_str:
        return None
    
    try:
        parts = passing_str.strip().split('-')
        return [int(p) for p in parts if p.isdigit()]
    except:
        return None


def parse_race_html_full(html_path: Path) -> Dict:
    """
    レースHTMLをパースして全データを抽出
    
    Args:
        html_path: HTMLファイルパス
    
    Returns:
        dict: {
            'race_info': レース情報,
            'horses': 出走馬リスト
        }
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    race_id = Path(html_path).stem
    
    # ============ レース情報 ============
    race_info = {
        'race_id': race_id,
        'venue_code': race_id[4:6] if len(race_id) >= 6 else None,  # 競馬場コード
        'kaisai': race_id[6:8] if len(race_id) >= 8 else None,     # 開催回
        'day': race_id[8:10] if len(race_id) >= 10 else None,       # 開催日
        'race_num': race_id[10:12] if len(race_id) >= 12 else None, # レース番号
    }
    
    # 競馬場名マッピング
    venue_map = {
        '01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京',
        '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉'
    }
    race_info['venue_name'] = venue_map.get(race_info['venue_code'], '')
    
    # レース名・詳細
    race_data = soup.find('dl', class_='racedata')
    if race_data:
        h1 = race_data.find('h1')
        race_info['race_name'] = h1.text.strip() if h1 else ''
        
        span = race_data.find('span')
        if span:
            info_text = span.text.strip()
            
            # 距離・コース
            match = re.search(r'(芝|ダート)(右|左)?(外|内)?(直)?(\\d+)m', info_text)
            if match:
                race_info['surface'] = match.group(1)
                race_info['direction'] = match.group(2) or ''
                race_info['course_type'] = match.group(3) or match.group(4) or ''
                race_info['distance'] = int(match.group(5))
            
            # 天候
            weather_match = re.search(r'天候 : (\\S+)', info_text)
            race_info['weather'] = weather_match.group(1) if weather_match else ''
            
            # 馬場状態
            condition_match = re.search(r'(芝|ダート) : (\\S+)', info_text)
            race_info['track_condition'] = condition_match.group(2) if condition_match else ''
            
            # 発走時刻
            time_match = re.search(r'発走 : (\\d+:\\d+)', info_text)
            race_info['start_time'] = time_match.group(1) if time_match else ''
    
    # 日付・詳細情報
    date_elem = soup.find('p', class_='smalltxt')
    if date_elem:
        date_text = date_elem.text
        
        date_match = re.search(r'(\\d{4})年(\\d{2})月(\\d{2})日', date_text)
        if date_match:
            race_info['date'] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            race_info['year'] = int(date_match.group(1))
            race_info['month'] = int(date_match.group(2))
        
        # クラス情報を抽出
        race_info['class_info'] = date_text.strip()
    
    # ============ 出走馬情報 ============
    horses = []
    result_table = soup.find('table', class_='race_table_01')
    
    if result_table:
        rows = result_table.find_all('tr')[1:]  # ヘッダースキップ
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 10:
                continue
            
            horse = {'race_id': race_id}
            
            # 基本情報のセルインデックス
            # 0:着順, 1:枠番, 2:馬番, 3:馬名, 4:性齢, 5:斤量, 6:騎手, 7:タイム, 8:着差
            
            # 着順
            finish = cells[0].text.strip()
            horse['finish_position'] = int(finish) if finish.isdigit() else None
            horse['is_finished'] = finish.isdigit()
            horse['dnf_reason'] = finish if not finish.isdigit() else None  # 中止, 除外 等
            
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
                horse['horse_id'] = match.group(1) if match else None
            
            # 性齢
            sex_age = cells[4].text.strip()
            if sex_age:
                horse['sex'] = sex_age[0] if sex_age else ''
                horse['age'] = int(sex_age[1:]) if len(sex_age) > 1 and sex_age[1:].isdigit() else None
            
            # 斤量
            try:
                horse['impost'] = float(cells[5].text.strip())
            except ValueError:
                horse['impost'] = None
            
            # 騎手
            jockey_link = cells[6].find('a')
            if jockey_link:
                horse['jockey_name'] = jockey_link.text.strip()
                href = jockey_link.get('href', '')
                match = re.search(r'/jockey/result/recent/(\\d+)/', href)
                horse['jockey_id'] = match.group(1) if match else None
            
            # タイム
            time_str = cells[7].text.strip()
            horse['time_str'] = time_str
            horse['time_seconds'] = parse_time_to_seconds(time_str)
            
            # 着差
            horse['margin'] = cells[8].text.strip()
            
            # diary_snap_cut 内の追加データを探す
            # 通過順、上がり3F はセル内の diary_snap_cut タグの中にある
            snap_cut = row.find('diary_snap_cut')
            if snap_cut:
                snap_cells = snap_cut.find_all('td')
                for sc in snap_cells:
                    text = sc.text.strip()
                    # 通過順（例: "1-1", "3-3-2"）
                    if '-' in text and all(p.isdigit() for p in text.split('-')):
                        horse['passing_order'] = text
                        passing_list = parse_passing_order(text)
                        if passing_list:
                            horse['first_corner'] = passing_list[0] if len(passing_list) > 0 else None
                            horse['last_corner'] = passing_list[-1] if len(passing_list) > 0 else None
                    # 上がり3F（例: "33.9"）
                    elif re.match(r'^\\d+\\.\\d+$', text):
                        try:
                            horse['last_3f'] = float(text)
                        except:
                            pass
            
            # オッズ・人気（diary_snap_cut外のセルから）
            # セルの順序が異なる可能性があるため、クラス名で判定
            for cell in cells:
                text = cell.text.strip()
                classes = cell.get('class', [])
                
                # 単勝オッズ
                if 'txt_r' in classes and re.match(r'^\\d+\\.\\d+$', text):
                    try:
                        if 'odds' not in horse:
                            horse['odds'] = float(text)
                    except:
                        pass
                
                # 人気
                if any('ml' in c for c in classes):
                    span = cell.find('span')
                    if span and span.text.strip().isdigit():
                        pop = int(span.text.strip())
                        if 1 <= pop <= 18:
                            horse['popularity'] = pop
            
            # 馬体重（例: "462(-2)"）
            for cell in cells:
                text = cell.text.strip()
                if re.match(r'^\\d+\\([\\+\\-]?\\d+\\)$', text):
                    weight, change = parse_horse_weight(text)
                    horse['horse_weight'] = weight
                    horse['weight_change'] = change
                    break
            
            # 調教師
            trainer_cell = None
            for cell in cells:
                if '[東]' in cell.text or '[西]' in cell.text:
                    trainer_cell = cell
                    break
            
            if trainer_cell:
                trainer_link = trainer_cell.find('a')
                if trainer_link:
                    horse['trainer_name'] = trainer_link.text.strip()
                    href = trainer_link.get('href', '')
                    match = re.search(r'/trainer/result/recent/(\\d+)/', href)
                    horse['trainer_id'] = match.group(1) if match else None
                
                horse['trainer_region'] = '東' if '[東]' in trainer_cell.text else '西'
            
            # 馬主
            for cell in cells:
                owner_link = cell.find('a', href=re.compile(r'/owner/'))
                if owner_link:
                    horse['owner_name'] = owner_link.text.strip()
                    href = owner_link.get('href', '')
                    match = re.search(r'/owner/result/recent/(\\d+)/', href)
                    horse['owner_id'] = match.group(1) if match else None
                    break
            
            # 賞金（最後のセル）
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
        
        # 出走頭数
        race_info['horse_count'] = len(horses)
    
    return {'race_info': race_info, 'horses': horses}


def parse_multiple_html_full(
    html_dir: Path,
    years: Optional[List[int]] = None,
    progress_callback=None
) -> Tuple[List[Dict], List[Dict]]:
    """
    複数HTMLファイルを一括パース（全データ抽出版）
    
    Args:
        html_dir: HTMLディレクトリ
        years: 対象年リスト（Noneで全年）
        progress_callback: 進捗コールバック関数
    
    Returns:
        (race_list, horse_list): レース情報リストと馬情報リスト
    """
    race_list = []
    horse_list = []
    
    if years is None:
        year_dirs = sorted([d for d in html_dir.glob('*') if d.is_dir()])
    else:
        year_dirs = [html_dir / str(y) for y in years if (html_dir / str(y)).exists()]
    
    total_files = sum(len(list(d.glob('*.html'))) for d in year_dirs if d.is_dir())
    processed = 0
    
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue
        
        for html_file in sorted(year_dir.glob('*.html')):
            try:
                result = parse_race_html_full(html_file)
                race_list.append(result['race_info'])
                
                # 各馬にレース情報を追加
                for horse in result['horses']:
                    horse['race_level'] = result['race_info'].get('race_level')
                    horse['level_score'] = result['race_info'].get('level_score')
                    horse['race_date'] = result['race_info'].get('date')
                    horse['venue_code'] = result['race_info'].get('venue_code')
                    horse['venue_name'] = result['race_info'].get('venue_name')
                    horse['distance'] = result['race_info'].get('distance')
                    horse['surface'] = result['race_info'].get('surface')
                    horse['track_condition'] = result['race_info'].get('track_condition')
                    horse_list.append(horse)
                
                processed += 1
                if progress_callback and processed % 1000 == 0:
                    progress_callback(processed, total_files)
                    
            except Exception as e:
                print(f"Error parsing {html_file}: {e}")
    
    if progress_callback:
        progress_callback(processed, total_files)
    
    return race_list, horse_list


# 後方互換性のためのエイリアス
parse_race_html = parse_race_html_full
parse_multiple_html = parse_multiple_html_full

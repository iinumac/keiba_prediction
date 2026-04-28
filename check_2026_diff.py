#!/usr/bin/env python3
"""
HTMLとParquetの差分を race_id 集合ベースで詳細にチェックするスクリプト

注意: race_id は年・日付を表すIDではないため、
  - HTMLディレクトリ名 (= race_id[:4])
  - Parquetの year 列 (= 実レース日から抽出した年)
は一致しない場合がある。よって差分は race_id の集合演算で行う。
"""
import pandas as pd
from pathlib import Path

HTML_DIR = Path('data/raceHTML')
RACES_PARQUET = Path('data/processed/races.parquet')

print("=" * 60)
print("HTML / Parquet データ整合性チェック (race_id 集合ベース)")
print("=" * 60)

# ---- 全HTML race_id 収集（全ディレクトリ横断） ----
html_race_ids = set()
html_dir_counts = {}
if HTML_DIR.exists():
    for year_dir in sorted([d for d in HTML_DIR.glob('*') if d.is_dir()]):
        ids = {f.stem for f in year_dir.glob('*.html')}
        html_dir_counts[year_dir.name] = len(ids)
        html_race_ids |= ids
    print(f"\n📁 HTML race_id 総数: {len(html_race_ids):,}")
    print("   ディレクトリ別件数 (参考: race_id[:4] 単位):")
    for d, c in sorted(html_dir_counts.items()):
        print(f"      {d}/: {c:,} 件")
else:
    print(f"\n⚠️ HTMLディレクトリが見つかりません: {HTML_DIR}")

# ---- Parquet race_id 収集 ----
parquet_race_ids = set()
df = None
if RACES_PARQUET.exists():
    try:
        df = pd.read_parquet(RACES_PARQUET)
        parquet_race_ids = set(df['race_id'].astype(str).tolist())
        print(f"\n📊 Parquet race_id 総数: {len(parquet_race_ids):,}")
        if 'year' in df.columns:
            print("   year列別件数 (実レース日から抽出した年):")
            for y, c in sorted(df.groupby('year').size().to_dict().items()):
                print(f"      year={y}: {c:,} 件")
    except Exception as e:
        print(f"\n❌ Parquet読み込みエラー: {e}")
else:
    print(f"\n⚠️ Parquetファイルが見つかりません: {RACES_PARQUET}")

# ---- 集合演算で差分判定 ----
print("\n" + "=" * 60)
print("差分分析 (race_id レベル)")
print("=" * 60)

only_in_html = html_race_ids - parquet_race_ids
only_in_parquet = parquet_race_ids - html_race_ids
both = html_race_ids & parquet_race_ids

if only_in_html:
    print(f"\n✅ HTMLにのみ存在（新規取込対象）: {len(only_in_html):,} 件")
    print("   サンプル（最大10件）:")
    for rid in sorted(only_in_html)[:10]:
        print(f"     - {rid}")
    if len(only_in_html) > 10:
        print(f"     ... 他 {len(only_in_html) - 10} 件")
else:
    print(f"\n✅ HTMLにのみ存在: 0 件（新規データなし）")

if only_in_parquet:
    print(f"\n⚠️ Parquetにのみ存在（HTML無し）: {len(only_in_parquet):,} 件")
    print("   サンプル（最大10件）:")
    for rid in sorted(only_in_parquet)[:10]:
        print(f"     - {rid}")
    if len(only_in_parquet) > 10:
        print(f"     ... 他 {len(only_in_parquet) - 10} 件")
else:
    print(f"\n✅ Parquetにのみ存在: 0 件")

print(f"\n📊 両方に存在: {len(both):,} 件")

print("\n" + "=" * 60)
print("結論")
print("=" * 60)

if only_in_html:
    print(f"✅ {len(only_in_html):,} 件の新規データがあります")
    print("   → incrementalモードで追加されます")
elif only_in_parquet:
    print(f"⚠️ ParquetがHTMLより {len(only_in_parquet):,} 件多いです")
    print("   → HTMLが削除された / 別ソース由来の可能性")
    print("   → 整合性を保つには MODE='full' で再パース")
else:
    print("✅ HTMLとParquetが完全一致")
    print("   → 新規データはありません")

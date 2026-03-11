#!/usr/bin/env python3
"""
2026年のHTMLとParquetの差分を詳細にチェックするスクリプト
"""
import pandas as pd
from pathlib import Path

# パス設定
HTML_DIR = Path('data/raceHTML/2026')
RACES_PARQUET = Path('data/processed/races.parquet')

print("=" * 60)
print("2026年データの詳細チェック")
print("=" * 60)

# HTMLファイルのrace_idリスト
html_race_ids = set()
if HTML_DIR.exists():
    html_files = sorted(HTML_DIR.glob('*.html'))
    html_race_ids = {f.stem for f in html_files}
    print(f"\n📁 HTMLファイル数: {len(html_race_ids)}")
    print(f"   最初のrace_id: {sorted(html_race_ids)[0] if html_race_ids else 'なし'}")
    print(f"   最後のrace_id: {sorted(html_race_ids)[-1] if html_race_ids else 'なし'}")
else:
    print(f"\n⚠️ HTMLディレクトリが見つかりません: {HTML_DIR}")

# Parquetファイルのrace_idリスト（2026年のみ）
parquet_race_ids = set()
if RACES_PARQUET.exists():
    try:
        df = pd.read_parquet(RACES_PARQUET)
        df_2026 = df[df['year'] == 2026]
        parquet_race_ids = set(df_2026['race_id'].astype(str).tolist())
        print(f"\n📊 Parquetの2026年レース数: {len(parquet_race_ids)}")
        print(f"   最初のrace_id: {sorted(parquet_race_ids)[0] if parquet_race_ids else 'なし'}")
        print(f"   最後のrace_id: {sorted(parquet_race_ids)[-1] if parquet_race_ids else 'なし'}")
    except Exception as e:
        print(f"\n❌ Parquet読み込みエラー: {e}")
else:
    print(f"\n⚠️ Parquetファイルが見つかりません: {RACES_PARQUET}")

# 差分分析
print("\n" + "=" * 60)
print("差分分析")
print("=" * 60)

# HTMLにあってParquetにないもの（追加すべきデータ）
only_in_html = html_race_ids - parquet_race_ids
if only_in_html:
    print(f"\n✅ HTMLにのみ存在（新規データ）: {len(only_in_html)}件")
    print("   サンプル（最大10件）:")
    for rid in sorted(only_in_html)[:10]:
        print(f"     - {rid}")
    if len(only_in_html) > 10:
        print(f"     ... 他{len(only_in_html) - 10}件")
else:
    print(f"\n✅ HTMLにのみ存在: 0件（新規データなし）")

# ParquetにあってHTMLにないもの（削除されたデータ）
only_in_parquet = parquet_race_ids - html_race_ids
if only_in_parquet:
    print(f"\n⚠️ Parquetにのみ存在（HTMLが削除された？）: {len(only_in_parquet)}件")
    print("   サンプル（最大10件）:")
    for rid in sorted(only_in_parquet)[:10]:
        print(f"     - {rid}")
    if len(only_in_parquet) > 10:
        print(f"     ... 他{len(only_in_parquet) - 10}件")
else:
    print(f"\n✅ Parquetにのみ存在: 0件")

# 両方に存在するもの
both = html_race_ids & parquet_race_ids
print(f"\n📊 両方に存在: {len(both)}件")

print("\n" + "=" * 60)
print("結論")
print("=" * 60)

if only_in_html:
    print(f"✅ {len(only_in_html)}件の新規データがあります")
    print("   → incrementalモードで追加されます")
elif only_in_parquet:
    print(f"⚠️ Parquetの方が{len(only_in_parquet)}件多いです")
    print("   → HTMLファイルが削除されたか、異なるソースからのデータです")
    print("   → 整合性を保つため、MODE='full'での再パースを検討してください")
else:
    print("✅ HTMLとParquetが完全に一致しています")
    print("   → 新規データはありません")

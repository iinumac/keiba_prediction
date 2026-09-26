# 競馬予想プロジェクト 統合設計書

作成日: 2026-09-26
対象: `/Users/iinumac/_PrivateDev` 配下の競馬「予想」関連ソース（POG系は対象外）
ステータス: **フェーズ0（保全）・フェーズ1（統合）・フェーズ2（整理）完了 / フェーズ3 未着手**

---

## 1. 目的

競馬予想に関するソースが4ディレクトリに分散し、同じ生データを二重に抱えた状態になっていた。
これを **単一リポジトリ `keiba_prediction` に集約**し、データの取得・整理・学習・予想を
**Google Colab 上の C01〜C04 ノートブック 1本のパイプライン**で回せる形にする。

---

## 2. 統合前のインベントリ

| # | ディレクトリ | 最終更新 | Git | ディスク | 役割 | 処遇 |
|---|---|---|---|---|---|---|
| 1 | `keiba_prediction` | 2026-03 | `iinumac/keiba_prediction`（**生存**） | 7.3GB | Colabパイプライン、`src/`、parquet正本 | **統合先（ハブ）** |
| 2 | `keiba202608` | 2026-08 | なし | 36KB | C04（三連複・期待値） | ①へ移設 → **削除予定** |
| 3 | `odds_prediction` | 2026-04 | なし | 32KB | `deepresearch.md`（オッズ断層の理論） | ①へ移設 → **削除予定** |
| 4 | `Keiba` | 2025-12 | `iinumac/keiba.git`（**消滅**） | 5.5GB | 旧世代一式＋Firebase予想サイト＋`keiba_gag` | **アーカイブ** |

---

## 3. ⚠️ 初版設計書からの訂正

調査を進める中で、初版（2026-09-26 午前）の記述に **3点の誤りと3点の見落とし** が判明した。

### 訂正1: keiba_prediction は origin と同期していなかった

初版の記述「未pushコミット: 0件（origin/main と同期済み）」は**誤り**。
`git log origin/main..HEAD` が空だったため同期済みと判断したが、逆方向を確認していなかった。
実際は **ローカルが origin/main より6コミット遅れ**ていた。

```
1aa280fc Try to bypass netkeiba 403 from Colab IPs (#4)
67a65d69 Surface real reason behind not_found in C01 download loop (#3)
864d042d Merge pull request #2
7b7dcd6c Skip downloads by disk HTML existence, not parquet membership
64e13d3d Merge pull request #1
66354604 Fix HTML/Parquet diff check to compare race_id as a set
```

内容は **C01 の netkeiba 403 問題とダウンロード判定ロジックの修正**であり、
フェーズ3の「C01〜C04 通し実行」に直結する。GitHub 上で PR #1〜#4 として作業が進んでいた。
→ フェーズ0で rebase 済み（コンフリクトなし）。

### 訂正2: Keiba の GitHub リポジトリは消滅している

`https://github.com/iinumac/keiba.git` は **Repository not found**。
したがって **ローカルの `Keiba` が唯一のコピー**であり、未pushコミットは
「まだ push していない」のではなく「**push 先がもう存在しない**」状態だった。

これは「Keiba を削除せずアーカイブする」という初版の判断を、より強い理由で裏付ける。
アーカイブでは `.git`（665MB）を**必ず丸ごと保持**すること。

### 訂正3: Keiba の raceHTML は Git 管理外

`Keiba/.gitignore` が `data/raceHTML/` を除外しているため、
Keiba 側の 55,153 ファイル・4.0GB は **Git に入っていない**。
初版は「重複なので削除可」としたが、削除すると**ファイル自体が完全に消える**。
→ フェーズ2での照合は必須。`keiba_prediction` 側に全件あることを確認してから削除する。

### 見落とし1: Webフロントエンドは単一SPAで、未pushコミットにしか存在しなかった

`Keiba/public/` は「Web公開ソース66ファイル」ではなく、実体は
**`public/index.html` 単一ファイル（1,775行）**＋データ65件。

- タイトル: 「印入力＆買い目ジェネレーター (Online)」
- 構成: Firebase Auth（Googleログイン）＋ Firestore のブラウザ完結型SPA
- 存在場所: 未pushコミット `f8699e545` **のみ**（作業ツリーからは削除されていた）

→ フェーズ0でディスクに復元済み。
→ 注意: Firebase のクライアント設定が直書きされている。アーカイブを公開する場合は要確認。

### 見落とし2: keiba_prediction に Git管理外の実コードがあった

`src/` は「現役・唯一のコード資産」としたが、実際には
**`src/predict/predict_today.py`（264行）が未追跡**だった。
出馬表HTMLをパースして学習済みモデルで予想を出す、予想実行の本体にあたるスクリプト。
→ フェーズ0で main にコミット済み。

その他の未追跡（いずれもローカルにしか無かった）:
- `models_2025/` 8点 11MB — コード・ノートブックのどこからも参照されていない孤立資産
- `notebooks/_old/` 9点、`notebooks/tmp/` 18点 — 作業ゴミだが Git 管理外
- `data/raceHTML/2026/` 114件 — C01 でダウンロード済み・未コミット

### 見落とし3: data/csv は parquet と完全に同一内容

`keiba_prediction/data/csv/` 391MB は parquet の CSV エクスポートだった。

| ファイル | 行数 |
|---|---|
| `data/csv/results.csv` | 788,705 |
| `data/processed/results.parquet` | 788,705 |

さらに `results_part{1,2,3}.csv` は `results.csv` の三分割で、二重に重複している。
→ フェーズ0で `.gitignore` に追加。削除候補（391MB）。

---

## 4. フェーズ0（保全）実施記録 — 完了

削除を一切伴わず、「消えて困るものが全部 Git に入っている」状態を作った。

### keiba_prediction

| # | 操作 | 結果 |
|---|---|---|
| 1 | `.gitignore` に `.claude/` と `data/csv/` を追加 | — |
| 2 | 未追跡だった 2026年レースHTML 114件をコミット | `3c64e72e`（115ファイル / +224,491行） |
| 3 | ローカル生成版 `master_*.csv` を保全ブランチへ退避 | `backup/local-masters-20260926` |
| 4 | `origin/main`（6コミット先行）を fetch して rebase | コンフリクトなし |
| 5 | 未追跡だった `src/predict/predict_today.py` をコミット | `470dffd4`（264行） |
| 6 | 孤立資産を保全ブランチへ退避 | `backup/untracked-artifacts-20260926`（37ファイル） |

HTML 114件の健全性は事前に検証済み（62〜83KB・平均76KB、追跡済み平均74KBと整合、結果テーブルあり）。

**`master_*.csv` を main に載せなかった理由**:
main の版は Colab 生成（`ffd2d04a`, 2026-03-09 06:57 UTC）、ローカルの版は同日 21:26 JST 生成。
騎手ID集合は同一（574件）だが `jockey_added_value` が **526/574 件で値が異なる**。
どちらが正か判断材料がないため main は Colab 版のまま維持し、ローカル版はブランチに退避した。

### Keiba

| # | 操作 | 結果 |
|---|---|---|
| 1 | `public/index.html`（唯一のWebフロントエンド）をディスクへ復元 | 71KB / 1,775行 |
| 2 | 未追跡・未コミットだった成果物23件をコミット | `ff9cc6245`（+24,105行） |
| 3 | 保全タグを作成 | `archive/pre-consolidation-20260926` |

`data/weekly` と `public/data` の削除102件はコミットしていない（履歴に残るため復元可能）。

---

## 5. フェーズ1（統合）実施記録 — 完了

| # | 操作 |
|---|---|
| 1 | `C04_winning_strategy_simulation.ipynb` を `notebooks/colab/` へ移設 |
| 2 | `deepresearch.md` を `docs/odds_deepresearch.md` へ移設 |
| 3 | `notebooks/colab/README.md` を C01→C04 の通し手順に全面改訂（Colabバッジ4本、データフロー図、既知の課題） |
| 4 | 本書を `docs/MIGRATION_PLAN.md` として統合先に配置 |

---

## 6. 移行後の構成

```
_PrivateDev/
├── keiba_prediction/                    ← 唯一の現役リポジトリ
│   ├── notebooks/colab/
│   │   ├── C01_data_preparation.ipynb        HTML差分ダウンロード
│   │   ├── C02_feature_engineering.ipynb     HTMLパース → parquet更新 → push
│   │   ├── C03_model_training.ipynb          モデル学習 → 予測マスタ作成 → push
│   │   ├── C04_winning_strategy_simulation.ipynb  三連複 期待値・買い目
│   │   └── README.md                         C01→C04 の通し手順
│   ├── src/                             共通ロジック（C03/C04の特徴量もここへ寄せる）
│   ├── data/processed/                  parquet + マスタ（Colabから読む正本）
│   ├── data/raceHTML/                   生HTML（Git管理を継続 ※決定事項1）
│   ├── models/ models_2025/
│   └── docs/
│       ├── odds_deepresearch.md              オッズ断層の理論
│       └── MIGRATION_PLAN.md                 本書
└── _archive_keiba_2025/                 旧 Keiba（リネームのみ、読み取り専用・.git必須）
```

### 保全ブランチ

| ブランチ / タグ | リポジトリ | 内容 |
|---|---|---|
| `backup/local-masters-20260926` | keiba_prediction | ローカル生成版 `master_*.csv`（採用可否は未決） |
| `backup/untracked-artifacts-20260926` | keiba_prediction | `models_2025/`, `notebooks/_old/`, `notebooks/tmp/` |
| `archive/pre-consolidation-20260926` | Keiba | 統合前の全状態（唯一の記録） |

---

## 7. 重複と削除候補

| 項目 | 容量 | 削除の条件 |
|---|---|---|
| `Keiba/data/raceHTML/`（2010–2025, 55,153件） | 3.7GB | **Git管理外のため照合必須**。`keiba_prediction` 側（2010–2026, 55,435件・全件Git追跡済み）に全件あることをファイル単位で確認してから |
| `keiba_prediction/data/csv/` | 391MB | parquet と行数一致を確認済み。削除可 |
| `Keiba/keiba_gag/features_dataset_fixed.csv` | 377MB | parquet に置換済みと確認後 |
| `Keiba/node_modules/`, `Keiba/migration_env/` | 129MB | 再生成可能。削除可 |
| `keiba_prediction/notebooks/{tmp,_old}/` | 3.4MB | 保全ブランチに退避済み。削除可 |
| `keiba_prediction/notebooks/sagemaker/` | — | C01/C02 に置換済み |
| `keiba202608/`, `odds_prediction/` | — | 移設完了。削除可 |

**回収見込み: 約 4.6GB**

> 削除はすべて実行前にその場で確認を取る。本書の承認＝削除の承認ではない。

---

## 8. フェーズ2（整理）実施記録 — 完了

### アーカイブ化

`Keiba` を **`_archive_keiba_2025`** にリネームし、`ARCHIVED.md` を設置（コミット `b7c7b1232`）。
GitHub リモートが消滅しておりローカルが唯一のコピーである旨、`.git` を削除しないこと、
ここにしか無い資産（SPA・keiba_gag・特徴量データセット3種）を明記した。

### 重複 raceHTML の照合と削除

削除が不可逆（Keiba 側は Git 管理外）なため、サンプルではなく全件照合を行った。

| 検証 | 結果 |
|---|---|
| ファイル名集合 | Keiba 固有 **0件**（完全な部分集合） |
| 全55,153件のサイズ | **完全一致** |
| 全55,153件の **MD5** | **完全一致** |

照合後に削除。

### 削除実績（約3.8GB回収）

| 対象 | 容量 | 根拠 |
|---|---|---|
| `_archive_keiba_2025/data/raceHTML` | 3.3GB | 上記MD5照合 |
| `_archive_keiba_2025/{node_modules,migration_env}` | 129MB | 再生成可能 |
| `keiba_prediction/data/csv` | 374MB | parquet と行数完全一致 |
| `keiba_prediction/notebooks/sagemaker` | 24KB | C01/C02 に置換済み・Git復元可 |

`notebooks/{tmp,_old}` は保全ブランチへのコミット時に作業ツリーから除去済み。

容量: `_archive_keiba_2025` 5.5GB → **2.1GB** / `keiba_prediction` 7.3GB → **6.9GB**

### ドキュメント整備

| ファイル | 内容 |
|---|---|
| `docs/ARCHITECTURE.md` | 現構成で全面書き直し。GitHubをデータストアとする設計、C01〜C04、`src/` の公開関数、データ定義 |
| `docs/FEATURE_BACKLOG.md` | C03/C04 の特徴量突合表と、旧 Keiba・keiba_gag からの取り込み候補 |

### 旧 `Keiba/python` 救出候補の判定

**コードは移植せず、着眼点のみ `FEATURE_BACKLOG.md` に記録**する方針とした。
旧スクリプトは廃止済みの `features_dataset_fixed.csv` 前提で書かれており
そのままでは動かないため、動かないコードを現役リポジトリに置くより
知見を台帳化する方が有効と判断した。

| 判定 | スクリプト |
|---|---|
| **着眼点を採用**（C03/C04 のどちらにも無い分析軸） | `analyze_track_condition_upsets.py`（馬場状態×波乱度・478行）、`analyze_course_umaban.py`（コース×枠順）、`analyze_distance_impact{,_dirt}.py`（距離替わり）、`analyze_horse_weight.py`（馬体重増減）、`analyze_track_change.py`（芝ダ替わり） |
| **C04 と重複・移植不要** | `calculate_expected_value.py`、`detect_value_horses.py` |
| **別枠** | `parse_odds_from_image.py`（Firebase廃止後に単体利用なら要移植） |
| **不要** | `parse_jra_text.py`（ハードコードの使い捨て） |

---

## 9. フェーズ3（未着手）

1. **C01→C02→C03→C04 を Colab で通しで実行**し、動作と所要時間を記録
   - **C01 の netkeiba 403 問題**（PR #3/#4 で対策済み）が解消しているかを最優先で確認
2. **C03 と C04 の特徴量突合** → 共通部分を `src/features/` に集約
   （共通は7個のみ。`surface_encoded`/`surface_code` など同概念・別名が存在）
   → 作業台帳: `FEATURE_BACKLOG.md`
3. マスタ出力の `shift()` 有無の決着（未決事項C）
4. `keiba_gag` の戦略シミュレーション資産から C04 への取り込み判断
5. **C01〜C03 の自動化範囲の検討**（ユーザー指示により統合完了後に着手）

---

## 10. 決定事項

1. **生HTML（55,435件 / `.git` 240MB）は Git 管理のまま維持する**
   - 理由: parquet の読み込み・更新は多くても週1回であり、クローン時間は実害にならない

2. **統合先は `keiba_prediction`**（GitHub `iinumac/keiba_prediction`）

3. **`Keiba` は削除せずアーカイブ。`.git` は必ず保持**
   - 理由: GitHub リモートが消滅しており、ローカルが唯一のコピー

4. **C01〜C03 の自動化範囲の検討は統合完了後**

5. **Firebase プロジェクト `pog-draft-2025` をまるごと削除する**（未実施）
   - 当初は「POG と共有のため Hosting サイトのみ削除」としていたが、
     **POG 2025 が2026シーズンの作り直しにより不要**となり判断を変更。
     POG2026 は `pog-takatsuba` を使用しており `pog-draft-2025` に依存していない。
   - 削除により `keibayoso` / `registerOdds` / Firestore全コレクション /
     全開放ルールが一括で解消される。
   - 手順は `_archive_keiba_2025/ARCHIVED.md` の Firebase セクション参照。
     30日間の復元猶予あり。`pog-takatsuba` と取り違えないこと。

6. **Firestore ルールの全開放（`allow read, write: if true`）は 5 の実施で解消**

7. **旧スクリプトはコード移植せず着眼点のみ台帳化**

---

## 11. 未決事項

| # | 論点 | 状態 |
|---|---|---|
| A | Firebase の削除 | **方針決定済み・未実施**。`pog-draft-2025` をプロジェクトごと削除（利用者が POG2026 に移行して不在になったため）。手順は `_archive_keiba_2025/ARCHIVED.md` |
| B | `keiba_gag` の戦略資産（28本） | C04 とは**補完関係**と判明（C04=期待値ベース / keiba_gag=買い目パターン総当たり）。取り込み候補を `FEATURE_BACKLOG.md` に記録。採否はフェーズ3 |
| C | マスタ出力の `shift()` 有無 | ファイル選択ではなく **C03 の設計論点**と判明。`FEATURE_BACKLOG.md` §2 に整理。フェーズ3で決着 |
| D | 旧 `Keiba/python` 救出候補 | **判定完了**（§8参照） |
| E | Vertex AI `gemini-1.5-flash-001` | Aの実施時に不要となるため**クローズ** |

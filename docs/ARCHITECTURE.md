# アーキテクチャ

最終更新: 2026-09-26（旧 `Keiba/ARCHITECTURE.md` を現構成で全面的に書き直し）

競馬レースの3着内（複勝圏）確率を予測し、三連複の期待値がプラスになる買い目を出すシステム。
**GitHub リポジトリそのものをデータストアとして使い、実行環境は Google Colab** という構成をとる。

---

## 全体像

```
        netkeiba.com
             │  ① C01: 差分ダウンロード
             ▼
   data/raceHTML/YYYY/*.html          生HTML 55,435件（Git管理）
             │  ② C02: パース・増分更新
             ▼
   data/processed/races.parquet       レース情報   1.3MB
   data/processed/results.parquet     出走馬結果  28MB / 788,705行
             │                                    │
   ③ C03: 学習                          ④ C04: 直接読み込み
             ▼                                    ▼
   models/*.pkl                        三連複の期待値・推奨買い目
   data/processed/master_*.csv
```

### なぜ GitHub をデータストアにしているか

Colab は実行のたびに環境が消えるため、データを外に置く必要がある。
GitHub を使うことで、①データの永続化、②バージョン管理、③Colab からの
`raw.githubusercontent.com` 経由の高速読み込み、が同時に satisfied される。

- **書き込み**: C02 / C03 が処理の最後に `GITHUB_TOKEN`（Colabシークレット）で push
- **読み込み**: `src/utils/data_loader.py` の `GITHUB_BASE_URL` から parquet を取得

生HTML 55,435件を Git 管理下に置いているためリポジトリは大きい（`.git` 約240MB）が、
更新は多くても週1回のためクローン時間は実害にならないと判断している。

---

## 実行環境

| 環境 | 用途 |
|---|---|
| **Google Colab** | 主。C01〜C04 のすべて |
| ローカル | 補助。`src/predict/predict_today.py` で出馬表HTMLから直接予想 |

かつて SageMaker（`S01`/`S02`）とローカル実行（`L01`）の構成があったが、
いずれも Colab の C01/C02/C03 に統合され廃止済み。

---

## ノートブック

運用手順は [`notebooks/colab/README.md`](../notebooks/colab/README.md) を参照。

| # | 役割 | 入力 | 出力 | push |
|---|---|---|---|:---:|
| C01 | HTML差分ダウンロード | netkeiba | `data/raceHTML/` | — |
| C02 | パース → Parquet増分更新 | 生HTML | `races.parquet` / `results.parquet` | ✅ |
| C03 | LightGBM学習・マスタ作成 | Parquet | `models/` / `master_*.csv` | ✅ |
| C04 | 三連複の期待値・買い目 | Parquet（GitHubから直接） | 推奨買い目 | — |

C04 は C03 の成果物に依存せず Parquet を直接読むため、C03 を飛ばしても動作する。

---

## `src/` モジュール

| モジュール | 行数 | 主な関数 |
|---|---:|---|
| `scraper/parser.py` | 626 | `parse_race_html_full` — 1レースのHTMLを辞書化<br>`parse_multiple_html_full` — 一括パース<br>`parse_incremental_parquet` — **既存Parquetとの差分だけ処理**（C02の中核）<br>補助: `classify_race_level` / `parse_time_to_seconds` / `parse_horse_weight` / `parse_passing_order` |
| `features/calculator.py` | 216 | `calculate_horse_features` / `calculate_jockey_features` / `build_feature_dataset` |
| `utils/data_loader.py` | 217 | `load_races` / `load_results`（GitHubまたはローカル、キャッシュ付き）<br>`get_horse_history` / `get_jockey_stats` / `get_trainer_stats` / `search_horse_by_name` |
| `predict/predict_today.py` | 264 | 出馬表HTMLをパースし学習済みモデルで予想（ローカル実行用） |

> **注意**: C03 と C04 の特徴量計算は現在この `src/features/` を経由せず、
> 各ノートブック内に直接書かれている。両者の定義には差異があり、
> 集約が課題として残っている。→ [`FEATURE_BACKLOG.md`](FEATURE_BACKLOG.md)

---

## モデル

| ディレクトリ | 内容 |
|---|---|
| `models/` | `model_no_odds.pkl` / `model_with_odds.pkl` / `lightgbm_model.pkl` / `model_config.pkl` |
| `models_2025/` | 2025年世代の LightGBM（`baseline` / `g1_specialized` / `top3_{turf,dirt,with_odds,prediction}` / `improved_tuned`）と `course_gate_bias.json` |

C03 は目的変数を「3着以内（`is_top3`）」とし、オッズなし／オッズありの2モデルを学習する。
学習期間は `TRAIN_END_YEAR = 2024` までで、2025年以降を検証に充てる時系列分割。
新馬・初出走（`is_debut == 1`）は過去データが無いため学習から除外する。

`models_2025/` はコード・ノートブックのどこからも参照されていない孤立資産。

---

## 予測の考え方

的中率ではなく**期待値**を最大化する。控除率が20〜25%あるため、
人気馬を当てにいくだけでは回収率は75〜80%に収束する。

そこで市場（オッズ）が過小評価している馬 — AIの推定する真の複勝率 × オッズ > 1.0 —
を探すバリューベッティングを採る。理論的背景（パリミュチュエル市場のオッズ断層、
本命・大穴バイアス、「2強構造」の定式化）は
[`odds_deepresearch.md`](odds_deepresearch.md) を参照。

---

## データ定義

### `races.parquet`
レース単位。`race_id` が主キー。`race_name` / `surface` / `distance` / `race_date` ほか。

### `results.parquet`
出走馬×レース単位、788,705行。`race_id` + `horse_number` で一意。
`finish_position` / `horse_id` / `horse_name` / `jockey_id` / `trainer_id` /
`odds` / `popularity` / `impost` / `horse_weight` / `last_3f` / `time_seconds` ほか。

### `master_*.csv`
週末の予想時に参照する軽量スナップショット。C03 が生成。

| ファイル | 内容 |
|---|---|
| `master_horse.csv` | 馬ごとの最新 `horse_expected_top3_rate` と前走情報 |
| `master_jockey.csv` | 騎手ごとの最新 `jockey_added_value` |
| `master_trainer.csv` | 調教師ごとの最新 `trainer_added_value` |

**`jockey_added_value`（騎手の押し上げ力）の定義**
「そのレースの結果」から「馬の期待値」を引いた差分の、その騎手の過去累積平均。

```
jockey_added_value_in_race = is_top3 - horse_expected_top3_rate
jockey_added_value         = groupby(jockey_id).shift().expanding().mean()
```

`shift()` は未来情報のリークを防ぐため。ただしマスタ出力時にも効くため
最新レースが反映されない副作用があり、設計論点として残っている。

### 除外ルール
- 障害レース（`races.race_name` に「障害」を含む、または `surface` が障害）
- 藤岡康太騎手（C03 のクレンジング段階で除外）

---

## 前世代

2025年までの実装は `_archive_keiba_2025/`（旧 `Keiba`）に凍結されている。
GitHub リモートが削除済みでローカルが唯一のコピーのため、`.git` を保持すること。
詳細は同ディレクトリの `ARCHIVED.md`。

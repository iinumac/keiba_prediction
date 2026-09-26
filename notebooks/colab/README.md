# Google Colab 競馬予想パイプライン

データ取得 → 整形 → 学習 → 予想までを Google Colab 上で完結させるノートブック群です。
**C01 → C02 → C03** が週次のデータ更新、**C04** が週末の予想にあたります。

---

## ノートブック一覧

| # | ノートブック | 役割 | 出力 | Colab |
|---|---|---|---|---|
| C01 | `C01_data_preparation.ipynb` | netkeiba から未取得のレースHTMLだけを差分ダウンロード | `data/raceHTML/YYYY/*.html` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C01_data_preparation.ipynb) |
| C02 | `C02_feature_engineering.ipynb` | HTMLをパースして Parquet を増分更新 → GitHubへプッシュ | `data/processed/{races,results}.parquet` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C02_feature_engineering.ipynb) |
| C03 | `C03_model_training.ipynb` | LightGBM の学習と予測マスタ作成 → GitHubへプッシュ | `models/`, `data/processed/master_*.csv` | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C03_model_training.ipynb) |
| C04 | `C04_winning_strategy_simulation.ipynb` | 三連複の期待値戦略・回収率バックテスト・買い目出力 | 推奨買い目（画面出力） | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C04_winning_strategy_simulation.ipynb) |

---

## 週次の運用手順

### フェーズ1: データ更新（レース終了後）

1. **C01** を開いて「すべてのセルを実行」
   まだ持っていない最新のレースHTMLだけをダウンロードします。
2. **C02** を開いて「すべてのセルを実行」
   ダウンロードしたHTMLをパースして Parquet を更新し、GitHub へ自動プッシュします。
3. **C03** を開いて「すべてのセルを実行」
   最新の全データで AI モデルと予測用マスタを再構築し、GitHub へ自動プッシュします。

### フェーズ2: 予想（週末・当日）

4. **C04** を開いて「すべてのセルを実行」
   GitHub 上の Parquet を読んで3着内確率モデルを学習し、
   三連複の回収率バックテストと推奨買い目（軸1頭ながし／BOX／フォーメーション）を出力します。
   出馬表JSON（出馬表＋最新オッズ）を入力すると、未来のレースの買い目が出ます。

---

## C04 の考え方：的中率ではなく期待値

競馬には約20〜25%の控除率があるため、人気馬を当てにいくだけでは回収率は75〜80%に収束します。
C04 は **市場（オッズ）が過小評価している馬** — 真の複勝率 × オッズ > 1.0 となる馬 — を
AI で発見するバリューベッティング戦略を取ります。

理論的背景（パリミュチュエル市場のオッズ断層、本命・大穴バイアス、「2強構造」の定式化）は
[`docs/odds_deepresearch.md`](../../docs/odds_deepresearch.md) を参照してください。

---

## 事前準備：GitHub トークンの登録

C02 と C03 は処理の最後に生成物を GitHub へプッシュします。
そのため Colab 画面左の **鍵マーク（シークレット）** に以下を登録しておく必要があります。

* **名前**: `GITHUB_TOKEN`
* **値**: GitHub で発行した Personal Access Token (Classic)

シークレットから読み込めないエラーが出た場合は、実行途中にトークンの手入力枠が表示されるので
そこに直接貼り付けてください。

---

## データの流れ

```
netkeiba
   │  C01（差分ダウンロード）
   ▼
data/raceHTML/YYYY/*.html          ← Git管理（約55,000ファイル）
   │  C02（パース・増分更新）
   ▼
data/processed/races.parquet       ← 正本
data/processed/results.parquet
   │  C03（学習）              │  C04（直接読み込み）
   ▼                            ▼
models/ + master_*.csv        三連複 期待値・買い目
```

C04 は C03 の成果物ではなく **Parquet を直接** 読みます
（`raw.githubusercontent.com/iinumac/keiba_prediction/main/data/processed`）。
したがって C03 を飛ばしても C04 は動きますが、C02 までは必ず先に通してください。

---

## 既知の課題

- **C01 が netkeiba から 403 を返される場合がある**（Colab の IP レンジ起因）。
  対策コミットが入っています（`Try to bypass netkeiba 403 from Colab IPs`）が、
  再発する場合はダウンロード件数が 0 で終わっていないか確認してください。
- **C03 と C04 が特徴量を別々に定義している**。
  `market_implied_win_prob` / `odds_ratio_to_fav` / `jockey_added_value` などが
  両方に存在し、定義が一致しているか未検証です。`src/features/` への集約が課題です。

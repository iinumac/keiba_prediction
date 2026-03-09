# Colab (オンライン環境) でのデータ更新手順

週末のレースが終わった後など、最新のレースデータをGitHub上のParquetファイルに追加（更新）する際の手順です。
以下のリンクをクリックすると、お使いのブラウザ上でGoogle Colabが立ち上がり、すぐにスクリプトを実行できます。

## 使い方

1. 以下の **1️⃣ C01** を開き、「すべてのセルを実行」します。（まだ持っていない最新のレースHTMLだけをダウンロードします）
2. C01の処理が終わったら、続いて **2️⃣ C02** を開き、「すべてのセルを実行」します。（ダウンロードしたHTMLをパースしてParquetを更新し、GitHubへ自動プッシュします）

---

### ブラウザですぐに開くリンク集

#### 1️⃣ C01_data_preparation.ipynb (データ準備・HTML差分ダウンロード)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C01_data_preparation.ipynb)  
<https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C01_data_preparation.ipynb>

#### 2️⃣ C02_feature_engineering.ipynb (HTMLパース・Parquet保存・GitHubプッシュ)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C02_feature_engineering.ipynb)  
<https://colab.research.google.com/github/iinumac/keiba_prediction/blob/main/notebooks/colab/C02_feature_engineering.ipynb>

---

## ⚠️ C02 プッシュ時の注意点

C02の最後の処理でGitHubへ変更をプッシュします。
その際、ColabからGitHubへプッシュする権限が必要なため、Colab画面左側の「鍵マーク（シークレット）」に、あらかじめ以下の内容を登録しておく必要があります。

* **名前**: `GITHUB_TOKEN`
* **値**: GitHubで発行した Personal Access Token (Classic)

（※うまくシークレットから読み込めないエラーが出た場合は、実行途中にトークンの手入力枠が表示されるので、そこに直接コピペしてください）

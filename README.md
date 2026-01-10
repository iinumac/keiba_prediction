# 競馬予想プログラム

競馬レースの結果を予測するための機械学習プロジェクトです。

## プロジェクト構造

```
keiba_prediction/
├── notebooks/
│   ├── sagemaker/           # Sagemaker実行用Notebook
│   └── local/               # ローカル実行用Notebook
├── src/                     # 共通ソースコード
│   ├── scraper/             # HTMLスクレイピング
│   ├── features/            # 特徴量計算
│   ├── models/              # モデル定義
│   └── utils/               # ユーティリティ
├── data/
│   ├── raceHTML/            # レース結果HTML
│   ├── processed/           # 処理済みデータ
│   ├── features/            # 特徴量データ
│   └── images/              # 出馬表画像
├── models/                  # 学習済みモデル
└── config/                  # 設定ファイル
```

## 環境別役割分担

### Sagemaker (S01〜)
- HTMLファイルのダウンロード
- 特徴量の計算
- 計算結果の保存
- モデルの学習・更新

### ローカル (L01〜)
- 最新出馬表（画像ファイル）の解析
- モデルを使った予想

## Notebook命名規則

| 環境 | プレフィックス | 例 |
|------|---------------|-----|
| Sagemaker | `S{番号:2桁}_` | `S01_html_download.ipynb` |
| ローカル | `L{番号:2桁}_` | `L01_image_parser.ipynb` |

## セットアップ

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt
```

## 使用方法

1. Sagemakerで特徴量計算とモデル学習を実行
2. 学習済みモデルをローカルにダウンロード
3. ローカルで出馬表画像を解析し予想を実行

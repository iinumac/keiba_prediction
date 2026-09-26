# 特徴量バックログ / C03・C04 の突合

作成日: 2026-09-26
位置づけ: `MIGRATION_PLAN.md` フェーズ3「C03 と C04 の特徴量定義の突合」の作業台帳

---

## 1. 現状: C03 と C04 は別々に特徴量を定義している

| 特徴量 | C03（学習） | C04（三連複） | 備考 |
|---|:---:|:---:|---|
| `distance` | ✅ | ✅ | |
| `impost` | ✅ | ✅ | |
| `prev_finish` | ✅ | ✅ | |
| `prev_last_3f` | ✅ | ✅ | |
| `days_since_last` | ✅ | ✅ | |
| `jockey_added_value` | ✅ | ✅ | |
| `trainer_added_value` | ✅ | ✅ | |
| 馬場（芝/ダート） | `surface_encoded` | `surface_code` | **同概念・別名** |
| 馬の3着内率 | `horse_expected_top3_rate` | `horse_prev_top3_rate` | **同概念・別名・算出法未突合** |
| `level_score` | ✅ | — | 賞金ベースのクラス指標 |
| `is_jockey_changed` | ✅ | — | 乗り替わり |
| `popularity` / `odds` | オッズありモデルのみ | ✅ | |
| `market_implied_win_prob` | — | ✅ | 控除率補正後の市場暗示確率 |
| `odds_ratio_to_fav` | — | ✅ | 1番人気とのオッズ比＝**断層の指標** |
| `pop_odds_mismatch` | — | ✅ | 人気とオッズの乖離 |
| `horse_prev_win_rate` | — | ✅ | |
| `prev_popularity` / `prev_odds` | — | ✅ | |
| `is_debut` | — | ✅ | |
| `horse_weight` | — | ✅ | |
| `horse_number` | — | ✅ | 馬番 |

**共通はわずか7個。** C04 は市場（オッズ）側の特徴量が厚く、C03 は馬・騎手の実力側が厚い。

### やること

1. `surface_encoded` / `surface_code` の名称統一
2. `horse_expected_top3_rate` と `horse_prev_top3_rate` の**算出法を突合**（同じ値か確認）
3. 共通部分を `src/features/calculator.py` に集約し、両ノートブックが同じ関数を読む形にする
4. C04 の市場系特徴量（`odds_ratio_to_fav` ほか）を C03 のオッズありモデルにも入れるか検討

---

## 2. マスタ出力の設計論点（未決事項C）

`C03` のマスタ出力は `shift().expanding().mean()` の値を最新行から取るため、
**その馬・騎手の最新レースが評価値に反映されない**（1レース分古い）。

学習時は `shift()` が必須（リーク防止）だが、予測時のマスタは
完了済みレースをすべて含むのが筋であり、ここは C03 側の設計論点。

旧実装 `recompute_masters.py`（`backup/untracked-artifacts-20260926` ブランチ、
`notebooks/tmp/`）が `shift()` なしの inclusive 版を実装しており、
コメントに "corrected expanding means" とある。ただし騎手評価の基準値も
inclusive に変えているため学習時と食い違う。採否は要検討。

参考実装の取得:
```
git show backup/untracked-artifacts-20260926:notebooks/tmp/recompute_masters.py
```

---

## 3. 旧 Keiba にあり、C03・C04 のどちらにも無い分析軸

いずれも `_archive_keiba_2025/python/` にスクリプトが残っている。
旧 `features_dataset_fixed.csv` 前提で書かれているため**そのままでは動かない**。
移植するのはコードではなく**着眼点**。

| 分析軸 | 出典スクリプト | 行数 | 特徴量化の案 |
|---|---|---:|---|
| **馬場状態 × 波乱度** | `analyze_track_condition_upsets.py` | 478 | 重馬場で低人気馬が好走しやすいかの検証。真なら馬場状態を特徴量に追加し、C04 の期待値戦略の**セグメント条件**に使える |
| **コース × 枠順バイアス** | `analyze_course_umaban.py` | 102 | 成果物 `models_2025/course_gate_bias.json` は既にあるが**生成スクリプトが無い**。再生成できる状態にしたい |
| **距離替わり** | `analyze_distance_impact.py` / `_dirt.py` | 206 / 209 | 前走との距離差。C03/C04 とも `distance` の絶対値のみで**変化量を持っていない** |
| **馬体重増減** | `analyze_horse_weight.py` | 201 | C04 は `horse_weight` の絶対値のみ。**前走比の増減**が無い |
| **芝⇔ダート替わり** | `analyze_track_change.py` | 204 | C03/C04 とも `surface` の値のみで**替わりフラグが無い** |

### C04 と重複するもの（移植不要）

| スクリプト | 行数 | 判定 |
|---|---:|---|
| `calculate_expected_value.py` | 233 | 予測確率×オッズの期待値計算。**C04 が上位互換**（三連複特化・バックテスト付き） |
| `detect_value_horses.py` | 217 | 穴馬検出。C04 のバリューベッティングと目的が重複 |

### 別枠

| スクリプト | 行数 | 判定 |
|---|---:|---|
| `parse_odds_from_image.py` | 74 | 画像→オッズCSV。Firebase Function `registerOdds`（Vertex AI）と対になる機能。Firebase 廃止後に単体で使うなら要移植 |
| `parse_jra_text.py` | 86 | JRA公式テキストをハードコードでパースする使い捨て。**不要** |

---

## 4. keiba_gag（`_archive_keiba_2025/keiba_gag/`）からの取り込み候補

C04 が**期待値ベース**（AI確率×オッズ）なのに対し、keiba_gag は
**買い目パターンの総当たり最適化**。C04 に無い視点なので補完的。

| スクリプト | 内容 | 取り込み案 |
|---|---|---|
| `compare_strategies_20_29.py` | 1番人気オッズ2.0〜2.9に限定し、BOX3種/軸流し3種/フォーメーション3種の**9戦略を回収率で比較** | C04 の買い目生成に「どの形が効率的か」の根拠を与える |
| `sim_ai_2025.py` | 「AI1位 - AI1〜3位 - AI1〜7位」13点フォーメーションの2025年検証 | AI順位ベースのフォーメーション最適化 |
| `optimize_segment.py` | セグメント（オッズ帯）ごとの最適化 | 期待値だけでなく**どのレースを買うか**の選別条件 |
| `kaime.txt` / `keiba_report_20251207.md` | 実際の購入履歴と成果（11月第5週 回収率372.7% / 12月第1週 183.2%） | **実戦の正解データ**。バックテスト結果の妥当性検証に使える |

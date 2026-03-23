# jleague_scraper

[Jリーグ公式サイト](https://www.jleague.jp)から選手の個人スタッツを取得し、Excelで開きやすい形式のCSVに出力するPythonツールです。  
チーム単位だけでなく、リーグ全体の全選手データの取得にも対応しています。

## まずは最短で動かす（Windows向け）

1. Pythonをインストール（未導入の場合）  
2. 任意のフォルダで以下を1行ずつ実行

```shell
git clone https://github.com/AKmitorin/jleague_scraper
cd jleague_scraper
pip install -r requirements.txt
py main.py
```

引数なしで実行すると、対話式ウィザードが起動します。質問に答えるだけでOKです。
Mac・Linuxを使用している方は、 `py` コマンドを `python3` に置き換えてください。以下で紹介する使い方についても同様です。

Windowsではエクスプローラー上で `run_windows.bat` をダブルクリックしても起動できます。

---

## 特徴

- **全82項目に対応**  
  出場試合数、得点、アシストといった基本情報から、ゴール期待値、パス成功率、走行距離、スプリント回数などの詳細データまで取得できます。
- **リーグ全体データの完全取得**  
  `--team all` 実行時は各チームの個別ページを巡回するため、ランキング上位に表示されない選手も含めて取得できます。
- **引退・移籍選手への対応**  
  サイト上で詳細ページへのリンクが切れている選手のデータも収集対象です。
- **日本語ヘッダー付きCSV**  
  出力されるCSVは日本語項目名（単位付き）なので、そのまま分析に使えます。
- **Excel対応**  
  BOM付きUTF-8で保存されるため、ExcelやGoogleスプレッドシートで文字化けせずに開けます。
- **柔軟な指定**  
  シーズン（2025年、2026年など）やカテゴリ（J1/J2/J3）を自由に指定できます。

---

## 動作環境

- Python 3.12以上

---

## セットアップ

```bash
git clone https://github.com/AKmitorin/jleague_scraper
cd jleague_scraper
pip install -r requirements.txt
```

## 使い方

### 対話式ウィザード（初心者向け）

```shell
py main.py
```

※ 途中で `all` を選ぶと全チーム取得となり、10〜15分程度かかる場合があります。

### 引数指定

```shell
py main.py --year 2025 --category j1 --team shimizu --output output
```

※ 引数なしで実行した場合は対話式ウィザードが起動します。引数ありのときに省略した値は上記のデフォルトが使われます。

#### チーム一覧を表示

```shell
py main.py --list-teams --year 2025 --category j1
```

## パラメータ

| 引数 | 説明 | デフォルト値 | 例 |
| :--- | :--- | :---| :--- |
| `--year` | 取得したいシーズン	| `2025` | `2026` |
| `--category` | カテゴリ（j1 / j2 / j3） |	`j1` | `j2` |
| `--team` | チームの英名（または `all`） | `shimizu` | `kashima`, `urawa` |
| `--output` | 保存先ディレクトリ | `output` | `my_data` |
| `--interactive` | 対話式ウィザードで実行 | なし | - |
| `--list-teams` | チーム一覧を表示して終了 | なし | - |

## 出力ファイル

実行後、指定したディレクトリ（デフォルトでは output/）に以下の形式でCSVが生成されます。
    -  stats\_shimizu\_2025\_j1.csv
    - stats\_all\_2025\_j1.csv

## チーム指定について

`--team` には、Jリーグ公式サイトのURLに含まれるチーム識別子を指定します。

例（2025年J1）：
| 値 | チーム名 |
| :--- | :--- |
| `kashima` | 鹿島アントラーズ |
| `urawa` | 浦和レッズ |
| `kashiwa` | 柏レイソル |
| `ftokyo` | FC東京 |
| `tokyov` | 東京ヴェルディ |
| `machida` | FC町田ゼルビア |
| `kawasakif` |	川崎フロンターレ |
| `yokohamafm` | 横浜F・マリノス |
| `yokohamafc` | 横浜FC |
| `shonan` | 湘南ベルマーレ |
| `niigata` | アルビレックス新潟 |
| `shimizu` | 清水エスパルス |
| `nagoya` | 名古屋グランパス|
| `kyoto` | 京都サンガF.C. |
| `gosaka` | ガンバ大阪 |
| `cosaka` | セレッソ大阪 |
| `kobe` | ヴィッセル神戸 |
| `okayama` | ファジアーノ岡山 |
| `hiroshima` | サンフレッチェ広島 |
| `fukuoka` | アビスパ福岡 |

その他のチームは、Jリーグ公式サイトのURL：

```
https://www.jleague.jp/stats/{j1|j2|j3}/player/{year}/{team_id}/{stats_category}/
```

の `{team_id}` 部分を指定してください。

## 注意事項

- 本ツールは[Jリーグ公式サイト](https://www.jleague.jp)のHTML構造に依存しています。サイトの変更により動作しなくなる可能性があります。
- サーバーへの負荷を抑えるため、各項目の取得間に待機時間を設けています。
- `--team all` 実行時は全チームを巡回するため、10〜15分程度かかる場合があります。

## よくある失敗

- `py`, `python3` コマンドが動かない  
  Pythonがインストールされていない可能性があります。Python 3.12以上を入れてから再実行してください。
- `チーム一覧の取得に失敗しました`  
  ネットワークが不安定な場合に発生します。時間をおいて再実行してください。

## ライセンス

MIT License

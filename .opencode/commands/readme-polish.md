---
description: Markdown文書を構造修正し、yomiyasuで推敲する
---

`$ARGUMENTS` で指定されたMarkdown文書（省略時は `README.md`）を読みやすくしてください。次の手順で進めます。

1. 対象ファイルを最後まで読み、見出し構成の乱れ、表や箇条書きの崩れ、重複した説明、詰め込みすぎた長い段落を洗い出す。
2. `npx markdownlint-cli2 <対象>` を実行し、書式の崩れ（インデントによるコードブロック化、表セルのタブや空白、見出しレベルの不揃い、フェンス前後の空行など）を確認する。
3. `yomiyasu` スキルを読み込み、その手順（文書の種類と読者の判定、lint、言い直し、検査、verify）に従う。
4. 原文は変更せず、構造修正と推敲を反映した下書きを `<対象>.yomiyasu.md` に保存する。
5. `python3 $HOME/.config/opencode/skills/yomiyasu/scripts/yomiyasu_check.py run --source <対象> --final <対象>.yomiyasu.md --doc-type article` を実行し、出た候補を1つずつ確認する。直す場合は1回だけ直して再実行する。
6. 本文を変えない場合は、提出の直前に `verify --final <対象>.yomiyasu.md` を実行する。
7. 内容に問題がなければ下書きを `<対象>` に取り込み、下書きを削除する。
8. 次を簡潔に報告する。変更点、実行したコマンド（`markdownlint-cli2`、yomiyasu の run/verify）、残った lint 候補とその扱い。

`--doc-type` は文書に合わせて変えてよい（技術記事は `article`、手順書は `manual` など）。引数やチーム一覧、出力ファイル名などの事実に関わる記述を変えた場合は、必ずコード（`main.py`、`output.py`、`stat_definitions.py`、`team_names.py`）と突き合わせて確認する。

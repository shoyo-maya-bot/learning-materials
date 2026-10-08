# 教材の書き方（執筆ルール）

## 1 章の構成（この順で、見出しもこの名前で）

```markdown
# 20-07 Spring Boot の仕組み（DI）

!!! abstract "到達目標"
    - DI（依存性の注入）が何のためにあるかを説明できる
    - （2〜4 個。「〜を説明できる」「〜を書ける」「〜を読める」の形）

## 何か
## なぜ必要か
## どうやるか
（手順・コード。「悪い例」と「良い例」を並べる。!!! failure "悪い例" / !!! success "良い例"）
## サンプルアプリでは
（dev-environment の sample-app の該当ファイルと行の意味。パスは `sample-app/src/main/java/...`）
## もし〇〇がなかったら？
（その仕組みが無いと何が起きるか。1〜2 段落）
## 理解度チェック
（3〜5 問。答えは ??? note "答え"（折りたたみ）に書く）
## コードを読むときの確認観点
（- [ ] のチェックリスト 3〜6 個）
```

- 30 実ソース読解の章は「演習」節を最後に置き、解答は `docs/30-reading/answers/30-xx.md` に分ける（本文からリンク）
- 文体: です・ます。1 文 60 字程度まで。専門用語は初出で説明する
- コードは sample-app の実物を引用する（存在しないクラス・メソッドを書かない）。説明用の短い例は「例:」と明記する
- 社名・顧客名・実在のシステム名・個人名を書かない。架空の例は 会員・注文・商品
- sample-app などの実物を引用したコードブロックには、直前に引用元のコメントを書く（下の「コードの引用」）
- 外部のドキュメントは公式（Oracle / Spring / MyBatis / JUnit / Karate / Git など）にリンクする
- 1 章は 150〜400 行を目安。長くなる場合は分割を相談する

## コードの引用

dev-environment のコードを引用したブロックの直前に、引用元をコメントで書きます。
`scripts/check_code_quotes.py`（CI）が、実物と一致しているかを確かめます。

````markdown
<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java#L19-L22 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="19"
（引用したコード）
```
````

- パスは dev-environment のリポジトリ直下から書く（`sample-app/`・`local/`・`cloud/` など）
- `@exercise-base` / `@main` は引用したブランチ。冒頭に「読むコードは `exercise-base` ブランチ」の注記がある章は `@exercise-base`、それ以外は `@main`
- 本文や title・`linenums` で行番号を示すときは `#L19-L22` で範囲も書く。範囲を書くと、その行と一致するか（行番号のずれ）まで確かめる。
  離れた行の抜粋は `#L24-L34,L41-L65` のように並べる
- 行番号を示さない引用は範囲を省く（`<!-- src: sample-app/.../Member.java @main -->`）。ファイルのどこかに、そのまま連続してあればよい
- 空白の量と空行の有無は比べない。途中を飛ばすときは `// ...`・`// ...（説明）`・`// 46〜50 行目: 説明`・`# （中略）` の行を置く
- 行の一部を伏せるときは `（省略）` と書く（任意の文字列に一致する）
- title が `sample-app/`・`local/`・`cloud/` で始まるブロックは、コメントが無いと失敗する。説明用に書き換えた例（「例:」「悪い例」「修正案」）には付けない
- コメントの付け方に迷ったら `python scripts/check_code_quotes.py --suggest` が、一致する引用元を提案する

### 本文の行番号

本文（コードブロックの外）で「`DefaultFileFetcher.java` の 33〜35 行目」「`MemberServiceTest.get_throwsNotFoundForUnknownId`（61〜67 行目）」
のように行番号を書いたものも、`check_code_quotes.py` が固定した SHA の実物と照合します。

- 照合するのは、`ファイル名`（拡張子付き。同名のファイルが複数あるときはパスで書く）か `クラス名`・`クラス名.メソッド名` の直後の「N 行目」「N〜M 行目」
- 比べるブランチは、ページ冒頭に「読むコードは `exercise-base` ブランチ」の注記がある章と、30 実ソース読解の解答（`30-reading/answers/`）は `exercise-base`、それ以外は `main`
- 行が存在し、空行でないこと。直後に「の `コード`」「（`コード`）」「: `コード`」と書いたら、そのコードがその行にあること（`...` は任意の文字列）。
  `クラス名.メソッド名` や「（`メソッド名`）」なら、その行にメソッド名があるか、その行がそのメソッドの中であること
- コードもメソッド名も書いていない参照は、すぐ後の引用ブロック（「〜の 24〜33 行目です。」の後に引用）か、
  すぐ前の引用ブロック（引用の下の「- 40 行目: …」の箇条書き）と照合する
- どれでも照合できない参照は失敗になる（上限 0. `--max-unverified`）。行番号を書くときは
  「`File.java` N〜M 行目（`メソッド名`）」「`File.java` N 行目の `コード`」の形にして、中身と照合できるようにする
- ずれていると、同じコードがある行を案内する（「8 行目にあります」）。数字だけの「同じファイルの 36〜37 行目」は照合しない

### 引用元の固定

`@main` / `@exercise-base` は、ブランチの最新ではなく `dev-environment-pin.json` に書いた SHA に読み替えて比べます。
dev-environment が更新されても、教材の CI が急に赤くなることはありません（`check_versions.py` も同じ SHA を使います）。
固定先を変えるのは、このファイルの 1 か所だけです。

dev-environment の更新に教材を合わせる手順:

1. 手元の dev-environment で、新しいコードと教材を比べる: `python scripts/check_code_quotes.py --repo-dir ../dev-environment --ref main=HEAD`
2. 出てきた差分に合わせて教材を直す（引用の中身・行番号・本文の説明）
3. `dev-environment-pin.json` の SHA を新しいコミットに上げ、教材の修正と同じ PR に入れる

dev-environment の PR では、教材の引用検査がその PR の head に対して走ります（dev-environment 側の CI）。
そこで差分が出たら、上の手順で教材の PR を用意します。

## 版の書き方

本文（コードブロックの外）に版を直接書かず、`mkdocs.yml` の `extra.versions` を参照します。値は `exercise-base` ブランチのものです。

```markdown
---
render_macros: true
---

| ビルド | Gradle {{ versions.gradle }}（Wrapper で固定） |
```

- `{{ versions.* }}` を使うページは、先頭に `render_macros: true` を書く（無いと `{{ }}` がそのまま表示される）
- `scripts/check_versions.py`（CI）が、`extra.versions` と exercise-base の実ファイルを照合し、本文に直接書いた版（「Spring Boot 4.0」「Karate 1.5」「Java 17」「`release = 17`」など）を検出する
- コードブロックの中の版は、引用元のコメント（src:）で `check_code_quotes.py` が照合する

## 確認

```bash
pip install -r requirements.txt -c constraints.txt
mkdocs serve          # http://127.0.0.1:8000 でプレビュー
mkdocs build --strict # リンク切れ・nav 漏れで失敗する（CI と同じ）
python scripts/check_chapters.py   # 章の構成（必須の見出し）と禁止語（banned-terms.txt）を検査
python scripts/check_code_quotes.py   # 引用したコードと本文の行番号が dev-environment の実物と一致するか（git で取得する）
python scripts/check_code_quotes.py --repo-dir ../dev-environment   # 手元の clone で確かめる
python scripts/check_versions.py --repo-dir ../dev-environment      # 本文の版が exercise-base と一致するか
ruff check . && ruff format --check .   # scripts/・tests/ の静的解析と書式（設定は ruff.toml。CI の lint ジョブ）
```

Windows（PowerShell）でも同じコマンドで動きます（CI の `windows` ジョブで確認）。結果をファイルに保存したりパイプに渡したりするときは、
先に `$env:PYTHONUTF8 = '1'` を実行すると、日本語の出力で止まりません。

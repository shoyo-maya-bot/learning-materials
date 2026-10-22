# learning-materials

新しく参加した開発者向けの教材（Java 17 / Spring Boot / MyBatis / Gradle / JUnit 5 / Karate）です。MkDocs でサイトにして GitHub Pages で公開します。

**サイト**: https://shoyo-maya-bot.github.io/learning-materials/

| 編 | 章 | 内容 |
|---|---|---|
| 10 環境構築 | 6 | Git・JDK・VS Code・コンテナ（Rancher Desktop）・sample-app の実行・Copilot |
| 20 基礎 | 18 | Java・record・Gradle・DI・設定・REST・入力チェック・SQL・MyBatis・トランザクション・ログ・JUnit・モック・Karate・Git の運用 |
| 30 実ソース読解 | 15 + 解答 | sample-app の会員 API と注文取込バッチを 1 本ずつ読む。各章に演習、解答は別ページ |
| 40 非同期処理 | 2 | スレッド・@Async・キュー（SQS）・再試行・冪等性 |
| 50 API | 7 | REST 設計・ステータスとエラー応答・OpenAPI・ページング・認証と認可・テスト |
| 60 設計品質 | 4 | 設計書の書き方・レビュー・品質の測り方・AI の出力を疑う（演習） |
| 70 クラウドとアーキテクチャ | 7 | 上流工程と非機能要件・アーキテクチャ設計・AWS（IAM・VPC・主要サービス・Well-Architected・DR）・Azure・資格試験（SAA / AZ） |
| 80 案件担当になる | 13 + 解答 | 作業担当から案件担当へ。到達度の目安表と自己診断、見積の手法・要員計画・進捗とエスカレーション・不具合と静的解析・設計書の読み方と改善提案・影響範囲・テスト観点・ブランチとコンフリクト・コミット単位・データの入出力方式・共通項目とログレベル・環境の差と共通部品。各章に演習、解答は別ページ |
| 00 マネジメント | 1 | 見積もり・進捗・品質・リスク・報告 |
| 付録 | 3 | つまずき集・外部参照・質問のコツ |

教材のコードは [dev-environment](https://github.com/shoyo-maya-bot/dev-environment) の `sample-app` を使います（70 クラウドとアーキテクチャは `cloud/` の Terraform も読みます）。
実案件では、30 実ソース読解の各章にある「実案件での読み替え」の表を使って実際のソースに当てはめてください。

## 書く・直す

執筆のルールと章のテンプレートは [CONTRIBUTING.md](CONTRIBUTING.md) にあります。
AI（Copilot など）に書かせるときの指示は [AGENTS.md](AGENTS.md) です。
引用元の dev-environment は `dev-environment-pin.json` の SHA で固定しています（更新の手順は CONTRIBUTING.md の「引用元の固定」）。

```bash
pip install -r requirements.txt -c constraints.txt   # 版は constraints.txt で固定（deps-lock.yml が自動で作る）
mkdocs serve                       # http://127.0.0.1:8000
python scripts/check_chapters.py   # 章の構成（到達目標・必須の見出し・演習と解答）と禁止語
python scripts/check_code_quotes.py   # 引用したコードが dev-environment の実物と一致するか
python scripts/check_versions.py   # 本文の版（mkdocs.yml の extra.versions）が exercise-base の実物と一致するか
python scripts/check_java_examples.py   # 「例:」などの Java のコード例の構文（Java 17 以上が必要）
mkdocs build --strict              # CI と同じ（サイト内のリンク切れで失敗）
python scripts/check_links.py site # 外部リンクの切れ（CI では週 1 回だけ）
```

本文に書く版（Java・Spring Boot・Gradle など）は、演習で使う dev-environment の **`exercise-base` ブランチ** のものです。
値は `mkdocs.yml` の `extra.versions` の 1 か所にまとめ、本文では `{{ versions.gradle }}` のように参照します（そのページの先頭に `render_macros: true`）。

main に push すると GitHub Pages に公開されます（初回だけ、リポジトリの Settings → Pages → Source を **GitHub Actions** にしてください）。
引用したコードや版が dev-environment の実物（`dev-environment-pin.json` で固定した SHA）とずれていると公開しません。
週 1 回の定期検査では、固定した SHA ではなく dev-environment の各ブランチ（main / exercise-base）の**最新**と比べ（`--latest`）、ずれていれば Issue が自動で起票されます（公開は止まりません。教材を直して SHA を上げる合図です）。
同じ定期検査で外部リンクも確かめ、切れていれば別の Issue「外部リンクが切れています（週 1 回の検査）」が起票されます（push・PR では確かめません）。

## 変更点

| 時期 | 変更 |
|---|---|
| 2026-10 | 「80 案件担当になる」を追加（13 章と解答）。作業担当・案件担当・業務開発リーダーの 3 段階と到達度の目安表、既存の章との対応、自己診断のやり方。00 マネジメント・学習の進め方から案内する |
| 2026-10 | 本文の版を `mkdocs.yml` の `extra.versions` に集約（mkdocs-macros-plugin を追加）。引用・版の検査に通らないと公開しない |
| 2026-10 | 40-02 の誤り（`OrderMessage` に無い `memberId`、DLQ に移る回数、メッセージ ID の重複排除では送り手の再送を弾けないこと）を直す。コード例の型を sample-app にそろえ（20-07・20-16）、record に無いアクセサを呼ぶコード例を `check_java_examples.py` で検出する |
| 2026-10 | 「例:」などの Java のコード例の構文検査（`check_java_examples.py`）を CI に追加し、誤り 16 件を直す。外部リンクの検査（`check_links.py`）を週 1 回の定期実行に追加し、切れていたリンク 1 件（Karate の公式ドキュメント）を直す |

## セキュリティ・ライセンス

- 脆弱性を見つけたら、公開の Issue ではなく [SECURITY.md](SECURITY.md) の方法で知らせてください
- ライセンスは [MIT](LICENSE) です

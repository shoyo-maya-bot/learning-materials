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
| 60 設計品質 | 3 | 設計書の書き方・レビュー・品質の測り方 |
| 70 クラウドとアーキテクチャ | 7 | 上流工程と非機能要件・アーキテクチャ設計・AWS（IAM・VPC・主要サービス・Well-Architected・DR）・Azure・資格試験（SAA / AZ） |
| 00 マネジメント | 1 | 見積もり・進捗・品質・リスク・報告 |
| 付録 | 3 | つまずき集・外部参照・質問のコツ |

教材のコードは [dev-environment](https://github.com/shoyo-maya-bot/dev-environment) の `sample-app` を使います（70 クラウドとアーキテクチャは `cloud/` の Terraform も読みます）。
実案件では、30 実ソース読解の各章にある「実案件での読み替え」の表を使って実際のソースに当てはめてください。

## 書く・直す

執筆のルールと章のテンプレートは [CONTRIBUTING.md](CONTRIBUTING.md) にあります。

```bash
pip install -r requirements.txt
mkdocs serve                       # http://127.0.0.1:8000
python scripts/check_chapters.py   # 章の構成（到達目標・必須の見出し・演習と解答）
mkdocs build --strict              # CI と同じ（リンク切れで失敗）
```

main に push すると GitHub Pages に公開されます（初回だけ、リポジトリの Settings → Pages → Source を **GitHub Actions** にしてください）。

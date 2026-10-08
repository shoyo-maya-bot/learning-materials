---
render_macros: true
---

# 外部参照

教材より詳しく調べたいときに使う、**公式ドキュメント** へのリンク集です。
ブログや Q&A サイトの情報は、古い版の内容や誤りを含むことがあります。まず公式を確認する習慣をつけてください。

!!! tip "版に注意する"
    sample-app（演習で使う `{{ versions.branch }}` ブランチ）は Java {{ versions.java }}・Spring Boot {{ versions.spring_boot }}・Gradle {{ versions.gradle }}・PostgreSQL {{ versions.postgres }} を使っています。
    `main` ブランチは版が新しいことがあります（`dev-environment/README.md` の「技術スタック」）。
    公式ドキュメントは版ごとに分かれていることが多いので、ページの版の表示を確認してください。
    版の一覧は `dev-environment/README.md` の「技術スタック」と `sample-app/build.gradle` にあります。

## Java

| 資料 | 内容 |
|---|---|
| [Java SE 17 ドキュメント（Oracle）](https://docs.oracle.com/en/java/javase/17/) | 言語仕様・ツール・ガイドの入口 |
| [Java SE 17 API リファレンス（Oracle）](https://docs.oracle.com/en/java/javase/17/docs/api/) | 標準ライブラリのクラスとメソッド（`String`、`List`、`Optional` など） |
| [Amazon Corretto 17 ユーザーガイド](https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/what-is-corretto-17.html) | Corretto のインストールと版の一覧 |
| [Eclipse Temurin（Adoptium）](https://adoptium.net/) | Temurin の入手先 |

## Spring Boot・MyBatis

| 資料 | 内容 |
|---|---|
| [Spring Boot リファレンス](https://docs.spring.io/spring-boot/index.html) | 設定・プロファイル・Web・テストなど全般 |
| [Spring Framework リファレンス](https://docs.spring.io/spring-framework/reference/) | DI・トランザクション・Web MVC の仕組み |
| [MyBatis 3 ドキュメント（日本語）](https://mybatis.org/mybatis-3/ja/) | Mapper XML の書き方、`#{}` と `${}` の違い、動的 SQL |
| [MyBatis Spring Boot Starter](https://mybatis.org/spring-boot-starter/mybatis-spring-boot-autoconfigure/) | Spring Boot から MyBatis を使う設定（`mybatis.*` のプロパティ） |

## テスト

| 資料 | 内容 |
|---|---|
| [JUnit](https://junit.org/) | JUnit のユーザーガイドへの入口（sample-app は JUnit 5 の書き方） |
| [AssertJ ドキュメント](https://assertj.github.io/doc/) | `assertThat(...)` の書き方 |
| [Mockito](https://site.mockito.org/) | モック（差し替え用の偽物）の作り方 |
| [Karate](https://karatelabs.github.io/karate/) | API テストのシナリオ（`.feature`）の書き方 |
| [JaCoCo](https://www.jacoco.org/jacoco/trunk/doc/) | カバレッジの測り方とレポートの見方 |

## ビルド

| 資料 | 内容 |
|---|---|
| [Gradle ユーザーマニュアル](https://docs.gradle.org/current/userguide/userguide.html) | タスク・依存関係・Wrapper |
| [Spring Boot Gradle プラグイン](https://docs.spring.io/spring-boot/gradle-plugin/index.html) | `bootRun`・`bootJar` の使い方 |

## Git・GitHub

| 資料 | 内容 |
|---|---|
| [Git ドキュメント](https://git-scm.com/doc) | コマンドのリファレンス |
| [Pro Git（日本語）](https://git-scm.com/book/ja/v2) | Git の考え方を基礎から学べる書籍（無償） |
| [gitattributes](https://git-scm.com/docs/gitattributes) | 改行コードなどをファイルの種類ごとに決める設定 |
| [GitHub Docs（日本語）](https://docs.github.com/ja) | リポジトリ・PR・Actions・認証 |
| [SSH で GitHub に接続する](https://docs.github.com/ja/authentication/connecting-to-github-with-ssh) | SSH 鍵の作成と登録 |

## DB・コンテナ

| 資料 | 内容 |
|---|---|
| [PostgreSQL {{ versions.postgres }} ドキュメント](https://www.postgresql.org/docs/{{ versions.postgres }}/) | SQL・データ型・`psql` |
| [Rancher Desktop ドキュメント](https://docs.rancherdesktop.io/) | インストールと設定（Container Engine、メモリ、ネットワーク） |
| [Docker Compose ドキュメント](https://docs.docker.com/compose/) | `docker compose` コマンドと `docker-compose.yml` の書き方 |
| [WSL のインストール（Microsoft）](https://learn.microsoft.com/ja-jp/windows/wsl/install) | WSL2 の有効化 |

## AWS

| 資料 | 内容 |
|---|---|
| [AWS SDK for Java 2.x 開発者ガイド](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/home.html) | `S3Client` などのクライアントの作り方、認証情報の扱い |
| [AWS Well-Architected フレームワーク](https://docs.aws.amazon.com/ja_jp/wellarchitected/latest/framework/welcome.html) | 6 つの柱とベストプラクティス（[70-05](../70-cloud/70-05-aws-patterns.md)） |
| [AWS アーキテクチャセンター](https://aws.amazon.com/jp/architecture/) | 構成図の参考例とリファレンスアーキテクチャ |
| [AWS Certified Solutions Architect – Associate](https://aws.amazon.com/certification/certified-solutions-architect-associate/) | 試験の概要と試験ガイドへのリンク（[70-07](../70-cloud/70-07-certification.md)） |
| [Terraform AWS プロバイダー](https://registry.terraform.io/providers/hashicorp/aws/latest/docs) | dev-environment の `cloud/` で使うリソースの書き方 |

## Azure

| 資料 | 内容 |
|---|---|
| [Azure のドキュメント（Microsoft Learn）](https://learn.microsoft.com/ja-jp/azure/) | 各サービスの入口 |
| [Azure Well-Architected Framework](https://learn.microsoft.com/ja-jp/azure/well-architected/) | 5 つの柱とサービスごとのガイド（[70-06](../70-cloud/70-06-azure.md)） |
| [AWS と Azure のサービスの比較](https://learn.microsoft.com/ja-jp/azure/architecture/aws-professional/) | AWS の経験者向けの対応表 |
| [Microsoft Learn の資格](https://learn.microsoft.com/ja-jp/credentials/) | AZ-900 / AZ-104 / AZ-305 の試験ページと練習評価 |

## 上流工程

| 資料 | 内容 |
|---|---|
| [非機能要求グレード（IPA）](https://www.ipa.go.jp/archive/digital/iot-en-ci/jyouryuu/hikinou/ent03-b.html) | 非機能要件の 6 大項目と、項目ごとの段階（[70-01](../70-cloud/70-01-requirements.md)） |

## エディタ・AI 支援

| 資料 | 内容 |
|---|---|
| [VS Code で Java を使う](https://code.visualstudio.com/docs/java/java-tutorial) | Java の拡張機能の使い方 |
| [GitHub Copilot ドキュメント（日本語）](https://docs.github.com/ja/copilot) | Copilot の機能、リポジトリのカスタム指示 |
| [VS Code の GitHub Copilot](https://code.visualstudio.com/docs/copilot/overview) | Chat・エージェントモード・指示ファイル・プロンプトファイル |

# 20 基礎

この章群では、サンプルアプリを読み書きするために必要な基礎を学びます。
対象は Java 17 / Spring Boot 4 / MyBatis / Gradle / JUnit 5 / Karate です。
目安の期間は **2 週間** です。

!!! abstract "この章群の到達目標"
    - サンプルアプリ（`sample-app`）の各ファイルが「何のためにあるか」を説明できる
    - 会員 API に小さな機能を追加し、単体テストと API テストを書ける
    - コードレビューで、よくある誤り（`==` での文字列比較、例外の握りつぶしなど）を指摘できる

## 前提

- [10 環境構築](../10-setup/index.md) を終え、サンプルアプリがローカルで起動できること
- Java の文法を一度は学んだことがあること（この章群は「おさらい」と「つまずきやすい点」に絞ります）

## 章の一覧

各章は同じ構成です。
「何か → なぜ必要か → どうやるか → サンプルアプリでは → もし〇〇がなかったら？ → 理解度チェック → コードを読むときの確認観点」の順に並んでいます。

### Java の基礎（20-01〜20-05）

| 章 | 内容 | 目安 |
| --- | --- | --- |
| [20-01 Java の基本文法おさらい](20-01-java-syntax.md) | 型、`var`、`String`、制御構文、メソッド。`==` と `equals`、`null`、桁あふれ、金額の `BigDecimal` | 0.5 日 |
| [20-02 クラスとインタフェース](20-02-class-interface.md) | カプセル化、契約としてのインタフェース（`FileFetcher`） | 0.5 日 |
| [20-03 コレクションと Stream](20-03-collections-stream.md) | `List` / `Map` / `Set`、`Optional`、Stream の基本 | 1 日 |
| [20-04 例外処理](20-04-exception.md) | 検査例外と非検査例外、業務例外、握りつぶさない | 0.5 日 |
| [20-05 record と不変オブジェクト](20-05-record-immutable.md) | `record`、`List.copyOf`、防御的コピー | 0.5 日 |

### ビルドと Spring Boot（20-06〜20-10）

| 章 | 内容 | 目安 |
| --- | --- | --- |
| [20-06 Gradle（ビルドと依存関係）](20-06-gradle.md) | `build.gradle`、Gradle Wrapper、タスク、`test` と `karateTest` | 0.5 日 |
| [20-07 Spring Boot の仕組み（DI）](20-07-spring-di.md) | Bean、コンストラクタ注入、`@Bean` | 1 日 |
| [20-08 設定ファイルとプロファイル](20-08-config-profile.md) | `application*.yml`、環境変数、秘密情報の扱い | 0.5 日 |
| [20-09 REST コントローラ](20-09-rest-controller.md) | `MemberController`、`ApiExceptionHandler` | 1 日 |
| [20-10 入力チェック（Bean Validation と業務チェック）](20-10-validation.md) | `@Valid`、`@NotBlank`、業務チェック | 0.5 日 |

### データベース（20-11〜20-13）

| 章 | 内容 | 目安 |
| --- | --- | --- |
| [20-11 SQL の基本](20-11-sql.md) | SELECT / INSERT、制約 | 1 日 |
| [20-12 MyBatis（Mapper インターフェースと XML）](20-12-mybatis.md) | Mapper インタフェースと XML の対応 | 1 日 |
| [20-13 トランザクション](20-13-transaction.md) | `@Transactional` | 0.5 日 |

### 運用とテスト、チーム開発（20-14〜20-18）

| 章 | 内容 | 目安 |
| --- | --- | --- |
| [20-14 ログ](20-14-logging.md) | ログレベル、メッセージ ID | 0.5 日 |
| [20-15 JUnit 5 と AssertJ](20-15-junit.md) | 単体テストの書き方 | 1 日 |
| [20-16 モックとテストダブル](20-16-mock.md) | テスト用の実装に差し替える | 0.5 日 |
| [20-17 Karate](20-17-karate.md) | API テスト | 0.5 日 |
| [20-18 Git フローとレビュー](20-18-git-flow-review.md) | ブランチ、プルリクエスト、レビュー | 0.5 日 |

## おすすめの進め方（2 週間）

番号順に進めるのが基本です。
ただし、前半で Java の基礎を固め、後半で Spring とテストに進むと理解がつながりやすくなります。

| 日 | 進める章 | その日の確認 |
| --- | --- | --- |
| 1 日目 | 20-01、20-02 | `FileFetcher` と `DefaultFileFetcher` の関係を説明できる |
| 2 日目 | 20-03 | `ApiExceptionHandler` の Stream を 1 行ずつ説明できる |
| 3 日目 | 20-04、20-05 | `BusinessException` が `RuntimeException` を継承する理由を説明できる |
| 4 日目 | 20-06 | `./gradlew test` を実行し、テストレポートを開ける |
| 5 日目 | 20-07 | `MemberController` に `MemberService` が渡る流れを説明できる |
| 6 日目 | 20-08、20-09 | プロファイル `local` で起動し、会員 API を curl で呼べる |
| 7 日目 | 20-10、20-11 | 入力チェックのエラー応答（400）を再現できる |
| 8 日目 | 20-12、20-13 | `MemberMapper.xml` の SQL と Java のメソッドを対応づけられる |
| 9 日目 | 20-14、20-15、20-16 | `MemberServiceTest` にテストを 1 つ追加できる |
| 10 日目 | 20-17、20-18 | Karate のシナリオを 1 つ追加し、プルリクエストを作れる |

!!! tip "詰まったら"
    30 分調べて進まないときは、質問してください。
    質問の仕方は [質問のしかた](../appendix/how-to-ask.md) を参考にしてください。

## 次に進む

基礎を終えたら [30 実ソース読解](../30-reading/index.md) に進みます。
サンプルアプリのソースを、ファイル単位で詳しく読んでいきます。

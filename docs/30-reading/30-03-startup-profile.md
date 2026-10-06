# 30-03 起動クラスとプロファイル

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `SampleApplication` が、API とバッチのどちらとして起動するかを説明できる
    - `System.exit` を `batch` プロファイルのときだけ呼ぶ理由を説明できる
    - `application.yml` と `application-<プロファイル>.yml` の重ね合わせを読める
    - 設定値が最終的にどこから来るか（ファイル・環境変数・既定値）をたどれる

## 何か

起動クラスは、アプリケーションの `main` メソッドを持つクラスです。
Spring Boot では `@SpringBootApplication` を付けたクラスが起動クラスになります。

プロファイルは、設定の組み合わせに付けた名前です。
`local`（ローカル開発）や `batch`（バッチとして起動）のように使います。
起動時に `--spring.profiles.active=local,batch` のように指定します。

プロファイルの基本は [20-08 設定ファイルとプロファイル](../20-basics/20-08-config-profile.md) で学びました。
この章では、サンプルアプリの実物を読みます。

## なぜ必要か

サンプルアプリは、1 つのプロジェクトで API とバッチの両方を動かします。
同じ jar でも、起動のしかたで振る舞いが大きく変わります。

| 起動のしかた | 振る舞い | 終わり方 |
| --- | --- | --- |
| API（既定） | Web サーバーを起動し、リクエストを待つ | 止めるまで動き続ける |
| バッチ（`batch`） | Web サーバーを起動せず、ジョブを 1 回実行する | ジョブの終了コードで終わる |

ジョブ管理の仕組み（スケジューラ）は、終了コードでジョブの成否を判断します。
そのため、バッチは「正しい終了コードで、確実に終わる」必要があります。
一方で API は、終わってはいけません。
この違いを決めているのが、起動クラスとプロファイルです。

## どうやるか

### 起動クラスを読む

起動クラスでは、次の 2 点を確かめます。

1. `SpringApplication.run` の後に、何か処理があるか
2. その処理が、どの条件で動くか

### 設定の重ね合わせを読む

Spring Boot は、設定を次の順で重ねます。
後から読んだものが、前の値を上書きします。

1. `application.yml`（共通）
2. `application-<プロファイル>.yml`（有効なプロファイルの分。複数なら指定順）
3. 環境変数・起動引数（`--キー=値`）

さらに、値の中の `${環境変数名:既定値}` は、環境変数があればその値、無ければ既定値になります。

### 終了コードの返し方を読み分ける

!!! failure "悪い例"
    ```java
    // 例: ジョブの中で直接 System.exit を呼ぶ
    public void run(ApplicationArguments args) {
        // ... 取込処理 ...
        System.exit(4);
    }
    ```
    Spring の終了処理（DB 接続の後片付けなど）を飛ばしてプロセスが終わります。
    また、テストから `run` を呼ぶと、テストの JVM ごと終わってしまいます。

!!! success "良い例"
    <!-- src: sample-app/src/main/java/com/example/sample/SampleApplication.java#L16-L21 @exercise-base -->
    ```java title="sample-app/src/main/java/com/example/sample/SampleApplication.java" linenums="16"
        public static void main(String[] args) {
            ConfigurableApplicationContext ctx = SpringApplication.run(SampleApplication.class, args);
            if (ctx.getEnvironment().matchesProfiles("batch")) {
                System.exit(SpringApplication.exit(ctx));
            }
        }
    ```
    ジョブは終了コードを `ExitCodeGenerator` で返すだけにします。
    `System.exit` は起動クラスの 1 か所だけで、`batch` のときだけ呼びます。

## サンプルアプリでは

### 起動クラス

<!-- src: sample-app/src/main/java/com/example/sample/SampleApplication.java#L7-L14 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/SampleApplication.java" linenums="7"
/**
 * サンプルアプリの起動クラス.
 *
 * <p>既定は API（Web サーバー）として起動する。プロファイル batch を付けるとバッチとして起動し、
 * ジョブの終了コードでプロセスを終える。
 */
@SpringBootApplication
public class SampleApplication {
```

- 17 行目の `SpringApplication.run` で、Spring のコンテナ（Bean の入れ物）を起動します
- 18 行目で、有効なプロファイルに `batch` が含まれるかを調べます
- 19 行目の `SpringApplication.exit(ctx)` は、コンテナを閉じ、`ExitCodeGenerator` の Bean から終了コードを集めて返します
- その値を `System.exit` に渡して、プロセスの終了コードにします

`batch` が無いときは、`main` はそのまま終わります。
Web サーバーのスレッドが動き続けるので、プロセスは終わらずリクエストを待ちます。

### 終了コードを返す側

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java#L22-L24 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java" linenums="22"
@Component
@ConditionalOnProperty(name = "app.batch.job", havingValue = "JOB0001")
public class OrderImportJob implements ApplicationRunner, ExitCodeGenerator {
```

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java#L62-L65 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java" linenums="62"
    @Override
    public int getExitCode() {
        return exitCode;
    }
```

`run` の中で `exitCode` に 0・4・8 のいずれかを入れます（26〜28 行目、46・55・58 行目）。
詳しくは [30-13](30-13-batch-exit-code.md) で読みます。
ここでは「終了コードを決めるのはジョブ、プロセスを終わらせるのは起動クラス」という分担を押さえます。

### 設定ファイル

<!-- src: sample-app/src/main/resources/application.yml @exercise-base -->
```yaml title="sample-app/src/main/resources/application.yml"
# 共通設定. 環境ごとの値は application-<プロファイル>.yml と環境変数で上書きする
spring:
  application:
    name: sample-app
  messages:
    basename: messages
    encoding: UTF-8
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/sampledb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:}
mybatis:
  mapper-locations: classpath:mapper/*.xml
  configuration:
    map-underscore-to-camel-case: true
server:
  port: ${SERVER_PORT:8080}
```

<!-- src: sample-app/src/main/resources/application-local.yml @exercise-base -->
```yaml title="sample-app/src/main/resources/application-local.yml"
# ローカル開発（local/docker-compose.yml の DB と S3 エミュレータに接続）
spring:
  datasource:
    password: ${DB_PASSWORD:localpass}
app:
  s3:
    endpoint: ${S3_ENDPOINT:http://localhost:9090}
logging:
  level:
    com.example.sample: DEBUG
```

<!-- src: sample-app/src/main/resources/application-batch.yml @exercise-base -->
```yaml title="sample-app/src/main/resources/application-batch.yml"
# バッチとして起動する（Web サーバーを立てず、ジョブが終わったら終了する）
spring:
  main:
    web-application-type: none
```

3 つのファイルの役割は、次のとおりです。

| ファイル | 役割 | 主な値 |
| --- | --- | --- |
| `application.yml` | 全環境の共通の値 | DB の接続先、メッセージ、MyBatis、ポート |
| `application-local.yml` | ローカル開発だけの値 | DB のパスワードの既定値、S3 エミュレータの URL、DEBUG ログ |
| `application-batch.yml` | バッチ起動だけの値 | Web サーバーを立てない |

`application.yml` の `password` の既定値は空です（11 行目）。
本番のパスワードをファイルに書かず、環境変数で渡す前提だからです。
`local` のときだけ、ローカルの DB 用の既定値 `localpass` が使われます。

### 起動コマンドとの対応

`dev-environment/local/README.md` の起動コマンドと、上の読み取りを対応づけます。

```bash
# API
./gradlew bootRun --args='--spring.profiles.active=local'
# バッチ
./gradlew bootRun --args='--spring.profiles.active=local,batch --app.batch.job=JOB0001 --input=s3://sample-bucket/orders.csv'
```

バッチのコマンドでは、3 つの指定がそろって初めてジョブが動きます。

| 指定 | 効く場所 |
| --- | --- |
| `batch` プロファイル | `application-batch.yml`（Web サーバー無し）と `SampleApplication` 18 行目 |
| `--app.batch.job=JOB0001` | `OrderImportJob` 23 行目の `@ConditionalOnProperty` |
| `--input=...` | `OrderImportJob` 43 行目の `args.getOptionValues("input")` |

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `SampleApplication` | 起動クラス。API とバッチで jar やクラスが分かれていることも多い |
| `batch` プロファイル | バッチ用の起動設定（プロファイル、起動スクリプト、ジョブ定義） |
| `ExitCodeGenerator` と 0 / 4 / 8 | 運用設計書の終了コード体系と、ジョブ管理側の判定条件 |
| `application-local.yml` | 環境ごとの設定ファイル（`-dev`、`-stg`、`-prod` など）と、その置き場所 |
| `${DB_PASSWORD:}` | 秘密情報の渡し方（環境変数、秘密情報の管理サービス）。ファイルに直書きされていないか |
| `--app.batch.job=JOB0001` | ジョブの起動引数の定義（ジョブ管理側の設定） |

実案件では、起動スクリプトやジョブ管理側の定義も読みます。
アプリのコードだけでは、本番でどのプロファイルが有効かが分からないからです。

## もし System.exit の条件分岐がなかったら？

`System.exit` が無いと、バッチの終了コードは `ExitCodeGenerator` の値になりません。
ジョブが形式エラーを検出しても、スケジューラには正常終了と区別できない形で伝わります。
障害に気づくのが遅れます。

逆に、条件分岐無しで常に `System.exit` を呼ぶと、API が起動した直後に終了してしまいます。
`main` の 1 つの `if` が、API とバッチの両方を正しく動かしています。
なお、`main` を通る経路は単体テストでは確かめていません。
変更するときは、API とバッチの両方を手で起動して確かめます。

## 理解度チェック

**問 1.** `SpringApplication.exit(ctx)` は何をして、何を返しますか。

??? note "答え"
    コンテナを閉じ、`ExitCodeGenerator` の Bean から終了コードを集めて返します。
    サンプルアプリでは `OrderImportJob.getExitCode()` の値が返ります。

**問 2.** `batch` プロファイルで Web サーバーが起動しないのは、どの設定のためですか。

??? note "答え"
    `application-batch.yml` の `spring.main.web-application-type: none` のためです。

**問 3.** `local` プロファイルで、環境変数 `DB_PASSWORD` が無いとき、DB のパスワードは何になりますか。

??? note "答え"
    `localpass` です。
    `application.yml` 11 行目の値を、`application-local.yml` 4 行目が上書きし、その既定値が使われます。

**問 4.** ジョブの中で直接 `System.exit` を呼ばない理由を 2 つ挙げてください。

??? note "答え"
    Spring の終了処理を飛ばしてしまうことと、テストから `run` を呼ぶとテストの JVM ごと終わってしまうことです。

## コードを読むときの確認観点

- [ ] `SpringApplication.run` の後の処理と、その条件を確かめたか
- [ ] `System.exit` を呼ぶ場所が 1 か所に限られているか
- [ ] 有効なプロファイルごとに、どの設定ファイルが読まれるかを説明できるか
- [ ] `${...:既定値}` の既定値が、本番で使われても安全な値か
- [ ] パスワードなどの秘密情報が、共通の設定ファイルに書かれていないか

## 演習

1. `--spring.profiles.active=local` だけで起動しました。
   Web サーバーは起動しますか。`System.exit` は呼ばれますか。待ち受けるポートは何番ですか。
   それぞれ根拠の行を示して答えなさい。
2. バッチを `--spring.profiles.active=local,batch --input=s3://sample-bucket/orders.csv` で起動しました（`--app.batch.job` を付け忘れています）。
   何が起き、終了コードはいくつになりますか。行を示して説明しなさい。
   また、この動きの問題点を 1 つ挙げなさい。
3. `local` と `batch` の両方を有効にしたとき、`com.example.sample` パッケージのログレベルは何になりますか。
   根拠のファイルと行を示しなさい。
4. `SampleApplication.main` の `if` を外し、常に `System.exit(SpringApplication.exit(ctx))` を呼ぶように変えました。
   API として起動すると何が起きますか。また、`./gradlew test` で落ちるテストはありますか。

解答は [30-03 解答](answers/30-03.md) にあります。

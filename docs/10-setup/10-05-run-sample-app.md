# 10-05 sample-app のビルドと実行

!!! abstract "到達目標"
    - `./gradlew build` でビルドと単体テストを実行し、結果の見方を説明できる
    - プロファイル `local` で API を起動し、`curl` で呼び出せる
    - プロファイル `batch` でバッチ（JOB0001）を起動し、ログと終了コードを確認できる
    - 単体テスト（`test`）と API テスト（`karateTest`）の違いを説明できる

## 何か

sample-app は、教材と動作確認のための小さなアプリです。1 つのプロジェクトに次の 2 つが同居しています。

| 種類 | ID | 内容 |
|---|---|---|
| API | API0001 / API0002 | 会員の照会（`GET /api/v1/members/{id}`）と登録（`POST /api/v1/members`） |
| バッチ | JOB0001 | 注文ファイル（CSV）を S3 から読み、`orders` テーブルに取り込む |

どちらとして起動するかは **プロファイル** で切り替えます。
プロファイルとは、設定のまとまりに付けた名前で、起動時に `--spring.profiles.active=...` で選びます。

| プロファイル | 設定ファイル | 意味 |
|---|---|---|
| （共通） | `application.yml` | すべての起動で読む共通設定 |
| `local` | `application-local.yml` | ローカルの DB と S3 エミュレータに接続する |
| `batch` | `application-batch.yml` | Web サーバーを立てず、ジョブが終わったら終了する |

ビルドには **Gradle Wrapper**（`gradlew`）を使います。
決められた版の Gradle を自動で取得して動かすスクリプトで、Gradle 本体のインストールは不要です。

## なぜ必要か

- 教材の「30 実ソース読解」では、動かしながらコードを読みます。まず動く状態を作っておく必要があります
- ビルド・起動・テストのコマンドは、実案件でも毎日使います。ここで手に覚えさせます
- 「動かしたら何が出れば正しいか」を知っておくと、自分の変更で壊したときにすぐ気づけます

## どうやるか

以降のコマンドは、特に断りが無ければ Git Bash で `sample-app` フォルダにいる前提です。
PowerShell の場合は `./gradlew` を `.\gradlew.bat` に読み替えてください。

!!! info "事前に"
    [10-04](10-04-docker-local.md) の手順で、`docker compose ps` が `db` と `s3` の `healthy` を示していることを確認してください。

### 0. 教材用のブランチに切り替える

教材は、弱いところを直す前のコードを残した `exercise-base` ブランチで進めます（理由は [30 実ソース読解](../30-reading/index.md#exercise-base)）。

```bash
cd /c/work/dev-environment
git switch exercise-base
```

### 1. ビルドする

```bash
cd /c/work/dev-environment/sample-app
./gradlew build
```

初回は Gradle 本体と依存ライブラリのダウンロードがあるため、数分かかります。
最後に `BUILD SUCCESSFUL` と出れば OK です。

`build` は、コンパイル・単体テスト・jar の作成をまとめて行います。
単体テストは DB を使わないので、コンテナが止まっていても通ります。

| 生成物 | 場所 |
|---|---|
| 実行用の jar | `build/libs/sample-app-0.1.0.jar` |
| テスト結果 | `build/reports/tests/test/index.html` |
| カバレッジ（JaCoCo） | `build/reports/jacoco/test/html/index.html` |

!!! failure "悪い例"
    `BUILD FAILED` の最後の数行だけを見て、検索を始める。
    本当の原因は、たいてい出力の上のほう（最初の `error:` や `FAILED`）に書かれています。

!!! success "良い例"
    出力を上から読み、最初に出たエラーを探す。テストの失敗なら `build/reports/tests/test/index.html` を開いて、どのテストのどのアサーションで落ちたかを確認する。

### 2. API を起動する

```bash
./gradlew bootRun --args='--spring.profiles.active=local'
```

PowerShell の場合は、引数全体をダブルクォートで囲みます。

```powershell
.\gradlew.bat bootRun --args="--spring.profiles.active=local"
```

ログに `Started SampleApplication` と出れば起動完了です。
このターミナルは API が動いている間は使えません。止めるときは `Ctrl + C` を押します。

### 3. API を呼び出す

**別のターミナル** を開き、`curl` で呼び出します。

```bash
curl http://localhost:8080/api/v1/members/1
```

会員 1 の JSON（`id`・`name`・`email`）が返れば OK です。

続けて、会員を登録します。

```bash
curl -i -X POST http://localhost:8080/api/v1/members \
     -H 'Content-Type: application/json' \
     -d '{"name":"新規 会員","email":"new@example.com"}'
```

`-i` を付けるとステータスとヘッダーも表示されます。
`HTTP/1.1 201`、`Location: /api/v1/members/<採番された ID>`、登録した会員の JSON が返れば OK です。

同じコマンドをもう一度実行すると、メールアドレスが重複するため `409` とエラーの JSON が返ります。

```json
{"messageId":"APPE0003","message":"このメールアドレスは既に登録されています（new@example.com）。","details":[]}
```

!!! tip "PowerShell で curl を使うとき"
    Windows PowerShell 5.1 の `curl` は、別のコマンド（`Invoke-WebRequest`）の別名です。
    `curl.exe` と拡張子まで書くと、Windows 11 に標準で入っている curl が動きます。
    JSON を渡すコマンドは引用符の扱いが複雑になるため、Git Bash で実行するのがおすすめです。

### 4. バッチを起動する

API を `Ctrl + C` で止めてから（止めなくても動きますが、ログが混ざらないように）、バッチを起動します。
入力の CSV は、[10-04](10-04-docker-local.md) の `upload-sample` で S3 エミュレータに置いたものです。

```bash
./gradlew bootRun --args='--spring.profiles.active=local,batch --app.batch.job=JOB0001 --input=s3://sample-bucket/orders.csv'
```

| 引数 | 意味 |
|---|---|
| `--spring.profiles.active=local,batch` | ローカルの接続先で、バッチとして起動する |
| `--app.batch.job=JOB0001` | 実行するジョブを選ぶ |
| `--input=s3://sample-bucket/orders.csv` | 入力ファイルの場所 |

ログに次の行が出れば OK です。

```text
APPI0002 JOB0001 終了 imported=3 duplicated=0 errors=1
```

CSV の 4 行目は数量が 0 のため、形式エラーとして飛ばされます（`APPW0001` の警告ログが出ます）。
もう一度実行すると `imported=0 duplicated=3` になります。再実行しても同じ注文が二重に入らないことを確かめられます。

### 5. 終了コードを確認する

バッチは、結果を **終了コード** で呼び出し元に伝えます。

| 終了コード | 意味 |
|---|---|
| 0 | 正常 |
| 4 | 形式エラーの行あり（取込は続行） |
| 8 | 異常終了 |

`bootRun` 経由だと、終了コードが 0 以外のとき Gradle が `BUILD FAILED` と
`finished with non-zero exit value 4` を表示します。今回は形式エラーの行があるので、これが想定どおりの結果です。

終了コードそのものを確かめたいときは、jar を直接起動します。

```bash
./gradlew bootJar
java -jar build/libs/sample-app-0.1.0.jar --spring.profiles.active=local,batch \
     --app.batch.job=JOB0001 --input=s3://sample-bucket/orders.csv
echo $?        # PowerShell なら: $LASTEXITCODE
```

`4` と表示されれば OK です。

### 6. テストを実行する

```bash
./gradlew test          # 単体テスト（DB・S3 不要）
./gradlew karateTest    # API テスト（API を起動した状態で）
```

| タスク | 何を確かめるか | 必要なもの | 結果の場所 |
|---|---|---|---|
| `test` | クラス単位のロジック（JUnit 5・Mockito・AssertJ・MockMvc） | なし | `build/reports/tests/test/index.html` |
| `karateTest` | 起動中の API に HTTP で問い合わせた結果（Karate） | API・DB の起動 | `build/karate-reports/` |

`karateTest` は、別のターミナルで手順 2 の API を起動してから実行します。

### 日常の流れ

| タイミング | すること |
|---|---|
| 始業時 | Rancher Desktop を起動 → `docker compose up -d --wait` → `git pull` |
| 実装中 | `./gradlew test` をこまめに、API は `bootRun` で確認 |
| push 前 | `./gradlew build`、API を変えたら `karateTest` も |
| 終業時 | `docker compose stop` |

## サンプルアプリでは

起動クラス `sample-app/src/main/java/com/example/sample/SampleApplication.java` は、プロファイルで動きを変えています。

<!-- src: sample-app/src/main/java/com/example/sample/SampleApplication.java @main -->
```java
public static void main(String[] args) {
    ConfigurableApplicationContext ctx = SpringApplication.run(SampleApplication.class, args);
    if (ctx.getEnvironment().matchesProfiles("batch")) {
        System.exit(SpringApplication.exit(ctx));
    }
}
```

`batch` プロファイルのときだけ、アプリを終了して終了コードを返します。
`application-batch.yml` の `web-application-type: none` で、Web サーバーも立ち上げません。

ジョブ本体は `sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java` です。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @main -->
```java
@Component
@ConditionalOnProperty(name = "app.batch.job", havingValue = "JOB0001")
public class OrderImportJob implements BatchJob, ApplicationRunner, ExitCodeGenerator {
```

- `@ConditionalOnProperty`: `--app.batch.job=JOB0001` を渡したときだけ、このクラスが有効になります。API として起動したときは動きません
- `BatchJob`: ジョブ ID（`JOB0001`）を返すバッチの共通インタフェースです。ジョブ ID の誤りや指定漏れは `BatchJobGuard` が見つけ、終了コード 8 にします
- `ApplicationRunner`: 起動の最後に `run` メソッドが呼ばれます
- `ExitCodeGenerator`: `getExitCode` の値が、`SpringApplication.exit` の戻り値（終了コード）になります

テストの切り分けは `sample-app/build.gradle` にあります。

<!-- src: sample-app/build.gradle @main -->
```groovy
tasks.named('test') {
    useJUnitPlatform {
        excludeTags 'karate'
    }
    finalizedBy jacocoTestReport
}
```

`@Tag("karate")` の付いた `src/test/java/karate/ApiKarateTest.java` は、`test` から除外され、`karateTest` でだけ実行されます。
これにより、`./gradlew build` は DB を起動していなくても通ります。
起動の仕組みは [起動とプロファイル](../30-reading/30-03-startup-profile.md)、終了コードは [バッチの終了コード](../30-reading/30-13-batch-exit-code.md) で詳しく読みます。

## もしプロファイルがなかったら？

ローカル用・クラウド用・バッチ用の設定を 1 つのファイルに書き、起動のたびに書き換えることになります。
書き換えたままコミットしてしまい、クラウドの環境がローカルの接続先を見に行く、といった事故が起きます。

API とバッチも別のプロジェクトに分けるか、起動方法を毎回手で変える必要が出てきます。
プロファイルを使えば、同じ jar のまま、起動引数だけで動きを安全に切り替えられます。
設定の仕組みは [設定とプロファイル](../20-basics/20-08-config-profile.md) で学びます。

## 理解度チェック

1. `./gradlew build` が DB を起動していなくても成功するのはなぜですか。
2. API として起動したときに、JOB0001 が動かないのはどの仕組みによるものですか。
3. バッチを `bootRun` で実行したら `BUILD FAILED` と出ました。ログには `errors=1` があります。これは異常ですか。
4. `karateTest` を実行する前に必要なことは何ですか。
5. 同じ CSV でバッチを 2 回実行すると、`imported` と `duplicated` はどうなりますか。

??? note "答え"
    1. 単体テストは DB を使わない作りで、DB が必要な Karate のテストは `excludeTags 'karate'` で `test` から除外されているからです。
    2. `OrderImportJob` の `@ConditionalOnProperty` です。`app.batch.job=JOB0001` が無いとクラスが有効になりません。
    3. 異常ではありません。形式エラーの行があると終了コード 4 になり、Gradle は 0 以外の終了コードを失敗として表示します。
    4. DB を起動し、別のターミナルで API を `bootRun --args='--spring.profiles.active=local'` で起動しておくことです。
    5. 2 回目は `imported=0 duplicated=3` になります。取り込み済みの注文は二重に登録されません。

## コードを読むときの確認観点

- [ ] 起動に必要なプロファイルと引数が、README やクラスのコメントに書かれているか
- [ ] バッチのクラスが、API の起動時に誤って動かない条件（`@ConditionalOnProperty` など）を持っているか
- [ ] 終了コードの意味（0 / 4 / 8）がコードとドキュメントで一致しているか
- [ ] 単体テストが外部（DB・S3）に依存していないか。依存するテストはタグで分けているか
- [ ] 変更後に `./gradlew build` が通ることを確認したか

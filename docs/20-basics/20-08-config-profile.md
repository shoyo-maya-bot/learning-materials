# 20-08 設定ファイルとプロファイル

!!! abstract "到達目標"
    - `application.yml` と `application-<プロファイル>.yml` の関係を説明できる
    - プロファイルを指定してアプリを起動できる
    - `${環境変数:既定値}` の書き方を読み、設定値が決まる順番を説明できる
    - パスワードなどの秘密情報を yml に書いてはいけない理由を説明できる

## 何か

### 設定ファイル

Spring Boot は、`src/main/resources/application.yml` から設定を読みます。
DB の接続先、サーバーのポート番号、ログレベルなど、環境によって変わる値を書きます。
YAML（ヤムル）は、インデント（字下げ）で階層を表す書き方です。

例:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/sampledb
```

これは `spring.datasource.url` という 1 つの設定項目を表します。

### プロファイル

プロファイルは、設定の組み合わせに付ける名前です（`local`、`batch` など）。
プロファイル `local` を有効にすると、`application.yml` に加えて `application-local.yml` も読まれます。
同じ項目があれば、プロファイル側の値が優先されます。

### プレースホルダ

`${DB_URL:jdbc:postgresql://...}` は「環境変数などの `DB_URL` があればその値、無ければ `:` の後ろの既定値」という意味です。
`${DB_PASSWORD:}` のように `:` の後ろが空なら、既定値は空文字です。

## なぜ必要か

同じアプリを、ローカル、開発環境、本番で動かします。
DB の接続先やパスワードは環境ごとに違います。
値をコードに直書きすると、環境ごとにコードを変えてビルドし直すことになります。

設定をファイルと環境変数に出せば、同じ jar のまま、設定だけを変えて各環境で動かせます。

ただし、パスワードなどの秘密情報を yml に書いて Git に入れると、リポジトリを見られる全員に漏れます。
履歴に残るので、後から消しても取り消せません。

## どうやるか

### 値が決まる順番

同じ項目が複数の場所にあるとき、上ほど優先されます（主なもの）。

| 優先 | 場所 | 例 |
| --- | --- | --- |
| 高 | コマンドライン引数 | `--server.port=9000` |
| ↓ | OS の環境変数 | `SERVER_PORT=9000` |
| ↓ | `application-<プロファイル>.yml` | `application-local.yml` |
| 低 | `application.yml` | |

環境変数では、項目名を大文字にし、`.` を `_` に変えた名前も使えます。
例: `spring.datasource.password` は `SPRING_DATASOURCE_PASSWORD` で上書きできます。
正確な順番は [Spring Boot: Externalized Configuration](https://docs.spring.io/spring-boot/reference/features/external-config.html) で確認できます。

### プロファイルを指定して起動する

例:

```bash
# Gradle から起動
./gradlew bootRun --args='--spring.profiles.active=local'

# 環境変数で指定
SPRING_PROFILES_ACTIVE=local ./gradlew bootRun
```

複数のプロファイルは `local,batch` のように `,` でつなぎます。
同じ項目があれば、後ろに書いたプロファイルが優先されます。

### 秘密情報は環境変数から

!!! failure "悪い例"
    ```yaml
    # 例: 本番のパスワードを yml に直書きして Git に入れる
    spring:
      datasource:
        password: Prod-Secret-1234
    ```

!!! success "良い例"
    ```yaml
    # 例: 値は環境変数から。既定値は空にする
    spring:
      datasource:
        password: ${DB_PASSWORD:}
    ```

本番の環境変数は、クラウドの秘密情報の管理サービスなどから渡します。
ローカルでは、Git に入れないファイル（`.env` など）やシェルで設定します。
「ローカル専用で外部につながらない値」以外は、yml に書きません。

### 設定値をコードで受け取る

例:

```java
@Value("${app.s3.region:ap-northeast-1}") String region
```

`@Value` で 1 項目ずつ受け取れます。
`:` の後ろに既定値を書けば、設定が無いときも起動できます。
既定値を書かない場合、設定が無いと起動時にエラーになります。必須の設定は、あえて既定値を書かないのも手です。

## サンプルアプリでは

### 共通設定（application.yml）

`sample-app/src/main/resources/application.yml`

```yaml
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

- DB の接続先・ユーザー・パスワードは環境変数で上書きできます
- パスワードの既定値は空です。本番のパスワードは書かれていません
- `spring.messages.basename: messages` で、`messages.properties` をメッセージの本文として読みます
- `map-underscore-to-camel-case` は、DB の列名 `order_no` を Java の `orderNo` に対応させる指定です

### ローカル用（application-local.yml）

`sample-app/src/main/resources/application-local.yml`

```yaml
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

- ローカルの Docker で動く DB 専用のパスワードを既定値にしています。外部につながらないので許容しています
- `app.s3.endpoint` を指定すると、`S3Config` が S3 エミュレータへ接続します
- 自分のパッケージのログを `DEBUG` まで出します

### バッチ用（application-batch.yml）

`sample-app/src/main/resources/application-batch.yml`

```yaml
# バッチとして起動する（Web サーバーを立てず、ジョブが終わったら終了する）
spring:
  main:
    web-application-type: none
```

`sample-app/src/main/java/com/example/sample/SampleApplication.java`

```java
if (ctx.getEnvironment().matchesProfiles("batch")) {
    System.exit(SpringApplication.exit(ctx));
}
```

プロファイル `batch` では Web サーバーを起動しません。
ジョブが終わると、ジョブの終了コードでプロセスを終えます。
起動例は `OrderImportJob` のコメントにあります。

```text
--spring.profiles.active=local,batch --app.batch.job=JOB0001 --input=s3://sample-bucket/orders.csv
```

`local` と `batch` を組み合わせ、`app.batch.job` でどのジョブを動かすかを指定しています。

### 設定が無いときの切り替え（S3Config）

`sample-app/src/main/java/com/example/sample/order/batch/S3Config.java`

```java
@Value("${app.s3.endpoint:}") String endpoint,
// ...
if (endpoint.isBlank()) {
    b.credentialsProvider(DefaultCredentialsProvider.builder().build());
} else {
    b.endpointOverride(URI.create(endpoint))
    // ...（エミュレータ向けの固定の認証情報）
}
```

`app.s3.endpoint` はプロファイル `local` でだけ設定されます。
クラウドでは未設定なので、IAM ロール（クラウドが自動で渡す認証情報）を使います。
アクセスキーを設定ファイルに書かずに済む作りです。

## もし〇〇がなかったら？

もしプロファイルがなければ、ローカル用と本番用で別々の jar を作るか、起動のたびに設定ファイルを手で書き換えることになります。
書き換え忘れで、ローカルの PC から本番の DB に接続してしまう事故も起こりえます。

もし秘密情報を yml に書いて Git に入れていたら、リポジトリの閲覧者全員がパスワードを知ることになります。
履歴から消すのは難しく、結局パスワードの変更と、影響を受ける全環境の設定の入れ替えが必要になります。

## 理解度チェック

1. 環境変数 `DB_URL` を設定せずに起動したとき、`spring.datasource.url` は何になりますか。

    ??? note "答え"
        既定値の `jdbc:postgresql://localhost:5432/sampledb` です。

2. プロファイル `local` で起動したとき、DB のパスワードはどう決まりますか（環境変数 `DB_PASSWORD` は未設定とします）。

    ??? note "答え"
        `application-local.yml` の既定値 `localpass` です。
        `application.yml` の `${DB_PASSWORD:}` より、プロファイル側の値が優先されます。

3. プロファイル `batch` を付けて起動すると、何が変わりますか。2 つ挙げてください。

    ??? note "答え"
        Web サーバーを起動しないこと（`web-application-type: none`）。
        処理が終わるとジョブの終了コードでプロセスを終えること（`SampleApplication`）です。

4. 本番のパスワードを yml に書いてはいけない理由を答えてください。

    ??? note "答え"
        Git に入るとリポジトリの閲覧者全員に漏れ、履歴に残って取り消せないためです。
        環境変数や秘密情報の管理サービスから渡します。

## コードを読むときの確認観点

- [ ] yml に本番のパスワード・アクセスキー・トークンが書かれていないか
- [ ] 環境で変わる値が、コードに直書きされていないか
- [ ] プレースホルダの既定値が、本番で使われても安全な値か
- [ ] 新しい設定項目を足したとき、どのプロファイル・環境変数で設定するかが分かるか
- [ ] ローカル専用の設定が `application.yml`（共通）に入っていないか

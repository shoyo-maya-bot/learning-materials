# 30-12 ファイルの取得（S3）

!!! abstract "到達目標"
    - `FileFetcher` インタフェースを挟む理由を説明できる
    - `DefaultFileFetcher` が `s3://バケット/キー` を分解して読む流れを読める
    - `S3Config` が、ローカル（エミュレータ）とクラウドで接続先と認証を切り替える仕組みを説明できる
    - ローカルの S3 エミュレータにファイルを置き、バッチから読ませられる

## 何か

**S3**（Amazon S3）は、クラウド上にファイルを置いておくストレージのサービスです。
ファイルは **バケット**（入れ物）と **キー**（入れ物の中での名前）で特定します。
`s3://sample-bucket/orders.csv` なら、バケットが `sample-bucket`、キーが `orders.csv` です。

JOB0001 は、取込む注文ファイルを S3 から読みます。
ローカルではクラウドにつながず、S3 と同じ使い方ができる **エミュレータ**（模倣するソフト）をコンテナで動かします。

この章で読むのは、次の 3 つのクラスと、ローカル環境の設定です。

| クラス | 役割 |
|---|---|
| `FileFetcher` | 「場所を渡すと、行の一覧が返る」という約束（インタフェース） |
| `DefaultFileFetcher` | その約束の実装。S3 かローカルファイルかを見分けて読む |
| `S3Config` | S3 に接続する部品（`S3Client`）を作る設定 |

## なぜ必要か

ファイルの取得は、業務ロジックとは別の関心ごとです。
「どこから読むか」が業務ロジックに混ざっていると、次のような困りごとが起きます。

- 単体テストのたびに S3（やエミュレータ）が必要になる
- 読み込み元を S3 から別の場所に変えるとき、業務ロジックまで直すことになる
- ローカルとクラウドで接続先が違うだけなのに、コードを書き分けることになる

sample-app では、取得をインタフェースの向こうに隠し、接続先の違いは設定で吸収しています。

## どうやるか

外部とのやり取りは、**インタフェースで包み、実装を差し替えられるようにする** のが基本です。

!!! failure "悪い例"
    例: ジョブの中で直接 `S3Client` を作って読む。

    ```java
    // 例: sample-app には無いコード
    S3Client s3 = S3Client.builder().endpointOverride(URI.create("http://localhost:9090")).build();
    List<String> lines = /* s3.getObject(...) を読む */;
    ```

    接続先がコードに埋め込まれ、クラウドでは動きません。テストでも S3 が必要になります。

!!! success "良い例"
    ジョブは `FileFetcher` だけを知り、`S3Client` は設定クラスで作って DI（依存性の注入）で渡す。
    テストでは `FileFetcher` をラムダに置き換える。

## サンプルアプリでは

### 約束（インタフェース）

```java title="sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java（6〜10 行目）"
/** 入力ファイルを行の並びとして読む（s3:// とローカルパスを同じ形で扱う）. */
public interface FileFetcher {

    List<String> readLines(String location) throws IOException;
}
```

メソッドが 1 つだけなので、テストではラムダで書けます（`OrderImportJobTest.java` 17 行目の `loc -> List.of(...)`）。

### 実装

```java title="sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java（17〜44 行目）"
@Component
public class DefaultFileFetcher implements FileFetcher {

    private final S3Client s3;

    public DefaultFileFetcher(S3Client s3) {
        this.s3 = s3;
    }

    @Override
    public List<String> readLines(String location) throws IOException {
        if (!location.startsWith("s3://")) {
            return Files.readAllLines(Path.of(location), StandardCharsets.UTF_8);
        }
        String rest = location.substring("s3://".length());
        int slash = rest.indexOf('/');
        if (slash <= 0 || slash == rest.length() - 1) {
            throw new IllegalArgumentException("s3://バケット/キー の形式で指定してください: " + location);
        }
        GetObjectRequest req = GetObjectRequest.builder()
                .bucket(rest.substring(0, slash))
                .key(rest.substring(slash + 1))
                .build();
        try (ResponseInputStream<GetObjectResponse> in = s3.getObject(req);
                BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            return reader.lines().toList();
        }
    }
}
```

- 22〜24 行目: `S3Client` をコンストラクタで受け取ります。作るのは `S3Config` です
- 28〜30 行目: `s3://` で始まらなければ、ローカルのファイルとして UTF-8 で読みます
- 31〜32 行目: `s3://` を取り除き、最初の `/` の位置を探します
- 33〜35 行目: `/` が無い・先頭にある（バケット名が空）・末尾にある（キーが空）なら、形式の誤りとします
- 36〜39 行目: `/` の前をバケット、後ろをキーにします。キーに `/` が含まれても構いません（`inbound/orders.csv` など）
- 40〜43 行目: try-with-resources（`try (...)`）で、読み終わったら必ずストリームを閉じます

BOM は、ここでは取り除きません。取り除くのは `OrderImportService` の見出しの確認です（30-10）。

### 接続先と認証の切り替え

```java title="sample-app/src/main/java/com/example/sample/order/batch/S3Config.java（20〜39 行目）"
@Configuration
public class S3Config {

    @Bean
    public S3Client s3Client(
            @Value("${app.s3.region:ap-northeast-1}") String region,
            @Value("${app.s3.endpoint:}") String endpoint,
            @Value("${app.s3.access-key:test}") String accessKey,
            @Value("${app.s3.secret-key:test}") String secretKey) {
        S3ClientBuilder b = S3Client.builder().region(Region.of(region));
        if (endpoint.isBlank()) {
            b.credentialsProvider(DefaultCredentialsProvider.builder().build());
        } else {
            b.endpointOverride(URI.create(endpoint))
                    .forcePathStyle(true)
                    .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(accessKey, secretKey)));
        }
        return b.build();
    }
}
```

`@Value("${キー:既定値}")` は、設定の値を受け取り、無ければ `:` の後ろの既定値を使う書き方です。

| 条件 | 接続先 | 認証情報 |
|---|---|---|
| `app.s3.endpoint` が空（クラウド） | 本物の S3 | `DefaultCredentialsProvider`（実行環境の IAM ロールなど、標準の探し方） |
| `app.s3.endpoint` あり（ローカル） | 指定した URL（エミュレータ） | 固定の値（既定は `test` / `test`） |

`forcePathStyle(true)` は、`http://localhost:9090/バケット/キー` のように、バケット名を URL のパスに入れる形式にする指定です。
既定の形式はバケット名をホスト名に入れる（`バケット.ホスト`）ので、`localhost` のエミュレータでは名前解決できません。

`app.s3.endpoint` は、`local` プロファイルでだけ設定されます。

```yaml title="sample-app/src/main/resources/application-local.yml（5〜7 行目）"
app:
  s3:
    endpoint: ${S3_ENDPOINT:http://localhost:9090}
```

### ローカルの S3 エミュレータ

```yaml title="local/docker-compose.yml（25〜32 行目を抜粋。「（省略）」の部分は実物を見てください）"
  s3:
    # S3 互換のエミュレータ。チームで別の製品を使う場合は .env の S3_EMULATOR_IMAGE で差し替える
    image: ${S3_EMULATOR_IMAGE:-（省略）}
    environment:
      （省略）: ${S3_BUCKET:-sample-bucket}
      initialBuckets: ${S3_BUCKET:-sample-bucket}
    ports:
      - "${S3_PORT:-9090}:9090"
```

既定のイメージ名と、製品固有の環境変数名は、ここでは省略しています。
`environment` の 2 行は、どちらも「起動時にバケット `sample-bucket` を作る」ための設定です。

ファイルを置くスクリプトは、AWS CLI を使わず、`curl` で PUT するだけです。

```bash title="local/scripts/upload-sample.sh（5〜8 行目）"
BUCKET="${S3_BUCKET:-sample-bucket}"
PORT="${S3_PORT:-9090}"
curl -sf -X PUT --upload-file data/orders.csv "http://localhost:${PORT}/${BUCKET}/orders.csv"
echo "uploaded: s3://${BUCKET}/orders.csv"
```

7 行目の URL も、バケット名がパスに入る形式です。`S3Config` の `forcePathStyle(true)` と対応しています。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| `FileFetcher` | ファイル取得・ストレージ操作の共通部品（インタフェース） |
| `S3Config` の `endpoint` 分岐 | 環境ごとの接続先の切り替え（プロファイル別の設定ファイル、環境変数） |
| `DefaultCredentialsProvider` | クラウドの実行環境に付けた権限（ロール）。権限の申請先も確認する |
| `access-key: test` | ローカル専用のダミーの認証情報。本物の鍵をソースや設定に書いていないか確認する |
| `s3://sample-bucket/orders.csv` | 本番・検証環境のバケット名とキーの命名規則（運用設計書） |
| `upload-sample.sh` | テストデータを置く手順・スクリプト |

!!! warning "大きなファイルに注意"
    `readLines` は、ファイル全体を `List<String>` としてメモリに読み込みます。
    数十万行を超えるファイルでは、メモリ不足になるおそれがあります。
    実案件では、1 行ずつ流して処理する作りになっているかを確認してください。

## もし FileFetcher がなかったら？

`OrderImportJob` が `S3Client` を直接使っていたら、`OrderImportJobTest` は S3 なしでは動きません。
テストのたびにエミュレータを起動し、ファイルを置く必要があります。CI（自動テストの仕組み）でも同じ準備が要ります。

また、「`--input` にローカルパスを渡して手元のファイルで試す」こともできなくなります。
1 つのインタフェースを挟むだけで、テストのしやすさと動かしやすさが大きく変わります。

## 理解度チェック

1. `OrderImportJob` は `S3Client` を直接使っていますか。

    ??? note "答え"
        使っていません。`OrderImportJob` が受け取るのは `FileFetcher` だけです（`OrderImportJob.java` 36 行目のコンストラクタ）。
        `S3Client` を使うのは `DefaultFileFetcher` だけです。

2. クラウドで動かすとき、S3 の認証情報はどこから来ますか。

    ??? note "答え"
        `app.s3.endpoint` が空なので、`DefaultCredentialsProvider` が実行環境の標準の場所（環境変数や実行環境に付けたロールなど）から探します（`S3Config.java` 30〜31 行目）。
        ソースや設定ファイルに鍵は書きません。

3. `--input=s3://sample-bucket/inbound/orders.csv` のとき、バケットとキーはそれぞれ何になりますか。

    ??? note "答え"
        バケットは `sample-bucket`、キーは `inbound/orders.csv` です。最初の `/` で分けるので、キーに `/` が含まれても構いません。

4. `forcePathStyle(true)` が、ローカルでだけ設定されているのはなぜですか。

    ??? note "答え"
        エミュレータは `localhost` で動くので、バケット名をホスト名に入れる形式では名前解決できないからです。
        本物の S3 では既定の形式で問題ないので、設定していません。

## コードを読むときの確認観点

- [ ] 外部（ストレージ・API・DB）とのやり取りが、インタフェースで包まれているか確認したか
- [ ] 接続先・認証情報が、どの設定・環境変数で切り替わるか確認したか
- [ ] ローカル用の値（ダミーの鍵・エミュレータの URL）が、本番の設定に漏れていないか確認したか
- [ ] 文字コードと、ファイルの大きさ（メモリに全部読むか）を確認したか
- [ ] 読み込みに失敗したとき（ファイルが無い・権限が無い）の例外と、その受け止め先を確認したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **動きを予想する**: `--input=s3://sample-bucket/` で JOB0001 を起動すると、どのファイルの何行目で何が起き、終了コードはいくつになりますか。
2. **動きを予想する**: アップロードしていないキー `--input=s3://sample-bucket/nothing.csv` を指定すると、終了コードはいくつですか。その例外はどこで受け止められますか。
3. **場所を探す**: `OrderImportJobTest` が S3 もエミュレータも無しで動くのはなぜですか。根拠となるコードの場所を 2 つ答えてください。
4. **小さな変更**: ポート 9090 が他のソフトと衝突したので、`local/.env` の `S3_PORT` を `9190` に変えて `docker compose up -d --wait` しました。バッチを動かすまでに、ほかに何を合わせる必要がありますか（2 つ）。
5. **場所を探す**: 本番環境で、間違って `app.s3.endpoint` に値が設定されていたら、何が起きると考えられますか。関係する行を答えてください。

解答: [30-12 解答](answers/30-12.md)

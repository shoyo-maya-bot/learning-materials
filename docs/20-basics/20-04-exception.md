# 20-04 例外処理

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 検査例外と非検査例外の違いを説明できる
    - 業務例外（`BusinessException` / `NotFoundException`）の役割を説明できる
    - 例外を握りつぶすコードを見つけ、直し方を説明できる
    - try-with-resources でリソースを確実に閉じるコードを書ける

## 何か

例外は「処理を続けられない事態」を、呼び出し元に知らせる仕組みです。
`throw` で投げ、`try` / `catch` で受け取ります。
受け取らなかった例外は、呼び出し元へ順にさかのぼって伝わります。

### 検査例外と非検査例外

| 種類 | 親クラス | 特徴 | 例 |
| --- | --- | --- | --- |
| 検査例外（checked） | `Exception` | `catch` するか `throws` で宣言しないとコンパイルエラー | `IOException` |
| 非検査例外（unchecked） | `RuntimeException` | 宣言は不要 | `IllegalArgumentException`、`NullPointerException` |

検査例外は「呼び出し側が対処を考えるべき失敗」（ファイルが無い等）に使われます。
非検査例外は「プログラムの誤り」や「上位でまとめて扱う失敗」に使われます。

### 業務例外

業務例外は「プログラムは正しいが、業務のルール上続けられない」ことを表す例外です。
例: 会員が見つからない、メールアドレスが登録済み。
多くのプロジェクトでは、`RuntimeException` を継承した自前のクラスを用意します。

## なぜ必要か

例外がなければ、失敗を戻り値（`-1` や `null`）で知らせることになります。
呼び出し側が確認を忘れると、失敗したまま処理が進みます。

例外を使えば、確認を忘れても処理は止まります。
さらに、例外を 1 か所でまとめて受け取り、応答（エラー画面や API のエラー応答）に変換できます。
各メソッドがエラー応答を作る必要がなくなります。

ただし、例外を `catch` して何もしない（握りつぶす）と、この利点がすべて失われます。

## どうやるか

### 例外を握りつぶさない

!!! failure "悪い例"
    ```java
    // 例: 失敗しても何も起きなかったように見える
    try {
        lines = fetcher.readLines(location);
    } catch (IOException e) {
        // 何もしない
    }
    ```
    原因がログにも残らず、後続で `lines` が `null` のまま使われます。

!!! failure "悪い例"
    ```java
    // 例: メッセージだけ残し、スタックトレースと原因を捨てている
    try {
        lines = fetcher.readLines(location);
    } catch (IOException e) {
        log.error("読込失敗: " + e.getMessage());
        return List.of();
    }
    ```
    空のリストを返すので、呼び出し側は「0 件だった」と区別できません。

!!! success "良い例"
    ```java
    // 例: 対処できないなら、原因（cause）を付けて投げ直す
    try {
        lines = fetcher.readLines(location);
    } catch (IOException e) {
        throw new UncheckedIOException("入力ファイルを読めません: " + location, e);
    }
    ```

対処できる場所でだけ `catch` します。対処できないなら、そのまま上に伝えます。
投げ直すときは、元の例外を第 2 引数（cause）に渡し、原因をたどれるようにします。

### catch の範囲は狭く

`catch (Exception e)` は、想定外の例外（プログラムの誤り）まで受け取ってしまいます。
受け取るのは、想定している例外の型に絞ります。
例外的に `Exception` を受け取ってよいのは、バッチの最上位のように「何が起きても終了コードを決める」場所です。

### リソースは try-with-resources で閉じる

ファイルやネットワークの接続は、使い終わったら閉じる必要があります。
`try (...)` の括弧の中で開くと、例外が起きても必ず閉じられます。

例:

```java
try (BufferedReader reader = Files.newBufferedReader(path)) {
    return reader.lines().toList();
}
```

### 業務例外はメッセージ ID を持たせる

業務例外には、利用者向けの文言そのものではなく、メッセージ ID（文言を引くためのキー）を持たせます。
文言は設定ファイルで管理し、変更や多言語化をしやすくします。

## サンプルアプリでは

### 業務例外の階層

`sample-app/src/main/java/com/example/sample/common/BusinessException.java`

<!-- src: sample-app/src/main/java/com/example/sample/common/BusinessException.java @exercise-base -->
```java
/** 業務エラー. メッセージ ID（messages.properties のキー）と埋め込み値を持つ. */
public class BusinessException extends RuntimeException {

    private final String messageId;
    private final transient Object[] args;

    public BusinessException(String messageId, Object... args) {
        super(messageId);
        this.messageId = messageId;
        this.args = args.clone();
    }
    // ...（getMessageId() / getArgs()）
}
```

`sample-app/src/main/java/com/example/sample/common/NotFoundException.java`

<!-- src: sample-app/src/main/java/com/example/sample/common/NotFoundException.java @exercise-base -->
```java
/** 対象データが存在しない. */
public class NotFoundException extends BusinessException {
```

- `RuntimeException` を継承しているので、途中のメソッドに `throws` を書かずに済みます
- `NotFoundException` は `BusinessException` の一種です（継承）
- メッセージ ID と埋め込み値（`args`）を持ち、文言は `messages.properties` から引きます

### 投げる側

`sample-app/src/main/java/com/example/sample/member/MemberService.java`

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java @exercise-base -->
```java
if (mapper.existsByEmail(normalized)) {
    throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
}
```

サービスは「登録済みである」と知らせるだけです。HTTP のステータスは知りません。

### まとめて受け取る側

`sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java`

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java @exercise-base -->
```java
@ExceptionHandler(NotFoundException.class)
public ResponseEntity<ErrorResponse> notFound(NotFoundException e) {
    return body(HttpStatus.NOT_FOUND, e.getMessageId(), e.getArgs(), List.of());
}

@ExceptionHandler(BusinessException.class)
public ResponseEntity<ErrorResponse> business(BusinessException e) {
    log.warn("business error: {}", e.getMessageId());
    return body(HttpStatus.CONFLICT, e.getMessageId(), e.getArgs(), List.of());
}
```

`NotFoundException` は 404、その他の `BusinessException` は 409 に変換されます。
`NotFoundException` は `BusinessException` の子ですが、Spring はより具体的な型のハンドラを選びます。
詳しくは [20-09 REST コントローラ](20-09-rest-controller.md) で扱います。

### 検査例外と原因の引き継ぎ

`sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java @exercise-base -->
```java
List<String> readLines(String location) throws IOException;
```

ファイルの読み込みは失敗しうるので、検査例外 `IOException` を宣言しています。

`sample-app/src/main/java/com/example/sample/order/OrderImportService.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java @exercise-base -->
```java
private static long parseLong(String value, String name) {
    try {
        return Long.parseLong(value.trim());
    } catch (NumberFormatException e) {
        throw new IllegalArgumentException(name + " が数値ではありません", e);
    }
}
```

`NumberFormatException` を、項目名入りの分かりやすいメッセージに変えています。
第 2 引数に `e` を渡しているので、元の原因も失われません。
呼び出し元の `importLines` は、この例外を `catch` して「行番号: 理由」としてエラー一覧に残し、次の行へ進みます。
握りつぶしているのではなく、結果として記録している点に注目してください。

### try-with-resources

`sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java @exercise-base -->
```java
try (ResponseInputStream<GetObjectResponse> in = s3.getObject(req);
        BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
    return reader.lines().toList();
}
```

S3 からの入力を読み終えたら、例外の有無にかかわらず閉じられます。

### 最上位で Exception を受け取る

`sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @exercise-base -->
```java
} catch (Exception e) {
    log.error("JOB0001 異常終了", e);
    exitCode = ERROR;
}
```

バッチの最上位なので、どんな例外でも終了コード 8 にしてプロセスを終えます。
`log.error` の最後の引数に `e` を渡し、スタックトレースをログに残しています。

## もし〇〇がなかったら？

もし例外を握りつぶしていたら、バッチは「正常終了（終了コード 0）」で終わり、注文は 1 件も取り込まれません。
運用者は異常に気づかず、翌日に利用者からの問い合わせで初めて発覚します。
ログにも何も残っていないので、原因の調査は再現から始めることになります。

もし業務例外とハンドラの仕組みがなければ、各コントローラが `try` / `catch` でエラー応答を組み立てます。
コントローラごとにステータスや形式がばらつき、API の利用者が混乱します。

## 理解度チェック

1. `BusinessException` が `Exception` ではなく `RuntimeException` を継承しているのはなぜですか。

    ??? note "答え"
        非検査例外にして、途中のメソッドに `throws` を書かずに済ませるためです。
        業務例外は `ApiExceptionHandler` で 1 か所にまとめて受け取ります。

2. 例外を投げ直すときに、元の例外を第 2 引数に渡すのはなぜですか。

    ??? note "答え"
        原因（cause）をたどれるようにするためです。
        ログのスタックトレースに「Caused by」として元の例外が出ます。

3. `importLines` が `IllegalArgumentException` を `catch` して続行するのは、握りつぶしではないのはなぜですか。

    ??? note "答え"
        行番号と理由をエラー一覧に記録し、結果（`ImportResult`）として返しているためです。
        ジョブはエラーがあれば終了コード 4 にし、警告ログにも出します。

4. 次のコードの問題点を 2 つ挙げてください。
   `try { ... } catch (Exception e) { return null; }`

    ??? note "答え"
        `Exception` という広い型で受け取り、想定外の誤りまで隠していること。
        原因を記録せず `null` を返し、呼び出し側で別の例外を招くことです。

## コードを読むときの確認観点

- [ ] 空の `catch`、またはログだけで続行する `catch` がないか
- [ ] 投げ直すとき、元の例外を cause に渡しているか
- [ ] `catch (Exception e)` が最上位以外で使われていないか
- [ ] ファイルや接続を try-with-resources で閉じているか
- [ ] 業務エラーに業務例外とメッセージ ID を使っているか（文言を直書きしていないか）
- [ ] ログに例外オブジェクト（`e`）を渡し、スタックトレースを残しているか

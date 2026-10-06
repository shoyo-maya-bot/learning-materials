# 30-04 共通の例外とエラー応答

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `BusinessException` と `NotFoundException` の役割と継承関係を説明できる
    - `ApiExceptionHandler` が、どの例外をどの HTTP ステータスに変換するかを読める
    - エラー応答 `ErrorResponse` の 3 つの項目が、どこから来るかを説明できる
    - 共通の例外処理で扱っていない例外を見つけられる

## 何か

API のエラー処理は、次の 3 つの部品でできています。

| 部品 | 種類 | 役割 |
| --- | --- | --- |
| `BusinessException` / `NotFoundException` | 例外クラス | 業務上の失敗を、メッセージ ID と埋め込み値つきで表す |
| `ErrorResponse` | `record` | 利用者に返すエラー応答の形（JSON） |
| `ApiExceptionHandler` | 例外ハンドラ | 例外を受け取り、ステータスと `ErrorResponse` に変換する |

例外ハンドラとは、コントローラから投げられた例外を、まとめて受け取る仕組みです。
Spring では `@RestControllerAdvice` と `@ExceptionHandler` で書きます。

例外の基本は [20-04 例外処理](../20-basics/20-04-exception.md) で学びました。

## なぜ必要か

エラー応答の形が API ごとに違うと、呼び出す側が API ごとに処理を書き分けることになります。
共通の部品にまとめると、次の利点があります。

- すべての API が、同じ形（`messageId`、`message`、`details`）でエラーを返す
- サービスは「何が起きたか」を例外で表すだけでよく、HTTP を知らなくてよい
- ステータスの決め方を 1 か所で変えられる

## どうやるか

### 投げる側と受け取る側を対で読む

エラー処理は、投げる場所と受け取る場所が離れています。
次の順で対にして読みます。

1. 例外クラスの定義を読む（何を持っているか）
2. `throw new` で検索し、投げる場所を一覧にする
3. `@ExceptionHandler` を読み、例外の型ごとの変換を表にする
4. 表に無い例外が投げられていないかを確かめる

```bash
# 例: 業務例外を投げている場所の一覧
grep -rn "throw new .*Exception" src/main/java
```

### 継承関係に注意する

`@ExceptionHandler` は、投げられた例外に「最も近い型」のハンドラを選びます。
子クラスの例外に専用のハンドラがあれば、親クラスのハンドラより優先されます。

!!! failure "悪い例"
    ```java
    // 例: コントローラごとに例外を捕まえて、応答を手で組み立てる
    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable("id") long id) {
        try {
            return ResponseEntity.ok(service.get(id));
        } catch (NotFoundException e) {
            return ResponseEntity.status(404).body(Map.of("error", "not found"));
        }
    }
    ```
    API ごとに応答の形がばらつき、メッセージ ID も付きません。

!!! success "良い例"
    <!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java#L31-L34 @exercise-base -->
    ```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="31"
        @GetMapping("/{id}")
        public Member get(@PathVariable("id") long id) {
            return service.get(id);
        }
    ```
    コントローラは例外を捕まえません。
    変換は `ApiExceptionHandler` の 1 か所に任せます。

## サンプルアプリでは

### 例外クラス

<!-- src: sample-app/src/main/java/com/example/sample/common/BusinessException.java#L3-L13 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/BusinessException.java" linenums="3"
/** 業務エラー. メッセージ ID（messages.properties のキー）と埋め込み値を持つ. */
public class BusinessException extends RuntimeException {

    private final String messageId;
    private final transient Object[] args;

    public BusinessException(String messageId, Object... args) {
        super(messageId);
        this.messageId = messageId;
        this.args = args.clone();
    }
```

- `RuntimeException`（非検査例外）を継承しているので、`throws` を書かずに投げられます
- `messageId` は `messages.properties` のキーです（[30-05](30-05-message-ids.md) で読みます）
- `args` はメッセージの `{0}` などに埋め込む値です
- `args.clone()`（12 行目、20 行目）は防御的コピーです。外から配列を書き換えられないようにします
- `transient` は「直列化（バイト列への変換）の対象から外す」という印です。例外は直列化できる決まりですが、`Object[]` の中身が直列化できるとは限らないからです

<!-- src: sample-app/src/main/java/com/example/sample/common/NotFoundException.java#L3-L4 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/NotFoundException.java" linenums="3"
/** 対象データが存在しない. */
public class NotFoundException extends BusinessException {
```

`NotFoundException` は `BusinessException` の子クラスです。
中身は親と同じで、「存在しない」という種類を型で区別するためだけにあります。

### エラー応答

<!-- src: sample-app/src/main/java/com/example/sample/common/ErrorResponse.java#L5-L12 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/ErrorResponse.java" linenums="5"
/**
 * API のエラー応答.
 *
 * @param messageId メッセージ ID（例: APPE0001）
 * @param message 利用者向けメッセージ
 * @param details 入力チェックの項目別エラー（無ければ空）
 */
public record ErrorResponse(String messageId, String message, List<String> details) {}
```

JSON にすると、例えば次の形になります。

```json
{"messageId": "APPE0002", "message": "会員が見つかりません（会員ID: 42）。", "details": []}
```

### 例外ハンドラ

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java#L26-L49 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java" linenums="26"
    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<ErrorResponse> notFound(NotFoundException e) {
        return body(HttpStatus.NOT_FOUND, e.getMessageId(), e.getArgs(), List.of());
    }

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> business(BusinessException e) {
        log.warn("business error: {}", e.getMessageId());
        return body(HttpStatus.CONFLICT, e.getMessageId(), e.getArgs(), List.of());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> invalid(MethodArgumentNotValidException e) {
        List<String> details = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .sorted()
                .toList();
        return body(HttpStatus.BAD_REQUEST, MessageIds.INVALID_INPUT, new Object[0], details);
    }

    private ResponseEntity<ErrorResponse> body(HttpStatus status, String id, Object[] args, List<String> details) {
        String text = messages.getMessage(id, args, id, Locale.JAPANESE);
        return ResponseEntity.status(status).body(new ErrorResponse(id, text, details));
    }
```

読み取った変換を表にします。

| 例外 | ハンドラ | ステータス | `messageId` | `details` | ログ |
| --- | --- | --- | --- | --- | --- |
| `NotFoundException` | `notFound`（26〜29 行目） | 404 | 例外が持つ ID | 空 | 出さない |
| `BusinessException`（上記以外） | `business`（31〜35 行目） | 409 | 例外が持つ ID | 空 | WARN で ID だけ |
| `MethodArgumentNotValidException` | `invalid`（37〜44 行目） | 400 | `APPE0001` 固定 | 「項目名: 理由」を並べ替えたもの | 出さない |

ポイントは次の 3 つです。

- `NotFoundException` は `BusinessException` でもありますが、より近い型の `notFound` が選ばれます
- `body` の `messages.getMessage(id, args, id, ...)` の 3 つ目の引数は既定値です。本文が見つからないと、ID そのものが `message` になります
- `invalid` の `.sorted()` で、`details` の順番を毎回同じにしています。入力チェックの結果の順番は決まっていないからです

### 表に無い例外

`ApiExceptionHandler` が扱うのは、上の 3 種類だけです。
それ以外の例外は、Spring Boot の既定のエラー処理に任されます。
その場合、応答は `ErrorResponse` の形になりません。

| 例 | 起きる場面 | 扱い |
| --- | --- | --- |
| `GET /api/v1/members/abc` | パスの値を `long` に変換できない | `ApiExceptionHandler` では扱わない |
| 壊れた JSON の `POST` | 本文を `RegisterRequest` に変換できない | `ApiExceptionHandler` では扱わない |
| DB の一意制約違反など | 想定外の実行時例外 | `ApiExceptionHandler` では扱わない（500） |

これはサンプルを小さく保つための割り切りです。
実案件では、共通の例外処理がどこまで扱っているかを、必ず確かめます。

### テストでの確かめ方

`MemberControllerTest` は、コントローラと例外ハンドラを組み合わせて確かめています。

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java#L31-L34 @exercise-base -->
```java title="sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java" linenums="31"
        mvc = MockMvcBuilders.standaloneSetup(new MemberController(service))
                .setControllerAdvice(new ApiExceptionHandler(messages))
                .setValidator(validator)
                .build();
```

404 は `notFoundReturns404WithMessageId`（51〜57 行目）、400 は `invalidInputReturns400`（59〜67 行目）で確かめています。
409 は単体テストでは確かめておらず、`members.feature` の「同じメールアドレスは登録できない」（20〜30 行目）で確かめています。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `BusinessException` / `NotFoundException` | 共通の業務例外クラスの階層（共通部品・フレームワークにあることが多い） |
| `ErrorResponse` | API 設計書のエラー応答の形（項目名、必須かどうか） |
| `ApiExceptionHandler` | `@RestControllerAdvice` や共通のフィルタ。複数あるときは優先順位も |
| 404 / 409 / 400 の対応表 | API 設計書の「エラー時のステータス一覧」 |
| 表に無い例外（500 など） | 想定外の例外の扱い（ログ、障害通知、利用者向けの文言） |

## もし共通の例外ハンドラがなかったら？

コントローラごとに例外を捕まえ、応答を組み立てることになります。
API ごとに応答の形や、同じ失敗に対するステータスがばらつきます。
呼び出す側は API ごとにエラー処理を書き分ける必要があり、不具合の元になります。

また、例外を捕まえ忘れた API では、内部の情報を含む既定のエラー応答が返ることがあります。
共通の例外ハンドラは、エラー応答の品質を 1 か所で保つための仕組みです。

## 理解度チェック

**問 1.** `NotFoundException` を投げると、`notFound` と `business` のどちらが呼ばれますか。

??? note "答え"
    `notFound` です。
    `@ExceptionHandler` は、投げられた例外に最も近い型のハンドラを選ぶからです。

**問 2.** `messages.properties` に本文が無いメッセージ ID で例外を投げると、`message` はどうなりますか。

??? note "答え"
    メッセージ ID そのものになります。
    `body` の `getMessage` の 3 つ目の引数（既定値）に `id` を渡しているからです（47 行目）。

**問 3.** 入力チェックのエラーの `details` を `.sorted()` で並べ替えているのはなぜですか。

??? note "答え"
    入力チェックの結果の順番は決まっていないので、並べ替えないと応答が毎回変わりうるからです。
    順番を揃えると、テストや画面表示が安定します。

**問 4.** `BusinessException` の `args` を `clone()` しているのはなぜですか。

??? note "答え"
    防御的コピーのためです。
    呼び出し元が渡した配列を後から書き換えても、例外の中身が変わらないようにしています。

## コードを読むときの確認観点

- [ ] 例外クラスの継承関係を図にしたか
- [ ] `@ExceptionHandler` ごとに「例外 → ステータス → メッセージ ID → ログ」の表を作ったか
- [ ] 業務で投げている例外が、すべて表のどれかに当てはまるか
- [ ] 表に無い例外（型変換、JSON の不正、DB の例外）のときの応答を確かめたか
- [ ] ログに個人情報（メールアドレスなど）を出していないか

## 演習

1. `MemberService.get` が `NotFoundException` を投げました。
   呼ばれるハンドラ、HTTP ステータス、ログの出力の有無を、行を示して答えなさい。
2. `{"name":"","email":"not-an-email"}` を登録 API に送りました。
   応答のステータス、`messageId`、`details` の件数と並び順を、行を示して説明しなさい。
3. `ApiExceptionHandler` の `notFound` メソッド（26〜29 行目）を削除しました。
   存在しない会員を照会したときの応答はどう変わりますか。
   また、`./gradlew test` で落ちるテストを挙げなさい。
4. `GET /api/v1/members/abc` の応答は、`ErrorResponse` の形になりますか。
   判断の根拠となるコードを示しなさい。
   また、`ErrorResponse` の形（400、`APPE0001`）で返すための修正案と、追加すべきテストを書きなさい。

解答は [30-04 解答](answers/30-04.md) にあります。

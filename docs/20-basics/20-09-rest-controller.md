# 20-09 REST コントローラ

!!! abstract "到達目標"
    - REST API の基本（URL・HTTP メソッド・ステータスコード・JSON）を説明できる
    - `@RestController` と `@GetMapping` / `@PostMapping` を使ったコントローラを書ける
    - `@RestControllerAdvice` で例外をエラー応答に変える仕組みを読める
    - `MemberController` に届いたリクエストが、応答になるまでの流れを説明できる

## 何か

### REST API

REST API は、HTTP で「リソース（会員、注文など）」を操作する API の作り方です。
次の組み合わせで表します。

| 要素 | 例 | 意味 |
| --- | --- | --- |
| URL | `/api/v1/members/1` | どのリソースか |
| HTTP メソッド | `GET`、`POST` | 何をするか（照会、登録） |
| ステータスコード | `200`、`201`、`404` | 結果はどうだったか |
| 本文（JSON） | `{"id":1,"name":"…"}` | データ |

API の設計の考え方は [50 API](../50-api/index.md) で詳しく学びます。

### REST コントローラ

REST コントローラは、HTTP リクエストを受け取り、サービスを呼び、結果を返すクラスです。
`@RestController` を付けると、メソッドの戻り値が自動で JSON に変換されます。
公式ドキュメントは [Spring Framework: Annotated Controllers](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller.html) です。

| 注釈 | 意味 |
| --- | --- |
| `@RequestMapping("/api/v1/members")` | このクラスが受け持つ URL の先頭部分 |
| `@GetMapping("/{id}")` | `GET` で受け取る。`{id}` は URL の一部を変数として受け取る |
| `@PostMapping` | `POST` で受け取る |
| `@PathVariable` | URL の `{id}` の値を引数で受け取る |
| `@RequestBody` | リクエスト本文の JSON を引数のオブジェクトに変換する |

## なぜ必要か

HTTP の受け取りと JSON の変換を毎回自分で書くと、本題の業務処理が埋もれます。
Spring がこれを肩代わりするので、コントローラは「どの URL で、何を受け取り、どのサービスを呼ぶか」だけを書けば済みます。

また、コントローラに業務ロジックを書かないことが大切です。
コントローラは HTTP の窓口、サービスは業務のルール、と役割を分けます。
こうすると、業務ロジックは HTTP なしで単体テストでき、バッチなど別の入口からも使えます。

## どうやるか

### コントローラは薄く

!!! failure "悪い例"
    ```java
    // 例: コントローラに業務ルールや DB 操作を書く
    @PostMapping
    public Product register(@RequestBody ProductRequest req) {
        if (mapper.existsByCode(req.code())) {
            return null; // 何が起きたか利用者に伝わらない
        }
        mapper.insert(req);
        ...
    }
    ```

!!! success "良い例"
    ```java
    // 例: 受け取って、サービスに任せて、返すだけ
    @PostMapping
    public ResponseEntity<Product> register(@Valid @RequestBody ProductRequest req) {
        Product created = service.register(req.code(), req.name());
        return ResponseEntity.created(URI.create("/api/v1/products/" + created.code())).body(created);
    }
    ```

### ステータスコードを正しく返す

| 場面 | ステータス |
| --- | --- |
| 照会できた | 200 OK |
| 登録できた | 201 Created（`Location` ヘッダに新しいリソースの URL） |
| 入力が不正 | 400 Bad Request |
| 対象が無い | 404 Not Found |
| 業務ルールに反する（重複など） | 409 Conflict |

!!! failure "悪い例"
    ```java
    // 例: エラーでも 200 を返し、本文にエラーを入れる
    return ResponseEntity.ok(Map.of("error", "not found"));
    ```
    利用者は本文を読まないと失敗に気づけず、監視でもエラーとして数えられません。

!!! success "良い例"
    ```java
    // 例: 業務例外を投げ、例外ハンドラで 404 にする
    throw new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id);
    ```

### 例外ハンドラにまとめる

エラー応答は、各コントローラで組み立てず、`@RestControllerAdvice` のクラスでまとめて作ります。
`@ExceptionHandler(例外クラス.class)` を付けたメソッドが、その例外を受け取って応答を返します。

## サンプルアプリでは

### MemberController

`sample-app/src/main/java/com/example/sample/member/MemberController.java`

```java
/** 会員 API（API ID: API0001 照会 / API0002 登録）. */
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {

    private final MemberService service;

    public MemberController(MemberService service) {
        this.service = service;
    }

    /** 登録の入力. */
    public record RegisterRequest(
            @NotBlank @Size(max = 50) String name, @NotBlank @Email @Size(max = 254) String email) {}

    @GetMapping("/{id}")
    public Member get(@PathVariable("id") long id) {
        return service.get(id);
    }

    @PostMapping
    public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
        Member created = service.register(req.name(), req.email());
        return ResponseEntity.created(URI.create("/api/v1/members/" + created.id())).body(created);
    }
}
```

- 照会（`GET /api/v1/members/{id}`）は `Member` をそのまま返します。ステータスは 200 です
- 登録（`POST /api/v1/members`）は `ResponseEntity.created(...)` で 201 と `Location` ヘッダを返します
- `@Valid` で `RegisterRequest` の入力チェックをします。不正なら例外になり、メソッドは呼ばれません（[20-10 入力チェック](20-10-validation.md)）
- どちらのメソッドも、サービスを呼んで返すだけです

### ApiExceptionHandler

`sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java`

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

@ExceptionHandler(MethodArgumentNotValidException.class)
public ResponseEntity<ErrorResponse> invalid(MethodArgumentNotValidException e) {
    // ...（項目別のエラーを details に集める）
    return body(HttpStatus.BAD_REQUEST, MessageIds.INVALID_INPUT, new Object[0], details);
}

private ResponseEntity<ErrorResponse> body(HttpStatus status, String id, Object[] args, List<String> details) {
    String text = messages.getMessage(id, args, id, Locale.JAPANESE);
    return ResponseEntity.status(status).body(new ErrorResponse(id, text, details));
}
```

| 例外 | ステータス | 投げる場所 |
| --- | --- | --- |
| `NotFoundException` | 404 | `MemberService.get`（会員が無い） |
| `BusinessException` | 409 | `MemberService.register`（メールアドレスが登録済み） |
| `MethodArgumentNotValidException` | 400 | Spring（`@Valid` の入力チェックに失敗） |

`body` メソッドは、メッセージ ID から `messages.properties` の文言を引き、`ErrorResponse` を作ります。
`getMessage` の第 3 引数 `id` は、文言が見つからないときの代わりの値です。

例: 会員 ID 42 が無い場合のエラー応答

```json
{"messageId":"APPE0002","message":"会員が見つかりません（会員ID: 42）。","details":[]}
```

### テストで確かめる

`sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java`

```java
@Test
void notFoundReturns404WithMessageId() throws Exception {
    mvc.perform(get("/api/v1/members/42"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.messageId").value("APPE0002"))
            .andExpect(jsonPath("$.message").value("会員が見つかりません（会員ID: 42）。"));
}
```

`MockMvc` を使い、サーバーを起動せずにコントローラと例外ハンドラの組み合わせを確かめています。
テストの書き方は [20-15 JUnit 5](20-15-junit.md) で学びます。

### リクエストから応答までの流れ

```text
GET /api/v1/members/42
  → MemberController.get(42)
  → MemberService.get(42)
  → MemberMapper.findById(42) が空の Optional を返す
  → NotFoundException を投げる
  → ApiExceptionHandler.notFound が 404 と ErrorResponse を返す
```

## もし〇〇がなかったら？

もし `ApiExceptionHandler` がなければ、`NotFoundException` は Spring の既定の処理に任されます。
API の利用者には、メッセージ ID を含まない汎用のエラー応答が返ります。
画面側は「会員が無い」のか「サーバーの障害」なのかを区別できず、利用者に正しい案内を出せません。

もしコントローラに業務ロジックを書いていたら、同じルール（メールアドレスの重複チェック）をバッチで使いたいときに、コピーするしかありません。
コピーした片方だけ直す、という食い違いが起きやすくなります。

## 理解度チェック

1. 会員の登録に成功したとき、ステータスコードと、応答に含まれるヘッダは何ですか。

    ??? note "答え"
        201 Created です。`Location` ヘッダに `/api/v1/members/{採番された ID}` が入ります。

2. `NotFoundException` は `BusinessException` の子クラスです。会員が見つからないとき、409 ではなく 404 になるのはなぜですか。

    ??? note "答え"
        Spring は、投げられた例外に最も近い型のハンドラを選ぶためです。
        `NotFoundException` 用の `notFound` メソッドが選ばれます。

3. 登録 API に `{"name":"","email":"not-an-email"}` を送ると、どのような応答になりますか。

    ??? note "答え"
        400 Bad Request で、`messageId` は `APPE0001` です。
        `details` に項目別のエラーが 2 件入ります（`MemberControllerTest.invalidInputReturns400` で確かめています）。

4. コントローラに業務ロジックを書かない理由を答えてください。

    ??? note "答え"
        業務ロジックを HTTP なしでテストでき、バッチなど別の入口からも使えるようにするためです。
        役割が分かれることで、変更の影響範囲も分かりやすくなります。

## コードを読むときの確認観点

- [ ] コントローラに業務ルールや DB 操作が書かれていないか
- [ ] 登録で 201 と `Location`、エラーで適切な 4xx を返しているか（エラーなのに 200 を返していないか）
- [ ] 入力の `@RequestBody` に `@Valid` が付いているか
- [ ] エラー応答をコントローラで個別に組み立てず、例外ハンドラに任せているか
- [ ] URL が名詞（リソース）で、操作を HTTP メソッドで表しているか

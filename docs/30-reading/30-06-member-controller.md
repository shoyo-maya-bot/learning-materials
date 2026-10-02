# 30-06 会員 API のコントローラ

!!! abstract "到達目標"
    - `MemberController` の 2 つの API の URL・入力・出力・ステータスを、行を示して説明できる
    - `RegisterRequest` の入力チェックが、どの入力をどう弾くかを読める
    - コントローラに書くこと・書かないことの線引きを説明できる
    - `MemberControllerTest` がどの部品を組み合わせて確かめているかを読める

## 何か

コントローラは、HTTP のリクエストを受け取り、サービスを呼び、結果を HTTP の応答にする部品です。
サンプルアプリの会員 API は、`MemberController` 1 つのクラスに 2 つの API があります。

| API ID | メソッドと URL | 処理 | 成功時 |
| --- | --- | --- | --- |
| API0001 | `GET /api/v1/members/{id}` | 会員の照会 | 200 と会員の JSON |
| API0002 | `POST /api/v1/members` | 会員の登録 | 201、`Location` ヘッダ、登録した会員の JSON |

REST コントローラの基本は [20-09 REST コントローラ](../20-basics/20-09-rest-controller.md)、
入力チェックは [20-10 入力チェック](../20-basics/20-10-validation.md) で学びました。

## なぜ必要か

コントローラは、外部との「境界」です。
ここを読むと、API の利用者から見た仕様（URL、入力、出力、ステータス）が分かります。
逆に、業務のルールはサービスにあるべきなので、コントローラが薄いかどうかは設計の良し悪しの目安になります。

## どうやるか

### 4 つの観点で読む

コントローラは、メソッドごとに次の 4 つを読み取ります。

| 観点 | 見る場所 |
| --- | --- |
| URL とメソッド | クラスの `@RequestMapping` + メソッドの `@GetMapping` / `@PostMapping` |
| 入力 | `@PathVariable`、`@RequestBody`、`@RequestParam` と、その型 |
| 入力チェック | `@Valid` と、入力の型に付いた `@NotBlank` などの注釈 |
| 出力 | 戻り値の型、`ResponseEntity` のステータスとヘッダ |

### 業務ロジックが混ざっていないかを見る

!!! failure "悪い例"
    ```java
    // 例: コントローラで正規化と重複チェックをする
    @PostMapping
    public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
        String email = req.email().trim().toLowerCase(Locale.ROOT);
        if (mapper.existsByEmail(email)) {
            return ResponseEntity.status(409).build();
        }
        // ...
    }
    ```
    同じルールをバッチなど別の入口から使えません。
    サービスの単体テストでも確かめられなくなります。

!!! success "良い例"
    ```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="36"
        @PostMapping
        public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
            Member created = service.register(req.name(), req.email());
            return ResponseEntity.created(URI.create("/api/v1/members/" + created.id())).body(created);
        }
    ```
    コントローラは、入力の形のチェック、サービスの呼び出し、応答の組み立てだけをします。

## サンプルアプリでは

ファイルは `sample-app/src/main/java/com/example/sample/member/MemberController.java` です。

### クラスの宣言とコンストラクタ（16〜25 行目）

```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="16"
/** 会員 API（API ID: API0001 照会 / API0002 登録）. */
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {

    private final MemberService service;

    public MemberController(MemberService service) {
        this.service = service;
    }
```

- `@RestController`: 戻り値を JSON にして応答の本文にするコントローラです
- `@RequestMapping("/api/v1/members")`: このクラスのすべての API の URL の先頭です。`v1` は API の版です
- コンストラクタ注入: Spring が `MemberService` の Bean を渡します。`final` なので後から差し替えられません
- Javadoc の API ID は、設計書の API 一覧と結びつける手がかりです

### 登録の入力（27〜29 行目）

```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="27"
    /** 登録の入力. */
    public record RegisterRequest(
            @NotBlank @Size(max = 50) String name, @NotBlank @Email @Size(max = 254) String email) {}
```

入力の JSON は、この `record` に変換されます。
注釈ごとの意味は次のとおりです。

| 項目 | 注釈 | 弾く入力 |
| --- | --- | --- |
| `name` | `@NotBlank` | `null`、空文字、空白だけ |
| `name` | `@Size(max = 50)` | 51 文字以上 |
| `email` | `@NotBlank` | `null`、空文字、空白だけ |
| `email` | `@Email` | メールアドレスの形でないもの（空文字は弾かない） |
| `email` | `@Size(max = 254)` | 255 文字以上 |

`@Email` は、空文字を「チェック対象外」として通します。
空文字を弾いているのは `@NotBlank` です。
最大長の 50 と 254 は、テーブルの列の長さと揃っています（`local/db/init/01_schema.sql` の `VARCHAR(50)`、`VARCHAR(254)`）。

`RegisterRequest` はコントローラの中に入れ子で定義されています。
この入力の形は、この API だけで使うからです。

### 照会（31〜34 行目）

```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="31"
    @GetMapping("/{id}")
    public Member get(@PathVariable("id") long id) {
        return service.get(id);
    }
```

- URL の `{id}` を、`long` の引数 `id` に変換します
- 戻り値が `Member` なので、成功時は 200 で、`Member` の JSON が本文になります
- 存在しないときは、サービスが投げた `NotFoundException` が 404 になります（[30-04](30-04-error-response.md)）

### 登録（36〜40 行目）

- `@Valid`: `RegisterRequest` の入力チェックを実行します。違反があると 400 になります
- `@RequestBody`: リクエストの本文（JSON）を `RegisterRequest` に変換します
- `ResponseEntity.created(...)`: ステータス 201 と、`Location` ヘッダ（作られた会員の URL）を設定します
- `.body(created)`: 登録した会員（採番された ID を含む）を本文にします

正規化（空白の除去、小文字化）と重複チェックは、コントローラではなくサービスにあります（[30-07](30-07-member-service.md)）。

### テスト

```java title="sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java" linenums="24"
    @BeforeEach
    void setUp() {
        StaticMessageSource messages = new StaticMessageSource();
        messages.addMessage("APPE0002", Locale.JAPANESE, "会員が見つかりません（会員ID: {0}）。");
        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();
        MemberService service = new MemberService(new MemberServiceTest.InMemoryMapper());
        mvc = MockMvcBuilders.standaloneSetup(new MemberController(service))
                .setControllerAdvice(new ApiExceptionHandler(messages))
                .setValidator(validator)
                .build();
    }
```

このテストは Spring を起動せず（`standaloneSetup`）、必要な部品を手で組み立てています。

| 部品 | テストでの中身 |
| --- | --- |
| コントローラ | 本物の `MemberController` |
| サービス | 本物の `MemberService` |
| Mapper | DB を使わない `MemberServiceTest.InMemoryMapper` |
| 例外ハンドラ | 本物の `ApiExceptionHandler`（本文は `StaticMessageSource`） |
| 入力チェック | `LocalValidatorFactoryBean` |

テストメソッドは 3 つです。

| テスト | 確かめていること |
| --- | --- |
| `registerThenGet`（37〜49 行目） | 登録で 201、`Location`、`id` が 1。続けて照会で 200 とメールアドレス |
| `notFoundReturns404WithMessageId`（51〜57 行目） | 存在しない ID で 404、`APPE0002` と本文 |
| `invalidInputReturns400`（59〜67 行目） | 空の氏名と不正なメールアドレスで 400、`APPE0001`、`details` が 2 件 |

DB を使った確認は、`members.feature` の API テストで行います（[30-15](30-15-read-karate.md) で読みます）。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `@RequestMapping("/api/v1/members")` | API 設計書の URL 一覧と版の規則 |
| Javadoc の API ID | API 一覧の ID。コードのどこに ID が書かれているか（注釈、定数、コメント） |
| `RegisterRequest` と注釈 | 項目定義書（必須、桁数、形式）。独自の入力チェックの注釈があることも多い |
| 201 と `Location` | API 設計書の成功時のステータスとヘッダ |
| `MemberControllerTest` | コントローラの単体テスト（Spring を起動するか、しないか） |
| 認証・認可が無い | 実案件ではほぼ必ずある。どこで誰を確かめているか（フィルタ、注釈） |

## もしコントローラと入力チェックの分担がなかったら？

入力チェックが無いと、空の氏名や形の崩れたメールアドレスがサービスまで届きます。
サービスや DB で想定外の例外になり、利用者には 500 が返ります。
どの項目が悪いのかも伝わりません。

逆に、業務のルールまでコントローラに書くと、同じルールを他の入口から使えなくなります。
ルールが複数の場所にコピーされ、片方だけ直す不具合が起きます。

## 理解度チェック

**問 1.** 会員の照会 API で、成功時のステータスが 200 になるのはなぜですか。

??? note "答え"
    戻り値がそのまま `Member` で、`ResponseEntity` でステータスを指定していないからです。
    `@RestController` のメソッドが値を返すと、既定で 200 になります。

**問 2.** 登録 API の `Location` ヘッダは、どの行で、どんな値になりますか。

??? note "答え"
    39 行目の `ResponseEntity.created(URI.create("/api/v1/members/" + created.id()))` で、
    `/api/v1/members/` に採番された ID を付けた値になります。

**問 3.** `email` が空文字のとき、違反になる注釈はどれですか。

??? note "答え"
    `@NotBlank` だけです。
    `@Email` は空文字をチェック対象外として通します。

**問 4.** `MemberControllerTest` で、DB を使わずに済んでいるのはなぜですか。

??? note "答え"
    `MemberService` に、DB を使わない `MemberServiceTest.InMemoryMapper` を渡しているからです（30 行目）。

## コードを読むときの確認観点

- [ ] URL・HTTP メソッド・成功時のステータスが、API 設計書と一致しているか
- [ ] `@RequestBody` の引数に `@Valid` が付いているか
- [ ] 入力の最大長などが、テーブルの列の定義と揃っているか
- [ ] コントローラに業務のルール（正規化、重複チェック、計算）が入り込んでいないか
- [ ] 成功・入力エラー・業務エラーのそれぞれに、テストがあるか

## 演習

1. 登録 API が成功したときの「ステータス」「`Location` ヘッダ」「本文」を、それぞれ決めている行を示して説明しなさい。
2. `{"name":"","email":""}` を登録 API に送りました。
   `details` は何件になりますか。どの項目のどの注釈の違反かを示して答えなさい。
3. 氏名が 50 文字で、その前後に空白が 1 つずつ付いた入力（全体で 52 文字）を送りました。
   登録は成功しますか。コントローラとサービスの行を示して説明しなさい。
4. `register` の戻り値を `ResponseEntity.ok(created)` に書き換えました。
   落ちるテストを、`./gradlew test` で実行されるものと `karateTest` で実行されるものに分けて挙げなさい。
5. `register` の引数から `@Valid` を消しました。
   `invalidInputReturns400` と同じ入力を送ると、何が起きますか。また、どのテストが落ちますか。

解答は [30-06 解答](answers/30-06.md) にあります。

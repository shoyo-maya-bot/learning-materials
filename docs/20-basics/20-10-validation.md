# 20-10 入力チェック（Bean Validation と業務チェック）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 形式チェックと業務チェックの違いを説明できる
    - Bean Validation のアノテーションを使って、API の入力チェックを書ける
    - 入力エラーが 400 応答（メッセージ ID 付き）になるまでの流れを読める
    - バッチ（CSV）の入力チェックがどこで行われているかを読める

## 何か

入力チェックとは、外から来たデータを処理する前に「使ってよい値か」を確かめることです。
入力チェックは大きく 2 種類に分けられます。

| 種類 | 確かめること | どこで行うか | 例 |
|---|---|---|---|
| 形式チェック | 値だけで判断できること（必須・桁数・形式） | Controller（Bean Validation） | 氏名が空でない、メールアドレスの形 |
| 業務チェック | DB や他のデータを見ないと判断できないこと | Service | メールアドレスが登録済みでない |

**Bean Validation**（ビーン バリデーション）は、Java の標準仕様です。
クラスの項目にアノテーション（`@NotBlank` など）を付けるだけで、形式チェックを宣言できます。
Spring Boot では `spring-boot-starter-validation` を依存に入れると使えます。

よく使うアノテーションは次のとおりです。

| アノテーション | 意味 |
|---|---|
| `@NotNull` | null でない |
| `@NotBlank` | null でも空文字でも空白だけでもない（文字列用） |
| `@Size(max = 50)` | 文字数（コレクションなら要素数）が範囲内 |
| `@Email` | メールアドレスの形 |
| `@Min` / `@Max` | 数値の下限・上限 |
| `@Pattern(regexp = "...")` | 正規表現に一致する |

## なぜ必要か

- **壊れたデータを入れないため**: 空の氏名や 0 個の注文が DB に入ると、後の処理がすべて狂います
- **利用者に分かりやすく返すため**: どの項目がなぜ誤りかを返せば、利用者が自分で直せます
- **攻撃を防ぐため**: 想定外に長い文字列や記号を、早い段階で止められます
- **層の責務を守るため**: 形式は Controller、業務ルールは Service と分けると、コードが読みやすくなります

チームのコーディング規約でも、Controller の責務は「入力の受け取り・形式チェック（Bean Validation）」です。
業務ロジックは Service に置きます。

## どうやるか

### 1. 入力の型にアノテーションを付ける

例:

```java
public record OrderRequest(
        @NotBlank @Size(max = 20) String orderNo,
        @NotNull @Min(1) @Max(999) Integer quantity) {}
```

数値の必須チェックをしたいときは、`int` ではなく `Integer` にします。
`int` は null になれないので、JSON に項目が無いと 0 が入り、`@NotNull` が効きません。

### 2. Controller の引数に `@Valid` を付ける

`@Valid` を付けないと、アノテーションがあってもチェックは動きません。

!!! failure "悪い例"
    ```java
    // 例: @Valid が無いので、空の氏名もそのまま Service に渡る
    @PostMapping
    public ResponseEntity<Member> register(@RequestBody RegisterRequest req) { ... }
    ```

!!! success "良い例"
    ```java
    // 例: @Valid でチェックが動き、違反は MethodArgumentNotValidException になる
    @PostMapping
    public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) { ... }
    ```

### 3. 違反を共通の形で返す

違反すると、Spring は `MethodArgumentNotValidException` を投げます。
これを `@RestControllerAdvice` のクラスでまとめて受け、400 応答に変換します。
各 Controller で個別に try-catch を書く必要はありません。

### 4. 業務チェックは Service で行う

「既に登録されているか」は、DB を見ないと分かりません。
これは Service で確かめ、違反なら `BusinessException`（メッセージ ID 付き）を投げます。

!!! failure "悪い例"
    ```java
    // 例: Controller に業務チェックと HTTP の判断が混ざっている
    @PostMapping
    public ResponseEntity<?> register(@Valid @RequestBody RegisterRequest req) {
        if (mapper.existsByEmail(req.email())) {
            return ResponseEntity.status(409).body("登録済みです");
        }
        ...
    }
    ```

!!! success "良い例"
    ```java
    // 例: Service が業務ルールを判断し、メッセージ ID で例外を投げる
    if (mapper.existsByEmail(normalized)) {
        throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
    }
    ```

### 5. 画面のチェックだけに頼らない

画面（フロントエンド）でチェックしていても、API は必ずチェックします。
API は画面を通さずに直接呼べるからです。

## サンプルアプリでは

### API の形式チェック（Bean Validation）

`sample-app/src/main/java/com/example/sample/member/MemberController.java` の 27〜29 行目です。
登録 API（API0002）の入力に、Bean Validation のアノテーションが付いています。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java @exercise-base -->
```java
/** 登録の入力. */
public record RegisterRequest(
        @NotBlank @Size(max = 50) String name, @NotBlank @Email @Size(max = 254) String email) {}
```

- `name` は必須で 50 文字まで、`email` は必須・メール形式・254 文字までです
- 桁数は DB の列（`VARCHAR(50)`、`VARCHAR(254)`）と合わせてあります

同じファイルの 36〜37 行目で `@Valid` を付けています。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java @exercise-base -->
```java
@PostMapping
public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
```

違反時の応答は `sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java` の 37〜44 行目で作ります。

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java @exercise-base -->
```java
@ExceptionHandler(MethodArgumentNotValidException.class)
public ResponseEntity<ErrorResponse> invalid(MethodArgumentNotValidException e) {
    List<String> details = e.getBindingResult().getFieldErrors().stream()
            .map(f -> f.getField() + ": " + f.getDefaultMessage())
            .sorted()
            .toList();
    return body(HttpStatus.BAD_REQUEST, MessageIds.INVALID_INPUT, new Object[0], details);
}
```

- 400 応答で、メッセージ ID は `APPE0001`（入力内容に誤りがあります。）です
- `details` に「項目名: 理由」を並べます。並び順を `sorted()` で固定し、テストしやすくしています

### API の業務チェック

`sample-app/src/main/java/com/example/sample/member/MemberService.java` の 24〜33 行目です。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java @exercise-base -->
```java
@Transactional
public Member register(String name, String email) {
    String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
    if (mapper.existsByEmail(normalized)) {
        throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
    }
```

- メールアドレスを前後の空白除去・小文字化してから、登録済みかを確かめます
- 登録済みなら `APPE0003` の `BusinessException` を投げ、例外ハンドラが 409 に変換します

### バッチ（CSV）の入力チェック

注文ファイル取込（JOB0001）は Bean Validation を使っていません。
1 行ずつ手で分解し、`OrderImportService.parse` で確かめています。
`sample-app/src/main/java/com/example/sample/order/OrderImportService.java` の 55〜74 行目です。

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java @exercise-base -->
```java
static Order parse(String line) {
    String[] cols = line.split(",", -1);
    if (cols.length != 4) {
        throw new IllegalArgumentException("列数が 4 ではありません（" + cols.length + " 列）");
    }
    String orderNo = cols[0].trim();
    if (orderNo.isEmpty()) {
        throw new IllegalArgumentException("order_no が空です");
    }
    long memberId = parseLong(cols[1], "member_id");
    String product = cols[2].trim();
    if (product.isEmpty()) {
        throw new IllegalArgumentException("product_code が空です");
    }
    long quantity = parseLong(cols[3], "quantity");
    if (quantity < 1 || quantity > 999) {
        throw new IllegalArgumentException("quantity は 1〜999 です（" + quantity + "）");
    }
    return new Order(orderNo, memberId, product, (int) quantity);
}
```

- 列数・必須・数値・範囲（1〜999）を順に確かめます
- 誤りがあれば例外を投げ、呼び出し元の `importLines` が「行番号: 理由」として記録し、次の行へ進みます
- `split(",", -1)` の `-1` は、末尾の空の列も数に入れる指定です（`A,1,P,` を 4 列と数える）
- `quantity` を `int` ではなく `long` で読んでから範囲を見ています。巨大な数でも桁あふれせずに範囲外と判定できます

### DB の制約（最後の砦）

`dev-environment/local/db/init/01_schema.sql` にも制約があります。

<!-- src: local/db/init/01_schema.sql @exercise-base -->
```sql
    email      VARCHAR(254) NOT NULL UNIQUE,
```

<!-- src: local/db/init/01_schema.sql @exercise-base -->
```sql
    quantity     INTEGER     NOT NULL CHECK (quantity BETWEEN 1 AND 999),
```

アプリのチェックをすり抜けても、DB が不正な値を拒否します。
ただし DB のエラーは利用者向けの分かりやすい応答になりません。アプリ側のチェックが本筋です。

!!! note "気付いておきたい点"
    `parse` は `member_id` の会員が実在するかは確かめていません。
    存在しない会員の行があると、DB の外部キー制約で失敗します。
    その影響は [20-13 トランザクション](20-13-transaction.md) で扱います。

## もし入力チェックがなかったら？

空の氏名や 0 個の注文が DB に入り、集計や画面表示で想定外のエラーが起きます。
DB の制約で止まった場合も、利用者には 500 エラーしか返らず、何を直せばよいか分かりません。
ログを調べる手間も増えます。

さらに、上限の無い文字列を受け付けると、巨大なデータでメモリや DB を圧迫されるおそれがあります。
入力チェックは、品質と安全の両方の入口です。

## 理解度チェック

1. メールアドレスの「形式」と「登録済みでないこと」は、それぞれどの層でチェックしますか。

    ??? note "答え"
        形式は Controller（Bean Validation の `@Email`）、登録済みでないことは Service です。
        後者は DB を見ないと判断できない業務チェックだからです。

2. `RegisterRequest` のアノテーションを残したまま `@Valid` を消すと、どうなりますか。

    ??? note "答え"
        チェックが動きません。空の氏名も Service に渡ります。
        DB の `NOT NULL` は空文字を止めないので、空の氏名が登録されるおそれがあります。

3. 必須の数値項目を `int` で受けると、何が問題ですか。

    ??? note "答え"
        JSON に項目が無いと 0 が入り、null にならないので `@NotNull` で検出できません。
        必須チェックをするなら `Integer` で受けます。

4. CSV の行 `A001,1,P-01,1000` は `parse` でどう扱われますか。

    ??? note "答え"
        `quantity は 1〜999 です（1000）` の `IllegalArgumentException` になります。
        `importLines` はこれを行番号付きでエラーに記録し、次の行の処理を続けます。

5. 入力エラーの `details` を `sorted()` で並べ替えているのはなぜですか。

    ??? note "答え"
        Bean Validation の違反は順序が決まっていないため、毎回同じ順で返すためです。
        応答が安定し、テストで確かめやすくなります。

## コードを読むときの確認観点

- [ ] リクエストの型にアノテーションがあり、Controller の引数に `@Valid` が付いている
- [ ] 桁数などの上限が、DB の列定義と合っている
- [ ] 業務チェック（DB を見る判断）が Controller ではなく Service にある
- [ ] 入力エラーが共通の例外ハンドラでメッセージ ID 付きの応答になっている
- [ ] バッチの入力チェックで、エラー行の行番号と理由が残る
- [ ] 必須の数値項目がプリミティブ型（`int` など）になっていない

参考: [Jakarta Bean Validation](https://beanvalidation.org/)、[Spring Framework: Validation](https://docs.spring.io/spring-framework/reference/core/validation/beanvalidation.html)

# 20-05 record と不変オブジェクト

!!! abstract "到達目標"
    - 不変オブジェクト（作った後に中身が変わらないオブジェクト）の利点を説明できる
    - `record` で何が自動で作られるかを説明できる
    - `record` でもリストの中身は変わりうることを説明し、`List.copyOf` で防げる
    - `record` を使わず可変クラスにする場面（`MemberRecord`）を読める

## 何か

### 不変オブジェクト

不変オブジェクトとは、作った後に中身が変わらないオブジェクトです。
Java の `String` や `Long` は不変です。
`"abc".toUpperCase()` は元の文字列を変えず、新しい文字列を返します。

### record

`record` は、不変のデータの入れ物を短く書くための構文です（Java 16 以降）。

例:

```java
public record Product(String code, String name) {}
```

この 1 行で、次のものが自動で作られます。

| 自動で作られるもの | 内容 |
| --- | --- |
| フィールド | `private final String code;` など |
| コンストラクタ | 全項目を受け取る |
| アクセサ | `code()`、`name()`（`get` は付かない） |
| `equals` / `hashCode` | 全項目が等しければ等しい |
| `toString` | `Product[code=P-01, name=…]` の形 |

setter は作られません。フィールドは `final` です。

## なぜ必要か

可変オブジェクトは、どこで書き換えられたかを追う必要があります。
メソッドに渡したオブジェクトが、戻ってきたら変わっていた、ということが起きます。

不変オブジェクトなら、作った時点の値がずっと続きます。
次の利点があります。

- どこに渡しても安全（勝手に変わらない）
- 複数のスレッドから同時に読んでも安全
- `equals` / `hashCode` が安定するので、`Set` や `Map` のキーに使える

従来のクラスで同じことをすると、コンストラクタ、getter、`equals`、`hashCode`、`toString` を手で書く必要があり、書き漏れが起きがちでした。
`record` はこれをなくします。

## どうやるか

### データの入れ物は record にする

!!! failure "悪い例"
    ```java
    // 例: setter があり、どこでも書き換えられる
    public class OrderLine {
        private String productCode;
        private int quantity;
        public void setQuantity(int quantity) { this.quantity = quantity; }
        // getter、equals、hashCode を手書き（書き忘れやすい）
    }
    ```

!!! success "良い例"
    ```java
    // 例: 不変。equals なども自動
    public record OrderLine(String productCode, int quantity) {}
    ```

値を変えたいときは、新しいオブジェクトを作ります。

### 入力チェックはコンパクトコンストラクタで

`record` の中に、引数の括弧を省いたコンストラクタ（コンパクトコンストラクタ）を書けます。
値の検査に使います。

例:

```java
public record OrderLine(String productCode, int quantity) {
    public OrderLine {
        if (quantity < 1) {
            throw new IllegalArgumentException("quantity は 1 以上です");
        }
    }
}
```

### record でもリストは変わりうる

`record` のフィールドは `final` ですが、`final` は「別のリストに差し替えられない」という意味です。
リストの中身の追加・削除は防げません。

!!! failure "悪い例"
    ```java
    // 例: 呼び出し元が持っている ArrayList をそのまま入れる
    List<String> errors = new ArrayList<>();
    Result r = new Result(errors);
    errors.add("後から追加"); // r.errors() の中身も変わってしまう
    ```

!!! success "良い例"
    ```java
    // 例: 変更できないコピーにしてから入れる
    Result r = new Result(List.copyOf(errors));
    ```

`List.copyOf` は、変更できない新しいリストを作ります。
これを防御的コピーと呼びます。
`record` のコンパクトコンストラクタの中で `errors = List.copyOf(errors);` と書けば、作る側が忘れても安全です。

なお、`List.copyOf` は `null` の要素を許しません。`null` が入っていると `NullPointerException` になります。

## サンプルアプリでは

### Member と Order

`sample-app/src/main/java/com/example/sample/member/Member.java`

```java
public record Member(Long id, String name, String email) {}
```

`sample-app/src/main/java/com/example/sample/order/Order.java`

```java
public record Order(String orderNo, long memberId, String productCode, int quantity) {}
```

会員と注文（CSV の 1 行）を不変のデータとして表しています。
アクセサは `member.email()` や `order.orderNo()` のように呼びます。

### メソッドを持つ record（ImportResult）

`sample-app/src/main/java/com/example/sample/order/ImportResult.java`

```java
public record ImportResult(int imported, int duplicated, List<String> errors) {

    public boolean hasErrors() {
        return !errors.isEmpty();
    }
}
```

`record` にも普通のメソッドを足せます。
`OrderImportJob` は `r.hasErrors()` で終了コード（0 か 4）を決めています。

### List.copyOf で渡す

`sample-app/src/main/java/com/example/sample/order/OrderImportService.java`

```java
return new ImportResult(imported, duplicated, List.copyOf(errors));
```

処理中に `ArrayList` へ追加してきた `errors` を、変更できないコピーにしてから結果に入れています。
`ImportResult` を受け取った側は、エラー一覧を変更できません。

### ErrorResponse

`sample-app/src/main/java/com/example/sample/common/ErrorResponse.java`

```java
public record ErrorResponse(String messageId, String message, List<String> details) {}
```

API のエラー応答です。Spring が JSON に変換します。
`ErrorResponse` 自体にはコンパクトコンストラクタがなく、`List.copyOf` もしていません。
渡す側の `ApiExceptionHandler` が、`List.of()` や Stream の `toList()` で作った変更できないリストを渡しているので、現状は安全です。
新しい呼び出し元を足すときは、変更できないリストを渡すように気をつけます。

### コントローラ内の record

`sample-app/src/main/java/com/example/sample/member/MemberController.java`

```java
public record RegisterRequest(
        @NotBlank @Size(max = 50) String name, @NotBlank @Email @Size(max = 254) String email) {}
```

登録 API の入力も `record` です。項目に入力チェックの注釈を付けられます。

### 配列の防御的コピー

`sample-app/src/main/java/com/example/sample/common/BusinessException.java`

```java
this.args = args.clone();
// ...
public Object[] getArgs() {
    return args.clone();
}
```

配列は変更できる入れ物です。
受け取るときと返すときに `clone()` でコピーし、外から中身を変えられないようにしています。

### あえて可変にしている MemberRecord

`sample-app/src/main/java/com/example/sample/member/MemberRecord.java`

```java
/** 登録用の可変オブジェクト（MyBatis が採番した ID を書き戻すため）. */
public class MemberRecord {

    private Long id;
    // ...
    public void setId(Long id) {
        this.id = id;
    }

    public Member toMember() {
        return new Member(id, name, email);
    }
}
```

MyBatis の `useGeneratedKeys` は、DB が採番した ID をオブジェクトに書き戻します。
`record` は書き換えられないので、登録用にだけ可変クラスを用意しています。
登録後は `toMember()` で不変の `Member` に変えて返します。可変な範囲を最小にする工夫です。

## もし〇〇がなかったら？

もし `ImportResult` が `List.copyOf` をせずに `ArrayList` をそのまま持っていたら、
受け取った側が `r.errors().clear()` のように中身を消せてしまいます。
ログに出した件数と、後で集計した件数が食い違うといった不具合になります。
原因は「どこかでリストが書き換えられた」ことで、探すのに時間がかかります。

もし `record` がなければ、`Member` のような単純なデータにも 40 行ほどの定型コードが必要です。
`equals` に項目を足し忘れると、`Set` で重複を正しく判定できなくなります。

## 理解度チェック

1. `record Member(Long id, String name, String email)` で、メールアドレスを読むメソッド名は何ですか。

    ??? note "答え"
        `email()` です。`getEmail()` ではありません。

2. `record` のフィールドは `final` なのに、リストの中身が変わりうるのはなぜですか。

    ??? note "答え"
        `final` は「別のリストに差し替えられない」だけで、リストの中身の追加・削除は防がないためです。
        `List.copyOf` などで変更できないリストにします。

3. `MemberRecord` が `record` ではなく普通のクラスなのはなぜですか。

    ??? note "答え"
        MyBatis が採番した ID を `setId` で書き戻すためです。`record` は書き換えられません。

4. `BusinessException` が `getArgs()` で `args.clone()` を返すのはなぜですか。

    ??? note "答え"
        配列をそのまま返すと、受け取った側が中身を書き換えられるためです。コピーを返して中身を守ります。

## コードを読むときの確認観点

- [ ] データの入れ物に、不要な setter がないか（`record` にできないか）
- [ ] `record` やフィールドにリスト・配列を入れるとき、コピーしているか
- [ ] 可変クラスにしている理由が明確か（フレームワークの都合など）
- [ ] `record` の検査がコンパクトコンストラクタに書かれているか
- [ ] 値を変えたいとき、既存オブジェクトを書き換えず、新しく作っているか

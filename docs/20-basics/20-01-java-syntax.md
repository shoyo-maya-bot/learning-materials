# 20-01 Java の基本文法おさらい

!!! abstract "到達目標"
    - 基本型（プリミティブ型）と参照型の違いを説明できる
    - 文字列の比較に `==` ではなく `equals` を使う理由を説明できる
    - 整数の桁あふれと、金額に `BigDecimal` を使う理由を説明できる
    - `null` が入りうる箇所を読み取り、安全に書ける

## 何か

Java の文法のうち、業務コードで毎日使う部分をおさらいします。
対象は、型、`var`、`String`、制御構文（`if` / `for` / `switch`）、メソッドです。

文法そのものより「つまずきやすい点」を中心に扱います。
文法の全体は公式の [Java チュートリアル](https://docs.oracle.com/javase/tutorial/java/nutsandbolts/index.html) で確認できます。

### 型の 2 種類

| 種類 | 例 | 変数に入るもの | `null` |
| --- | --- | --- | --- |
| 基本型（プリミティブ型） | `int`、`long`、`boolean`、`double` | 値そのもの | 入らない |
| 参照型 | `String`、`Long`、`List`、自作クラス | オブジェクトの場所（参照） | 入る |

`int` と `Integer`、`long` と `Long` のように対になる型があります。
参照型のほう（`Integer` など）をラッパー型と呼びます。
基本型とラッパー型は自動で変換されます。これをオートボクシングと呼びます。

### var

`var` は、右辺から型を推論させる書き方です（Java 10 以降）。
型が消えるわけではなく、コンパイル時に決まります。

例:

```java
var names = new ArrayList<String>(); // ArrayList<String> 型
var count = 0;                       // int 型
```

右辺を見て型がすぐ分かるときだけ使います。
`var result = service.process();` のように、型が読み取れない場合は型を書きます。

## なぜ必要か

Java はコンパイルが通っても、意図と違う動きをする書き方があります。
代表例が次の 4 つです。どれもテストをすり抜けやすく、本番で初めて見つかることがあります。

1. `==` で文字列を比べる（たまたま一致して見えることがある）
2. `null` を考えずにメソッドを呼ぶ（`NullPointerException`）
3. `int` の上限を超えて計算する（桁あふれ。エラーにならず値が化ける）
4. 金額を `double` で計算する（小数の誤差が出る）

## どうやるか

### `==` と `equals`

`==` は「同じオブジェクトか」を比べます。
`equals` は「中身が同じか」を比べます。
文字列や参照型の中身を比べるときは `equals` を使います。

!!! failure "悪い例"
    ```java
    // 例: 入力された区分が "01" かどうか
    if (kubun == "01") { ... }
    ```
    リテラル同士なら一致して見えることがあります。
    しかし、画面や CSV から読んだ文字列は別オブジェクトなので `false` になります。

!!! success "良い例"
    ```java
    // 例: 定数を左に置くと、kubun が null でも例外にならない
    if ("01".equals(kubun)) { ... }
    ```

ラッパー型（`Integer` / `Long`）も同じです。
`Long a = 1000L; Long b = 1000L;` で `a == b` は `false` になりえます。
小さい値（-128〜127）だけキャッシュされるため、テストでは通ってしまうことがあります。

### null

参照型の変数には `null` が入りえます。
`null` に対してメソッドを呼ぶと `NullPointerException` が発生します。

!!! failure "悪い例"
    ```java
    // 例: email が null なら NullPointerException
    String normalized = email.trim().toLowerCase();
    ```

!!! success "良い例"
    ```java
    // 例: 入口（入力チェック）で null を弾き、内側では null が来ない前提にする
    Objects.requireNonNull(email, "email");
    String normalized = email.trim().toLowerCase(Locale.ROOT);
    ```

あちこちで `if (x != null)` を書くより、入口で弾くほうが読みやすくなります。
入口のチェックは [20-10 入力チェック](20-10-validation.md) で学びます。
「無いかもしれない値」を返すときは `Optional` を使います（[20-03](20-03-collections-stream.md)）。

`toLowerCase()` に `Locale.ROOT` を渡すのは、実行環境の言語設定で結果が変わるのを防ぐためです。

### 整数の桁あふれ

`int` の上限は約 21 億（`Integer.MAX_VALUE` = 2,147,483,647）です。
上限を超えるとエラーにならず、負の値に化けます。これを桁あふれ（オーバーフロー）と呼びます。

!!! failure "悪い例"
    ```java
    // 例: 単価 50,000 × 数量 50,000 は 25 億。int では負の値になる
    int total = unitPrice * quantity;
    ```

!!! success "良い例"
    ```java
    // 例: 大きくなりうる計算は long。あふれたら例外にする
    long total = Math.multiplyExact((long) unitPrice, quantity);
    ```

`Math.addExact` / `Math.multiplyExact` は、あふれたときに `ArithmeticException` を投げます。
`long` から `int` へのキャスト `(int)` も、範囲外なら黙って値が化けます。
キャストの前に範囲を確認します。

### 金額は BigDecimal

`double` は 2 進数で小数を表すため、`0.1` を正確に表せません。

例:

```java
System.out.println(0.1 + 0.2); // 0.30000000000000004
```

!!! failure "悪い例"
    ```java
    // 例: 金額を double で持つ
    double price = 1980.0;
    double tax = price * 0.1;
    ```

!!! success "良い例"
    ```java
    // 例: 金額は BigDecimal。文字列から作り、丸め方を明示する
    BigDecimal price = new BigDecimal("1980");
    BigDecimal tax = price.multiply(new BigDecimal("0.10"))
            .setScale(0, RoundingMode.DOWN);
    ```

`new BigDecimal(0.1)` のように `double` から作ると、誤差ごと取り込まれます。
文字列か `BigDecimal.valueOf` で作ります。
比較は `equals` ではなく `compareTo` を使います。`equals` は `1.0` と `1.00` を別物とみなすためです。

### 制御構文とメソッド

`switch` は Java 14 以降、矢印の形（switch 式）で書けます。
`break` の書き忘れによる「次の case に落ちる」誤りが起きません。

例:

```java
String label = switch (exitCode) {
    case 0 -> "正常";
    case 4 -> "警告";
    default -> "異常";
};
```

メソッドは「1 つのことだけをする」「引数は少なく」が基本です。
引数で受け取ったオブジェクトを書き換えると、呼び出し側が驚きます。
結果は戻り値で返します。

## サンプルアプリでは

### 定数を左に置いた equals

`sample-app/src/main/java/com/example/sample/order/OrderImportService.java`

```java
if (lines.isEmpty() || !HEADER.equals(stripBom(lines.get(0)).trim())) {
    throw new IllegalArgumentException("見出し行が不正です（期待値: " + HEADER + "）");
}
```

CSV の 1 行目が見出しと一致するかを、定数 `HEADER` を左に置いて `equals` で比べています。
`trim()` で前後の空白を除き、`stripBom` で先頭の BOM（文字コードの目印）を除いてから比べています。

### long で受けてから範囲を確かめ、int にキャスト

同じファイルの `parse` メソッドです。

```java
long quantity = parseLong(cols[3], "quantity");
if (quantity < 1 || quantity > 999) {
    throw new IllegalArgumentException("quantity は 1〜999 です（" + quantity + "）");
}
return new Order(orderNo, memberId, product, (int) quantity);
```

数量はいったん `long` で読みます。
範囲（1〜999）を確かめてから `(int)` にキャストしているので、値が化けることはありません。
いきなり `int` で読むと、巨大な値が来たときの扱いが分かりにくくなります。

### Locale を指定した小文字化

`sample-app/src/main/java/com/example/sample/member/MemberService.java`

```java
String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
```

メールアドレスの前後の空白を除き、小文字にそろえています。
`email` が `null` にならないのは、コントローラの入力チェック（`@NotBlank`）で弾いているためです。

### 基本型とラッパー型の使い分け

`sample-app/src/main/java/com/example/sample/member/Member.java`

```java
public record Member(Long id, String name, String email) {}
```

`id` はラッパー型の `Long` です。登録前は ID が未採番（`null`）でありうるためです。
一方、`MemberController` の `get(@PathVariable("id") long id)` は基本型の `long` です。
URL のパスには必ず値があるので、`null` を許す必要がありません。

なお、サンプルアプリには金額の項目がありません。
金額を扱う機能を足すときは、この章の `BigDecimal` の書き方に従います。

## もし〇〇がなかったら？

もし `equals` を知らずに `==` で文字列を比べていたら、どうなるでしょうか。
単体テストでは、リテラル同士の比較で偶然 `true` になり、テストが通ってしまうことがあります。
本番で CSV やリクエストから読んだ値と比べたときに初めて `false` になります。
「ローカルでは動くのに本番だけ動かない」という、原因の分かりにくい不具合になります。

桁あふれも同じです。小さなテストデータでは起きず、大量データや大きな金額で初めて起きます。
しかもエラーにならず、負の値や誤った値がそのまま保存されます。

## 理解度チェック

1. `"01" == kubun` が、テストでは `true` なのに本番で `false` になることがあるのはなぜですか。

    ??? note "答え"
        `==` は同じオブジェクトかを比べるためです。
        テストではリテラル同士が同じオブジェクトを指して `true` になることがあります。
        本番で外部から読んだ文字列は別オブジェクトなので `false` になります。`equals` を使います。

2. `"01".equals(kubun)` と `kubun.equals("01")` の違いは何ですか。

    ??? note "答え"
        `kubun` が `null` のとき、後者は `NullPointerException` になります。
        前者は `false` を返すだけです。

3. `OrderImportService.parse` が数量をいきなり `int` で読まず、`long` で読んでから `(int)` にしているのはなぜですか。

    ??? note "答え"
        範囲を確かめてからキャストするためです。
        1〜999 に収まることを確認しているので、`(int)` で値が化けることはありません。

4. 金額を `double` で計算してはいけない理由と、`BigDecimal` を作るときの注意を答えてください。

    ??? note "答え"
        `double` は小数を正確に表せず、誤差が出るためです。
        `BigDecimal` は文字列か `BigDecimal.valueOf` から作ります。比較は `compareTo` を使います。

## コードを読むときの確認観点

- [ ] 文字列やラッパー型（`Long` など）を `==` で比べていないか
- [ ] `null` が来うる変数に、確認なしでメソッドを呼んでいないか
- [ ] `int` の掛け算・足し算で、上限を超える可能性がないか
- [ ] `(int)` などのキャストの前に、範囲を確認しているか
- [ ] 金額を `double` / `float` で扱っていないか
- [ ] `toLowerCase` / `toUpperCase` に `Locale.ROOT` を渡しているか

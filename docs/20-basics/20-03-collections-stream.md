# 20-03 コレクションと Stream

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `List` / `Set` / `Map` の違いと使い分けを説明できる
    - 変更できるコレクションと変更できないコレクションを見分けられる
    - `filter` / `map` / `sorted` / `toList` を使った Stream を読める・書ける
    - `Optional` を使って「無いかもしれない値」を扱える

## 何か

### コレクション

コレクションは、複数の値をまとめて扱う入れ物です。よく使うのは次の 3 つです。

| 型 | 特徴 | よく使う実装 | 例 |
| --- | --- | --- | --- |
| `List` | 順番がある。重複できる | `ArrayList` | CSV の行の並び |
| `Set` | 重複しない | `HashSet` | 登録済みの注文番号の集まり |
| `Map` | キーと値の組 | `HashMap` | 会員 ID → 会員 |

変数の型はインタフェース（`List`）にし、`new` のときだけ実装（`ArrayList`）を書きます。

### 変更できないコレクション

`List.of(...)`、`List.copyOf(...)`、Stream の `toList()` が返すリストは変更できません。
`add` などを呼ぶと `UnsupportedOperationException` が発生します。

### Stream

Stream は、コレクションの要素を「絞り込む → 変換する → 集める」流れで処理する書き方です。
`for` 文で書く処理を、何をしたいかが分かる形で書けます。

### Optional

`Optional` は「値があるかもしれないし、無いかもしれない」ことを型で表す入れ物です。
`null` を返す代わりに使います。

## なぜ必要か

業務処理の多くは「一覧を受け取り、条件で選び、形を変えて返す」ことです。
`for` 文だけで書くと、途中の変数や `if` が増え、意図が読み取りにくくなります。

また、`null` を返すメソッドは、呼び出し側が確認を忘れると `NullPointerException` になります。
`Optional` を返せば、「無い場合」を考えることを呼び出し側に強制できます。

変更できないコレクションを返すのは、受け取った側が勝手に中身を変える事故を防ぐためです。

## どうやるか

### for 文と Stream

!!! failure "悪い例"
    ```java
    // 例: 在庫のある商品のコードを集める（途中の状態が多い）
    List<String> codes = new ArrayList<>();
    for (Product p : products) {
        if (p.getStock() > 0) {
            codes.add(p.getCode());
        }
    }
    Collections.sort(codes);
    ```

!!! success "良い例"
    ```java
    // 例: 絞り込み → 変換 → 並べ替え → 集める
    List<String> codes = products.stream()
            .filter(p -> p.getStock() > 0)
            .map(Product::getCode)
            .sorted()
            .toList();
    ```

`Product::getCode` はメソッド参照で、`p -> p.getCode()` と同じ意味です。
`toList()` は Java 16 以降で使えます。返るリストは変更できません。

### よく使う操作

| 操作 | 意味 |
| --- | --- |
| `filter(条件)` | 条件に合う要素だけ残す |
| `map(変換)` | 要素を別の値に変える |
| `sorted()` | 並べ替える |
| `anyMatch(条件)` | 1 つでも条件に合えば `true` |
| `count()` | 件数を数える |
| `toList()` | リストに集める |
| `forEach(処理)` | 各要素に処理をする（戻り値なし） |

### Stream で書かないほうがよい場合

Stream の中で外の変数を書き換えるのは避けます。
処理の途中で例外を投げ分けたり、複数の値を同時に数えたりするなら、`for` 文のほうが読みやすいこともあります。

!!! failure "悪い例"
    ```java
    // 例: Stream の中で外のリストに add する
    List<String> errors = new ArrayList<>();
    lines.stream().forEach(l -> { if (l.isBlank()) errors.add(l); });
    ```

!!! success "良い例"
    ```java
    // 例: 結果は Stream から受け取る
    List<String> blanks = lines.stream().filter(String::isBlank).toList();
    ```

### Optional の使い方

!!! failure "悪い例"
    ```java
    // 例: get() は値が無いと例外。isPresent と組み合わせると null チェックと変わらない
    Optional<Member> m = mapper.findById(id);
    if (m.isPresent()) { return m.get(); }
    return null;
    ```

!!! success "良い例"
    ```java
    // 例: 無ければ業務例外にする
    return mapper.findById(id).orElseThrow(() -> new NotFoundException(...));
    ```

`Optional` は戻り値に使います。フィールドや引数には使いません。

## サンプルアプリでは

### Stream で入力エラーの一覧を作る

`sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java`

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java @exercise-base -->
```java
List<String> details = e.getBindingResult().getFieldErrors().stream()
        .map(f -> f.getField() + ": " + f.getDefaultMessage())
        .sorted()
        .toList();
```

入力チェックの項目別エラーを「項目名: メッセージ」の文字列に変換し、並べ替えて集めています。
`sorted()` があるので、応答の順番が毎回同じになります。テストで比べやすくなります。

### Optional と orElseThrow

`sample-app/src/main/java/com/example/sample/member/MemberMapper.java`

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberMapper.java @exercise-base -->
```java
Optional<Member> findById(long id);
```

`sample-app/src/main/java/com/example/sample/member/MemberService.java`

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java @exercise-base -->
```java
return mapper.findById(id).orElseThrow(() -> new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id));
```

会員が見つからないときは `null` ではなく空の `Optional` が返ります。
サービスは `orElseThrow` で「見つからない」業務例外に変えています。

### for 文を選んでいる例

`sample-app/src/main/java/com/example/sample/order/OrderImportService.java` の `importLines` は、
Stream ではなく `for` 文で書かれています。

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java @exercise-base -->
```java
for (int i = 1; i < lines.size(); i++) {
    String line = lines.get(i);
    if (line.isBlank()) {
        continue;
    }
    int lineNo = i + 1;
    // ...（解析し、登録件数・重複件数・エラーを数える）
}
return new ImportResult(imported, duplicated, List.copyOf(errors));
```

行番号が必要なこと、登録件数・重複件数・エラーの 3 つを同時に数えることから、`for` 文が読みやすい場面です。
最後の `List.copyOf(errors)` で、変更できないリストにしてから結果に入れています。

### Map と Set を使ったテスト用の実装

`sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java`

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java @exercise-base -->
```java
final Map<Long, Member> rows = new HashMap<>();
// ...
return rows.values().stream().anyMatch(m -> m.email().equals(email));
```

DB の代わりに `Map` で会員を持ち、`anyMatch` でメールアドレスの重複を調べています。

`sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java` では、
`Set<String> stored` の `add` が「新しく追加できたら `true`」を返す性質を使い、注文番号の重複を表しています。

<!-- src: sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java @exercise-base -->
```java
private final OrderImportService service = new OrderImportService(o -> stored.add(o.orderNo()) ? 1 : 0);
```

## もし〇〇がなかったら？

もし `Optional` がなく、`findById` が `null` を返していたら、
サービスの書き手が `null` の確認を忘れたとき、`NullPointerException` で 500 エラーになります。
本来は「会員が見つかりません（404）」と返すべきところです。
`Optional` を返すことで、「無い場合どうするか」を書かないとコンパイルが通らない形にできます。

もし変更できないコレクションがなければ、`ImportResult` を受け取った側が `errors` に追加・削除できてしまいます。
取込結果のログと実際の結果が食い違う、といった追いにくい不具合の原因になります。

## 理解度チェック

1. `List.of(1, 2).add(3)` を実行すると何が起きますか。

    ??? note "答え"
        `UnsupportedOperationException` が発生します。`List.of` のリストは変更できません。

2. `ApiExceptionHandler` で `sorted()` を入れている利点は何ですか。

    ??? note "答え"
        エラーの順番が毎回同じになることです。応答が安定し、テストで比べやすくなります。

3. `Optional` の `get()` を、値の有無を確かめずに呼ぶとどうなりますか。代わりに何を使いますか。

    ??? note "答え"
        値が無いと `NoSuchElementException` が発生します。
        `orElseThrow(() -> 業務例外)` や `orElse(既定値)` を使います。

4. `importLines` が Stream ではなく `for` 文で書かれている理由を 1 つ挙げてください。

    ??? note "答え"
        行番号を使うこと、または登録・重複・エラーの 3 つを同時に数えることです。
        Stream で書くと外の変数を書き換えることになり、読みにくくなります。

## コードを読むときの確認観点

- [ ] 変数の型がインタフェース（`List` / `Map` / `Set`）になっているか
- [ ] 戻り値で受け取ったリストに `add` などをしていないか（変更できないリストかもしれない）
- [ ] Stream の中で外の変数を書き換えていないか
- [ ] `null` を返すメソッドがないか。`Optional` にすべきでないか
- [ ] `Optional.get()` を確認なしに呼んでいないか

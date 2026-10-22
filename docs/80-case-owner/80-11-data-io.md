# 80-11 データの入出力方式（List・Cursor・ItemReader）

!!! abstract "到達目標"
    - List・Cursor・ItemReader の 3 つの方式の違いを、メモリの使い方と書き方の両面で説明できる
    - 設計書のデータ量と要件から、方式を選べる
    - 今の方式を別の方式に変えたら、コードの構造とメモリの使い方がどう変わるかを説明できる
    - Cursor を使うときの注意（トランザクション・閉じる・取得の単位）を説明できる

## 何か

バッチは、大量のデータを読み、処理し、書き出します。
データを **どう受け取るか** には、主に 3 つの方式があります。

| 方式 | 受け取り方 | メモリ | 書き方 |
|---|---|---|---|
| List | 全件を一度に `List` で受け取る | 全件分を持つ | いちばん簡単。`for` で回すだけ |
| Cursor | 1 件ずつ順に受け取る（MyBatis の `Cursor`） | 取得の単位の分だけ持つ | 受け取っている間、DB との接続とトランザクションを開いたままにする。最後に閉じる |
| ItemReader | 枠組み（Spring Batch）が `read()` を繰り返し呼び、1 件ずつ受け取る | 区切り（チャンク）の分だけ持つ | 読む・処理・書くを別の部品に分け、区切りごとにコミットする |

ファイルの読み方にも、同じ違いがあります。
`Files.readAllLines` は全行を `List` で返し、`BufferedReader.readLine` は 1 行ずつ返します。

## なぜ必要か

作業担当は、指示された方式で実装できれば十分です。
案件担当は、設計書のデータ量と要件から方式を選び、「もう一方の方式ならどうなるか」を説明できる必要があります。

方式の選び間違いは、テスト環境では見つかりにくい不具合になります。
テストのデータが 100 件なら、どの方式でも動きます。
本番で 500 万件になったとき、List の方式はメモリが足りなくなって止まります。

逆に、10 件しか扱わない処理に ItemReader の枠組みを持ち込むと、部品が増えて読みにくくなります。

## どうやるか

### 1. 選ぶ基準

| 基準 | List | Cursor | ItemReader |
|---|---|---|---|
| データ量 | 少ない（全件がメモリに楽に収まる） | 多い | 多い |
| コミットの単位（[80-10](80-10-commit-unit.md)） | 一括 | 一括（読む間は 1 つのトランザクション） | 中間（区切りごと） |
| 途中からの再開 | できない | できない（自分で作る） | 枠組みの機能を使える |
| 書きやすさ | 高い | 中（閉じる・トランザクションに注意） | 低（部品と設定が増える） |

### 2. List で書く

例:

```java
// 例: 全件を List で受け取る（件数が少ないとき）
@Transactional(readOnly = true)
public int exportOrders(String orderDate, OrderWriter writer) throws IOException {
    List<Order> orders = mapper.findByDate(orderDate);
    for (Order o : orders) {
        writer.write(o);
    }
    return orders.size();
}
```

### 3. Cursor で書く

MyBatis の Mapper は、戻り値を `Cursor<Order>` にすると、1 件ずつ取り出せます
（[Java API（MyBatis）](https://mybatis.org/mybatis-3/ja/java-api.html)）。

例:

```java
// 例: Cursor で 1 件ずつ受け取る（トランザクションの中で使い、最後に閉じる）
@Transactional(readOnly = true)
public int exportOrders(String orderDate, OrderWriter writer) throws IOException {
    int count = 0;
    try (Cursor<Order> cursor = mapper.openCursorByDate(orderDate)) {
        for (Order o : cursor) {
            writer.write(o);
            count++;
        }
    }
    return count;
}
```

List の書き方との違いは、次の 3 点です。

- `try-with-resources` で閉じる（閉じないと、DB の資源が残る）
- 読み終わるまで、トランザクション（DB との接続）を開いたままにする。`@Transactional` の外で使うと、Mapper の呼び出しから戻った時点で接続が閉じられ、読み進められない
- 件数は `size()` で取れないので、自分で数える

!!! warning "取得の単位（fetchSize）も確かめる"
    `Cursor` で受け取っても、JDBC ドライバーが全件をまとめて受け取ってしまうことがあります。
    PostgreSQL の JDBC ドライバーは既定で全件を受け取り、自動コミットを切り、取得の単位（fetchSize）を指定したときだけ少しずつ受け取ります
    （[Getting results based on a cursor（PostgreSQL JDBC）](https://jdbc.postgresql.org/documentation/query/#getting-results-based-on-a-cursor)）。
    Mapper XML の `<select>` の `fetchSize` 属性で指定します（[Mapper XML ファイル（MyBatis）](https://mybatis.org/mybatis-3/ja/sqlmap-xml.html)）。

### 4. ItemReader で書く

Spring Batch では、読む部品（ItemReader）・処理する部品（ItemProcessor）・書く部品（ItemWriter）を分けます。
枠組みが `read()` を繰り返し呼び、区切り（チャンク）の件数がたまったら書き出してコミットします
（[Chunk-oriented Processing（Spring Batch）](https://docs.spring.io/spring-batch/reference/step/chunk-oriented-processing.html)）。
`read()` が `null` を返すと、入力の終わりです（[ItemReader（Spring Batch）](https://docs.spring.io/spring-batch/reference/readers-and-writers/item-reader.html)）。

例:

```java
// 例: 1 行ずつ返す ItemReader（null を返したら終わり）
public class OrderLineReader implements ItemReader<String> {

    private final BufferedReader reader;

    public OrderLineReader(BufferedReader reader) {
        this.reader = reader;
    }

    @Override
    public String read() throws IOException {
        return reader.readLine();
    }
}
```

MyBatis には、Spring Batch 用の ItemReader（Cursor を使うもの・ページ単位で読むもの）があります
（[Spring Batch（MyBatis-Spring）](https://mybatis.org/spring/ja/batch.html)）。

## サンプルアプリでは

JOB0001 は List の方式です。ファイルを読む部品の約束（インタフェース）が、`List` を返す形になっています。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java @main -->
```java
List<String> readLines(String location) throws IOException;
```

ローカルのファイルは、`Files.readAllLines` で全行を読みます。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java @main -->
```java
return Files.readAllLines(path, StandardCharsets.UTF_8);
```

全行をメモリに持つので、ファイルの大きさに上限（`app.batch.max-input-bytes`）を設けています。
`DefaultFileFetcher` の Javadoc にその理由が書かれています。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java @main -->
```java
 * <p>ファイル全体をメモリに読むので、大きさに上限を設ける（{@code app.batch.max-input-bytes}。既定 64 MiB）。
```

`local/README.md` は、数十万行を超えるファイルを扱う実案件では、
行を順に読みながら一定の件数ごとにコミットする設計（Spring Batch など）に変えるよう述べています。
sample-app は、読みやすさを優先して List の方式を選んでいます。

## もし量に応じた方式の選択がなかったら？

テストでは 100 件の CSV で問題なく動いたバッチが、本番の月末に 300 万件のファイルを受け取ったとします。
List の方式では全行をメモリに読もうとして、メモリが足りずに止まります（`OutOfMemoryError`）。
メモリを増やしてしのいでも、翌月にさらに増えれば同じことが起きます。

設計の段階で「最大の件数」を確かめ、方式とメモリの見積をしていれば、この障害は起きません。
「最大で何件か」は、設計書に書かれていなければ質問すべき項目です。

## 理解度チェック

1. List と Cursor で、メモリの使い方はどう違いますか。
2. Cursor を `@Transactional` の外で使うと、何が起きますか。
3. ItemReader の方式で、コミットはいつ起きますか。
4. JOB0001 がファイルの大きさに上限を設けている理由は何ですか。

??? note "答え"
    1. List は全件を一度にメモリに持ちます。Cursor は 1 件ずつ取り出すので、取得の単位の分だけを持ちます。
    2. Mapper の呼び出しから戻った時点で DB との接続（MyBatis のセッション）が閉じられ、読み進めるとエラーになります。読み終わるまで、トランザクションの中で使う必要があります。
    3. 区切り（チャンク）の件数を読んで処理し、書き出したところでコミットします。
    4. ファイル全体を List としてメモリに読むので、大きすぎるとメモリが足りなくなるからです。

## コードを読むときの確認観点

- [ ] 大量のデータを `List` で受け取っていないか（最大の件数は設計書にあるか）
- [ ] `Cursor` を `try-with-resources` で閉じているか
- [ ] `Cursor` を、トランザクションの中で読み終えているか
- [ ] 全件をメモリに読むなら、大きさの上限とメモリの見積があるか
- [ ] 方式とコミットの単位の組み合わせが、設計書と合っているか

## 演習

1. 次の架空の処理について、List・Cursor・ItemReader のどれを選ぶかと、理由を答えてください。
   (a) 会員のランク（5 種類）のマスタを読み、画面に出す
   (b) 1 日分の注文（最大 20 万件）を CSV に書き出す。失敗したら最初からやり直してよい
   (c) 毎月の請求（最大 500 万件）を作る。途中で失敗したら、続きから再開したい
2. JOB0001 を、ファイルを 1 行ずつ読む方式に変えるとします。
   `FileFetcher`・`DefaultFileFetcher`・`OrderImportService.importLines`・テストのそれぞれで、何が変わるかを説明してください。
   メモリの使い方と、トランザクションがどう変わるか（変わらないか）も答えてください。
3. 次のコードの問題点を答えてください。

    ```java
    // 例: 演習 3 のコード
    public Cursor<Order> openOrders(String orderDate) {
        return mapper.openCursorByDate(orderDate);
    }
    ```

解答: [80-11 解答](answers/80-11.md)

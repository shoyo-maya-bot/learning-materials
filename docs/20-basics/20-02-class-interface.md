# 20-02 クラスとインタフェース

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - カプセル化（フィールドを隠し、操作をメソッドに限る）の目的を説明できる
    - インタフェースを「契約」として説明できる
    - `FileFetcher` と `DefaultFileFetcher` の関係を読める
    - インタフェースを使って、テスト用の実装に差し替えるコードを書ける

## 何か

### クラス

クラスは、データ（フィールド）と、そのデータを扱う処理（メソッド）をまとめたものです。
クラスから作った実体をオブジェクト（インスタンス）と呼びます。

### カプセル化

カプセル化とは、フィールドを `private` にして外から直接触らせず、メソッド経由でだけ操作させることです。
クラスの中身（どう実現しているか）を隠し、外に見せる約束（何ができるか）だけを公開します。

### インタフェース

インタフェースは「このメソッドを持つ」という約束（契約）だけを書いた型です。
処理の中身は書きません。中身は、インタフェースを実装（`implements`）したクラスが書きます。

例:

```java
public interface PriceCalculator {
    long calculate(long unitPrice, int quantity);
}
```

使う側はインタフェースだけを知り、どの実装が来るかを知りません。

## なぜ必要か

カプセル化をしないと、どこからでもフィールドを書き換えられます。
「会員のメールアドレスは必ず小文字」のようなルールを、1 か所で守れなくなります。

インタフェースがないと、使う側が特定の実装クラスに直接依存します。
たとえば「S3 からファイルを読む」処理を直接呼んでいると、次の問題が起きます。

- 単体テストのたびに S3（またはエミュレータ）が必要になる
- 読み込み元を変えるとき（ローカルファイル、別のストレージ）に、使う側も直す必要がある

インタフェースを挟むと、使う側を変えずに実装を差し替えられます。

## どうやるか

### フィールドは private、変更はメソッドで

!!! failure "悪い例"
    ```java
    // 例: どこからでも書き換えられる
    public class Product {
        public String code;
        public int stock;
    }
    // 呼び出し側で product.stock = -5; と書けてしまう
    ```

!!! success "良い例"
    ```java
    // 例: ルール（在庫は負にならない）をクラスの中で守る
    public class Product {
        private final String code;
        private int stock;

        public Product(String code, int stock) {
            this.code = code;
            this.stock = stock;
        }

        public void ship(int quantity) {
            if (quantity > stock) {
                throw new IllegalStateException("在庫が足りません");
            }
            stock -= quantity;
        }

        public int getStock() {
            return stock;
        }
    }
    ```

変わらないフィールドには `final` を付けます。
setter（値を書き換えるメソッド）は、本当に必要なときだけ作ります。

### インタフェースに依存する

!!! failure "悪い例"
    ```java
    // 例: 使う側が実装クラスを自分で new している
    public class OrderJob {
        private final S3Reader reader = new S3Reader();
    }
    ```
    `OrderJob` をテストするには、必ず S3 につながる `S3Reader` が動きます。

!!! success "良い例"
    ```java
    // 例: インタフェースを受け取る。どの実装かは外から渡す
    public class OrderJob {
        private final InputReader reader; // インタフェース

        public OrderJob(InputReader reader) {
            this.reader = reader;
        }
    }
    ```

外から実装を渡す仕組みを DI（依存性の注入）と呼びます。
Spring がこれを自動で行います。詳しくは [20-07 Spring Boot の仕組み（DI）](20-07-spring-di.md) で学びます。

### 継承は控えめに

クラスは `extends` で別のクラスを継承できます。
ただし、親クラスの変更が子クラスに広く影響するため、業務コードでは多用しません。
「〜は〜の一種である」と自然に言えるときだけ使います。
サンプルアプリでは、例外クラスの階層（[20-04 例外処理](20-04-exception.md)）で使っています。

## サンプルアプリでは

### FileFetcher（契約）

`sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java`

```java
/** 入力ファイルを行の並びとして読む（s3:// とローカルパスを同じ形で扱う）. */
public interface FileFetcher {

    List<String> readLines(String location) throws IOException;
}
```

契約は「場所（`location`）を渡すと、行の一覧が返る」だけです。
S3 かローカルファイルかは、この型からは分かりません。それでよいのです。

### DefaultFileFetcher（実装）

`sample-app/src/main/java/com/example/sample/order/batch/DefaultFileFetcher.java`

```java
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
        // ...（s3://バケット/キー を分解して S3 から読む）
    }
}
```

- `implements FileFetcher` で、契約を守ることを宣言しています
- `@Override` は「インタフェースのメソッドを実装している」印です。綴りを誤るとコンパイルエラーになります
- `S3Client` は `private final` で隠され、外からは見えません（カプセル化）

### 使う側（OrderImportJob）

`sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java`

```java
private final FileFetcher fetcher;
private final OrderImportService service;

public OrderImportJob(FileFetcher fetcher, OrderImportService service) {
    this.fetcher = fetcher;
    this.service = service;
}
```

`OrderImportJob` は `DefaultFileFetcher` を知りません。`FileFetcher` だけを知っています。

### テストでの差し替え

`sample-app/src/test/java/com/example/sample/order/OrderImportJobTest.java`

```java
OrderImportJob job = new OrderImportJob(loc -> List.of(OrderImportService.HEADER, "A1,1,P,1"), service);
```

テストでは、`FileFetcher` の実装をラムダ式で渡しています。
メソッドが 1 つだけのインタフェースは、ラムダ式で実装を書けます。
これで S3 なしに、ジョブの終了コードを確かめられます。

### カプセル化の例（MemberRecord）

`sample-app/src/main/java/com/example/sample/member/MemberRecord.java` は、
フィールドを `private` にし、`id` だけに setter を用意しています。
MyBatis が採番した ID を書き戻すためで、`name` と `email` は書き換えられません。

## もし〇〇がなかったら？

もし `FileFetcher` インタフェースがなく、`OrderImportJob` が `DefaultFileFetcher` を直接使っていたら、
ジョブのテストのたびに S3 クライアントが必要になります。
「入力が無いとき終了コード 8」のような単純な確認にも、S3 エミュレータの起動が必要です。
テストは遅く、壊れやすくなり、やがて書かれなくなります。

また、将来「別のストレージから読む」ことになったとき、
インタフェースがあれば新しい実装クラスを足すだけで済みます。
なければ、ジョブ本体にも手を入れることになります。

## 理解度チェック

1. `OrderImportJob` のフィールドの型が `DefaultFileFetcher` ではなく `FileFetcher` なのはなぜですか。

    ??? note "答え"
        使う側を特定の実装に依存させないためです。
        テストではラムダ式の実装に、本番では `DefaultFileFetcher` に差し替えられます。

2. `OrderImportJobTest` で `loc -> List.of(...)` と書けるのはなぜですか。

    ??? note "答え"
        `FileFetcher` が抽象メソッドを 1 つだけ持つインタフェースだからです。
        このようなインタフェースは、ラムダ式で実装を渡せます。

3. `MemberRecord` で `id` にだけ setter があるのはなぜですか。

    ??? note "答え"
        MyBatis が登録時に採番した ID を書き戻すためです。
        `name` と `email` は書き換える必要がないので、setter を作っていません。

4. フィールドを `public` にすると、どんな問題が起きますか。

    ??? note "答え"
        どこからでも値を書き換えられ、クラスのルール（在庫が負にならない等）を守れなくなります。
        不具合が起きたとき、どこで書き換えたかを探すのも難しくなります。

## コードを読むときの確認観点

- [ ] フィールドが `private` になっているか。変わらないものに `final` が付いているか
- [ ] 不要な setter が作られていないか
- [ ] 使う側がインタフェースに依存しているか（実装クラスを `new` していないか）
- [ ] 実装メソッドに `@Override` が付いているか
- [ ] 継承を「コードの使い回し」だけの目的で使っていないか

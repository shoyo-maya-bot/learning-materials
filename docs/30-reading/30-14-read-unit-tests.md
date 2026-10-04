# 30-14 単体テストを読む

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - テストを「仕様の一覧」として読み、本体のどの動きを守っているかを説明できる
    - DB や S3 を置き換える 3 つの書き方（ラムダ、手書きの偽物、MockMvc の単独構成）を読める
    - `@ParameterizedTest` と `@CsvSource` で書かれたテストを読み、ケースを足せる
    - 本体を変えたとき、どのテストが落ちるか（落ちないか）を予想できる

## 何か

**単体テスト**は、クラスやメソッドを小さな単位で動かし、結果を確かめるコードです。
sample-app の単体テストは 4 つのクラスにあり、`./gradlew test` で実行します。

| テストクラス | 対象 | 置き換えているもの |
|---|---|---|
| `OrderImportServiceTest` | `OrderImportService` | `OrderMapper` をラムダに |
| `OrderImportJobTest` | `OrderImportJob` | `FileFetcher` と `OrderMapper` をラムダに |
| `MemberServiceTest` | `MemberService` | `MemberMapper` を手書きの偽物（`InMemoryMapper`）に |
| `MemberControllerTest` | `MemberController` + `ApiExceptionHandler` | Spring を起動せず、MockMvc の単独構成で組み立てる |

どのテストも、DB・S3・Spring の起動を使いません。
`build.gradle` 37〜43 行目のコメントにも「単体テスト（DB・外部サービス不要）」とあります。

## なぜ必要か

初めてのコードを読むとき、テストは **最良の手がかり** です。

- テストの名前は、そのクラスが守るべき動きの一覧になっている
- テストの入力と期待値は、「具体的にどう動くか」の実例になっている
- テストが無い動きは、変えても誰も気づかない動き（＝変更が危ない場所）だとわかる

本体のコードを読む前に、テストのメソッド名を並べるだけでも、全体像がつかめます。

## どうやるか

テストは、**名前 → 準備 → 実行 → 確認** の順に読みます。
準備（Arrange）・実行（Act）・確認（Assert）の 3 つに分けて読む考え方を、AAA と呼びます。

!!! failure "悪い例"
    テストを上から 1 行ずつ読み、`assertThat` の書き方に気を取られる。
    何を置き換えているか、どの本体の行を通るかを確かめていない。

!!! success "良い例"
    1. テストのメソッド名を全部並べ、「このクラスの仕様」として読む
    2. 準備の部分で、**何を置き換えているか** を確かめる（DB の代わりに何を使っているか）
    3. 実行の 1 行から、本体のどの行を通るかをたどる
    4. 確認の部分で、何を確かめていて、**何を確かめていないか** を書き出す

テストの道具の公式ドキュメントは、[JUnit 5 ユーザーガイド](https://junit.org/junit5/docs/current/user-guide/) と [AssertJ](https://assertj.github.io/doc/) です。

## サンプルアプリでは

### OrderImportServiceTest: ラムダで DB を置き換える

```java title="sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java（13〜16 行目）"
class OrderImportServiceTest {

    private final Set<String> stored = new HashSet<>();
    private final OrderImportService service = new OrderImportService(o -> stored.add(o.orderNo()) ? 1 : 0);
```

`OrderMapper` はメソッドが 1 つ（`insertIfAbsent`）だけなので、ラムダで書けます。
`Set.add` は「新しく入ったら `true`、既にあれば `false`」を返します。
これで「未登録なら 1、登録済みなら 0」という `ON CONFLICT DO NOTHING` の動きをまねています。

テストのメソッド名を並べると、30-10・30-11 で読んだ仕様がそのまま出てきます。

| メソッド（行） | 確かめていること |
|---|---|
| `importsValidLinesAndSkipsDuplicates`（18〜32） | BOM 付きの見出し、空行の読み飛ばし、ファイル内の重複 |
| `rerunIsIdempotent`（34〜43） | 2 回目はすべて `duplicated` になる |
| `badLinesAreReportedWithLineNumbersAndOthersContinue`（45〜52） | 行番号付きのエラーと、残りの行の続行 |
| `wrongHeaderIsRejected`（54〜59） | 見出しが違えば例外 |
| `parseRejects`（61〜70） | `parse` の 4 種類のエラーメッセージ |

`parseRejects` は、1 つのメソッドで複数のケースを試す書き方です。

```java title="sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java（61〜70 行目）"
    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
        "A001,1,P-01        | 列数が 4 ではありません（3 列）",
        "' ,1,P-01,1'       | order_no が空です",
        "'A001,1, ,1'       | product_code が空です",
        "A001,1,P-01,1000   | quantity は 1〜999 です（1000）"
    })
    void parseRejects(String line, String message) {
        assertThatThrownBy(() -> OrderImportService.parse(line)).hasMessage(message);
    }
```

- 62 行目: 入力の行そのものにカンマが含まれるので、区切り文字を `|` に変えています
- 64〜65 行目: `@CsvSource` は値の前後の空白を取り除きます。空白を残したいケースは `'...'` で囲みます
- 69 行目: `parse` は `static` で `private` ではないので、同じパッケージのテストから直接呼べます

### OrderImportJobTest: 終了コードを確かめる

```java title="sample-app/src/test/java/com/example/sample/order/OrderImportJobTest.java（11〜20 行目）"
class OrderImportJobTest {

    private final OrderImportService service = new OrderImportService(o -> 1);

    @Test
    void exitCodeZeroWhenAllLinesValid() {
        OrderImportJob job = new OrderImportJob(loc -> List.of(OrderImportService.HEADER, "A1,1,P,1"), service);
        job.run(new DefaultApplicationArguments("--input=orders.csv"));
        assertThat(job.getExitCode()).isZero();
    }
```

- 13 行目: Mapper は「常に 1（登録できた）」を返すラムダです
- 17 行目: `FileFetcher` もラムダです。渡された場所 `loc` は使わず、決まった行を返します
- 18 行目: `DefaultApplicationArguments` で、コマンドラインの引数を組み立てています。Spring は起動しません

このテストクラスは、`OrderImportJob` と同じ `...order.batch` パッケージではなく、`...order` パッケージにあります。
そのため、`OrderImportService.HEADER`（パッケージ内だけで見える定数）は使えますが、`OrderImportJob.WARN` などは使えません。
期待値が `4` や `8` と数字で書かれているのは、このためです（26 行目、33 行目、39 行目）。

### MemberServiceTest: 手書きの偽物

```java title="sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java（16〜40 行目を抜粋）"
    /** DB を使わない差し替え用の Mapper. */
    static class InMemoryMapper implements MemberMapper {
        final Map<Long, Member> rows = new HashMap<>();
        long seq = 0;
        // findById / existsByEmail / insert を Map で実装（21〜36 行目）
    }

    private final InMemoryMapper mapper = new InMemoryMapper();
    private final MemberService service = new MemberService(mapper);
```

`MemberMapper` はメソッドが 3 つあるので、ラムダではなくクラスとして書いています。
このような「本物の代わりに、簡単な仕組みで本当に動く部品」を **フェイク**（偽物）と呼びます。
`insert`（32〜36 行目）は、本物の DB の自動採番をまねて `++seq` で ID を振ります。

### MemberControllerTest: Spring を起動せずに HTTP を試す

```java title="sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java（24〜35 行目）"
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

- 26〜27 行目: `messages.properties` の代わりに、必要なメッセージを 1 つだけ登録しています
- 28〜29 行目: 入力チェック（`@NotBlank` など）を動かすための検証器を、手で作っています
- 30 行目: `MemberServiceTest` のフェイクを使い回しています
- 31〜34 行目: **MockMvc** は、サーバーを立てずに HTTP の要求と応答を試せる道具です。`standaloneSetup` は、指定した部品だけで組み立てる方法です

各テストで ID が 1 から始まるのは、`@BeforeEach` がテストごとに新しいフェイクを作るからです。
`registerThenGet`（37〜49 行目）で `Location` が `/api/v1/members/1` になるのも、このためです。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| ラムダ・`InMemoryMapper` | モックライブラリ（Mockito など）の `mock(...)` / `when(...)`、テスト用の偽物クラス |
| `standaloneSetup` | `@WebMvcTest` などの、Spring を部分的に起動するテスト |
| DB を使うテストが無い | DB につなぐテスト（テスト用 DB・コンテナ）の有無と、その実行方法 |
| `build.gradle` の `test` / `karateTest` | テストの種類ごとのタスク・CI の設定 |
| `build/reports/jacoco/...` | カバレッジ（テストが通った行の割合）の報告と、チームの基準 |

## もし単体テストがなかったら？

30-10 から 30-13 で読んだ動き（BOM、行番号、重複、終了コード）を変えたとき、確かめる方法は「DB と S3 を起動してバッチを動かし、ログを目で見る」だけになります。
1 回の確認に数分かかり、境界の値（数量 0 と 1000、空行、BOM の有無）をすべて試すのは現実的ではありません。

また、テストは「この動きは意図したもの」という記録でもあります。
テストが無いと、後から読んだ人は、`split(",", -1)` の `-1` が意図的なのか偶然なのかを判断できません。

## 理解度チェック

1. `OrderImportServiceTest` 16 行目のラムダは、何の動きをまねていますか。

    ??? note "答え"
        `OrderMapper.xml` の `INSERT ... ON CONFLICT (order_no) DO NOTHING` です。
        未登録の注文番号なら 1、登録済みなら 0 を返します。

2. `MemberServiceTest` で、ラムダではなくクラス（`InMemoryMapper`）を書いているのはなぜですか。

    ??? note "答え"
        `MemberMapper` に抽象メソッドが 3 つあるからです。ラムダで書けるのは、抽象メソッドが 1 つだけのインタフェースです。

3. `@CsvSource` で `' ,1,P-01,1'` を `'` で囲んでいるのはなぜですか。

    ??? note "答え"
        囲まないと、`@CsvSource` が値の前後の空白を取り除き、`,1,P-01,1` になってしまうからです。
        このケースは「先頭が空白だけの order_no」を試したいので、空白を残す必要があります。

4. 単体テストで確かめられていないものを 1 つ挙げてください。

    ??? note "答え"
        たとえば `OrderMapper.xml` の SQL（ON CONFLICT）、`S3Config` と `DefaultFileFetcher`、`@Transactional` によるロールバックです。
        どれも DB・S3・Spring の起動が必要なので、単体テストの範囲外です。

## コードを読むときの確認観点

- [ ] テストのメソッド名を並べ、対象クラスの仕様として読んだか
- [ ] 何を置き換えているか（ラムダ・フェイク・モック・Spring の部分起動）を確認したか
- [ ] 置き換えた部品が、本物と同じ動きをしているか（まね方が正しいか）を確認したか
- [ ] 境界の値（0、上限、空、BOM など）がテストされているか確認したか
- [ ] テストされていない部分（SQL・設定・トランザクション）を書き出したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **動きを予想する**: `MemberControllerTest` の `invalidInputReturns400` で、応答 JSON の `message` は何になりますか。根拠となる行を答えてください（テストは `message` を確かめていません）。
2. **どのテストが落ちるか**: `MemberService.java` 26 行目の `toLowerCase(java.util.Locale.ROOT)` を消したとき（`trim()` は残す）、失敗するテストをすべて答えてください。
3. **小さな変更**: `parseRejects` に「`member_id` が数値でない」ケースを 1 行足してください。
4. **どのテストが落ちるか**: `OrderImportService.java` 25 行目の `@Transactional` を消したとき、失敗するテストはどれですか。
5. **場所を探す**: `MemberControllerTest` の 3 つのテストのうち、`ApiExceptionHandler` を通るものはどれですか。それぞれ、ハンドラのどのメソッドを通りますか。

解答: [30-14 解答](answers/30-14.md)

# 20-07 Spring Boot の仕組み（DI）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - DI（依存性の注入）が何のためにあるかを説明できる
    - Bean がどのように登録されるか（`@Component` / `@Service` / `@Bean`）を説明できる
    - コンストラクタ注入のコードを書ける
    - サンプルアプリで `MemberController` に `MemberService` が渡る流れを読める

## 何か

### DI（依存性の注入）

あるクラスが仕事をするために使う別のオブジェクトを「依存」と呼びます。
`MemberService` にとっての `MemberMapper` が依存です。

DI とは、依存を自分で `new` せず、外から渡してもらう設計です。
Spring は、アプリの起動時にオブジェクトを作り、必要な場所へ自動で渡します。
公式ドキュメントは [Spring Framework: The IoC Container](https://docs.spring.io/spring-framework/reference/core/beans.html) です。

### Bean と DI コンテナ

Spring が作って管理するオブジェクトを **Bean** と呼びます。
Bean を作り、組み立て、保管する仕組みを **DI コンテナ**（アプリケーションコンテキスト）と呼びます。

Bean として登録する方法は主に 2 つです。

| 方法 | 書き方 | 使う場面 |
| --- | --- | --- |
| クラスに注釈を付ける | `@Component`、`@Service`、`@RestController` など | 自分で書いたクラス |
| 設定クラスのメソッドで作る | `@Configuration` のクラスに `@Bean` メソッド | ライブラリのクラスなど、注釈を付けられないもの |

`@Service` や `@RestController` は `@Component` の一種です。役割を読み手に伝えるために使い分けます。

### コンポーネントスキャン

`@SpringBootApplication` を付けたクラスのパッケージ以下から、注釈付きのクラスを自動で探して Bean にします。
これをコンポーネントスキャンと呼びます。

## なぜ必要か

依存を自分で `new` すると、次の問題が起きます。

- どの実装を使うかがクラスの中に埋め込まれ、差し替えられない
- テストで DB や S3 につながる本物の依存が必ず動く
- 同じ依存（DB 接続など）を、あちこちで別々に作ってしまう

DI を使うと、クラスは「何が必要か」をコンストラクタで宣言するだけになります。
本番では Spring が本物を、テストでは自分がテスト用の実装を渡せます。

## どうやるか

### コンストラクタ注入

!!! failure "悪い例"
    ```java
    // 例: 自分で new する
    @Service
    public class ProductService {
        private final ProductMapper mapper = new ProductMapperImpl();
    }
    ```

!!! failure "悪い例"
    ```java
    // 例: フィールドに @Autowired（フィールド注入）
    @Service
    public class ProductService {
        @Autowired
        private ProductMapper mapper;
    }
    ```
    `final` にできず、テストで `new ProductService()` したときに `mapper` が `null` のままになります。

!!! success "良い例"
    ```java
    // 例: コンストラクタで受け取る（コンストラクタ注入）
    @Service
    public class ProductService {
        private final ProductMapper mapper;

        public ProductService(ProductMapper mapper) {
            this.mapper = mapper;
        }
    }
    ```

コンストラクタが 1 つだけなら、`@Autowired` は不要です。Spring が自動でそのコンストラクタを使います。
フィールドを `final` にでき、テストでは普通に `new` して依存を渡せます。

### インタフェースで受け取る

依存の型はできるだけインタフェースにします。
実装が 1 つだけ Bean として登録されていれば、Spring がそれを渡します。
同じインタフェースの実装が 2 つ以上あると、どれを渡すか決められず起動時にエラーになります。

### Bean の寿命

Bean は、既定ではアプリ全体で 1 つだけ作られます（シングルトン）。
複数のリクエストから同時に使われるので、Bean のフィールドにリクエストごとの値を保存してはいけません。

!!! failure "悪い例"
    ```java
    // 例: リクエストごとの値を Bean のフィールドに置く
    @Service
    public class CartService {
        private long currentMemberId; // 他のリクエストに上書きされる
    }
    ```

!!! success "良い例"
    ```java
    // 例: リクエストごとの値は引数で渡す
    @Service
    public class CartService {
        public void add(long memberId, String productCode) { /* ... */ }
    }
    ```

## サンプルアプリでは

### 起動クラス

`sample-app/src/main/java/com/example/sample/SampleApplication.java`

<!-- src: sample-app/src/main/java/com/example/sample/SampleApplication.java @exercise-base -->
```java
@SpringBootApplication
public class SampleApplication {

    public static void main(String[] args) {
        ConfigurableApplicationContext ctx = SpringApplication.run(SampleApplication.class, args);
        // ...
    }
}
```

`com.example.sample` 以下のクラスがコンポーネントスキャンの対象です。
`SpringApplication.run` の戻り値 `ctx` が DI コンテナです。

### 依存の連鎖

会員 API では、次の順で依存がつながっています。

```text
MemberController ──> MemberService ──> MemberMapper
 (@RestController)     (@Service)        (@Mapper)
```

`sample-app/src/main/java/com/example/sample/member/MemberController.java`

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java @exercise-base -->
```java
private final MemberService service;

public MemberController(MemberService service) {
    this.service = service;
}
```

`sample-app/src/main/java/com/example/sample/member/MemberService.java`

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java @exercise-base -->
```java
private final MemberMapper mapper;

public MemberService(MemberMapper mapper) {
    this.mapper = mapper;
}
```

どちらもコンストラクタ注入です。`@Autowired` は書かれていません。
`MemberMapper` はインタフェースで、`@Mapper` が付いています。
MyBatis の Spring Boot 連携が、SQL を実行する実装を作って Bean にします（[20-12 MyBatis](20-12-mybatis.md)）。

### @Bean で作る（S3Config）

`sample-app/src/main/java/com/example/sample/order/batch/S3Config.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/S3Config.java @exercise-base -->
```java
@Configuration
public class S3Config {

    @Bean
    public S3Client s3Client(
            @Value("${app.s3.region:ap-northeast-1}") String region,
            @Value("${app.s3.endpoint:}") String endpoint,
            @Value("${app.s3.access-key:test}") String accessKey,
            @Value("${app.s3.secret-key:test}") String secretKey) {
        S3ClientBuilder b = S3Client.builder().region(Region.of(region));
        // ...（エンドポイントの有無で接続先と認証情報を切り替える）
        return b.build();
    }
}
```

`S3Client` は AWS SDK のクラスなので、`@Component` を付けられません。
そこで `@Bean` メソッドで作って登録しています。
この Bean が `DefaultFileFetcher` のコンストラクタに渡ります。
`@Value` は設定値を受け取る注釈です（[20-08 設定ファイルとプロファイル](20-08-config-profile.md)）。

### インタフェースで受け取る（OrderImportJob）

`sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java`

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @exercise-base -->
```java
@Component
@ConditionalOnProperty(name = "app.batch.job", havingValue = "JOB0001")
public class OrderImportJob implements ApplicationRunner, ExitCodeGenerator {
    // ...
    public OrderImportJob(FileFetcher fetcher, OrderImportService service) {
```

`FileFetcher` の実装は `DefaultFileFetcher` だけなので、Spring はそれを渡します。
`@ConditionalOnProperty` は「設定 `app.batch.job` が `JOB0001` のときだけ Bean にする」指定です。
API として起動したときは、このジョブは作られません。

### テストでは自分で組み立てる

`sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java`

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java @exercise-base -->
```java
private final InMemoryMapper mapper = new InMemoryMapper();
private final MemberService service = new MemberService(mapper);
```

テストでは Spring を起動せず、`MemberMapper` のテスト用実装を自分で渡しています。
コンストラクタ注入だから、このように素直に書けます。

## もし〇〇がなかったら？

もし DI がなく、`MemberService` が中で MyBatis の実装を `new` していたら、
`MemberServiceTest` は DB なしでは動きません。
テストのたびに DB を用意し、データを消し、と準備が重くなり、単体テストは数秒から数分に延びます。

また、DB 接続のような重いオブジェクトを各クラスが別々に作ると、接続数が増えすぎて DB に負担をかけます。
Spring が 1 つだけ作って共有することで、これを防いでいます。

## 理解度チェック

1. `MemberService` のコンストラクタに `@Autowired` がないのに、`MemberMapper` が渡されるのはなぜですか。

    ??? note "答え"
        コンストラクタが 1 つだけのとき、Spring はそのコンストラクタを自動で使うためです。

2. `S3Client` を `@Component` ではなく `@Bean` で登録しているのはなぜですか。

    ??? note "答え"
        `S3Client` はライブラリのクラスで、注釈を付けられないためです。
        `@Bean` メソッドで設定値を使って作り、登録しています。

3. フィールド注入（`@Autowired private X x;`）よりコンストラクタ注入がよい理由を 2 つ挙げてください。

    ??? note "答え"
        フィールドを `final` にできること。
        テストで Spring を起動せずに `new` して依存を渡せることです。

4. API として起動したとき、`OrderImportJob` が Bean にならないのはなぜですか。

    ??? note "答え"
        `@ConditionalOnProperty` により、`app.batch.job=JOB0001` が指定されたときだけ Bean になるためです。

## コードを読むときの確認観点

- [ ] 依存をコンストラクタで受け取り、フィールドが `final` になっているか
- [ ] Bean の中で、別の Bean を `new` していないか
- [ ] 依存の型がインタフェースになっているか（差し替えが必要な場合）
- [ ] Bean のフィールドに、リクエストごとの値を保存していないか
- [ ] `@Service` / `@Component` / `@RestController` の役割が実態と合っているか

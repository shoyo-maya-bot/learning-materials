# 40-01 非同期処理の基本（スレッド・@Async・タイムアウト）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 同期処理と非同期処理の違いを、利用者の待ち時間の観点で説明できる
    - `@Async` を使うときの落とし穴（同じクラス内の呼び出し、例外、トランザクション）を説明できる
    - 外部呼び出しや DB 操作にタイムアウトを設定するコードを書ける
    - 処理を同期にするか非同期にするかを、理由を付けて選べる

## 何か

**同期処理** は、呼び出した処理が終わるまで呼び出し元が待つ方式です。
**非同期処理** は、処理を依頼したら終わりを待たずに次へ進む方式です。
結果は後で受け取るか、受け取らずに済ませます。

Java では、処理を並行して動かす単位を **スレッド** と呼びます。
Web アプリでは、1 つのリクエストを 1 つのスレッドが担当するのが基本です。
非同期処理は「別のスレッド」または「別のプロセス」に仕事を渡すことで実現します。

| 方式 | 仕事の渡し先 | 例 |
| --- | --- | --- |
| スレッドで非同期 | 同じアプリ内の別スレッド | Spring の `@Async`、`CompletableFuture` |
| キューで非同期 | 別のプロセス（別のコンテナ） | SQS に送り、受信側が処理する（[40-02](40-02-queue-retry-idempotency.md)） |
| 定刻で後回し | 決まった時刻に起動するバッチ | EventBridge Scheduler → Step Functions → バッチ |

**タイムアウト** は「この時間を過ぎたら待つのをやめる」という上限です。
同期でも非同期でも、待つ処理には必ず必要になります。

## なぜ必要か

利用者を長く待たせないためです。
たとえば「注文を受け付けたら確認メールを送る」処理を考えます。
メール送信に 3 秒かかると、同期処理では注文 API の応答も 3 秒遅れます。
メール送信は注文の成否に関係ないので、後で行えば十分です。

一方で、非同期処理には代償があります。

- 処理の失敗が、呼び出し元にその場で伝わらない
- 処理の順番や完了のタイミングが保証されない
- ログを追いにくくなる（スレッドやプロセスがまたがる）

「速くなるから全部非同期」ではありません。
**結果がすぐ必要か** で使い分けるのが基本です。

タイムアウトが必要なのは、相手が応答しないときにスレッドが止まり続けるからです。
スレッドの数には上限があります。
止まったスレッドが増えると、関係のないリクエストまで処理できなくなります。

## どうやるか

### 同期と非同期の使い分け

| 判断の観点 | 同期を選ぶ | 非同期を選ぶ |
| --- | --- | --- |
| 結果が応答に必要か | 必要（例: 会員の照会結果） | 不要（例: 通知メール、集計の更新） |
| 失敗をその場で伝えるか | 伝える（例: 入力誤り、在庫不足） | 後で再試行すればよい |
| 処理時間 | 短い（目安 1 秒未満） | 長い、または読めない |
| 失ってよいか | — | 失ってはいけないなら、スレッドではなくキューを使う |

最後の行が大切です。
`@Async` で別スレッドに渡した仕事は、アプリが停止すると消えます。
ECS のタスクは、デプロイや台数の変更で止まることがあります。
失ってはいけない仕事は、SQS などの外部のキューに置いてください。

### @Async の使い方

Spring では、メソッドに `@Async` を付けると別スレッドで実行されます。
有効にするには、設定クラスに `@EnableAsync` が必要です。

例:

```java
@Configuration
@EnableAsync
public class AsyncConfig {
}

@Service
public class NotificationService {

    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    @Async
    public void sendOrderMail(String orderNo) {
        // 呼び出し元とは別のスレッドで動く
        log.info("注文確認メールを送ります orderNo={}", orderNo);
    }
}
```

`@Async` は、Spring が作る **プロキシ**（呼び出しを横取りする代理のオブジェクト）で動きます。
そのため、次の落とし穴があります。

!!! failure "悪い例"
    ```java
    @Service
    public class OrderService {

        public void accept(String orderNo) {
            // ...注文を登録...
            sendMail(orderNo); // 同じクラスの中から呼ぶと、プロキシを通らない
        }

        @Async
        public void sendMail(String orderNo) {
            // 非同期にならず、accept と同じスレッドで動く
        }
    }
    ```

!!! success "良い例"
    ```java
    @Service
    public class OrderService {

        private final NotificationService notification;

        public OrderService(NotificationService notification) {
            this.notification = notification;
        }

        public void accept(String orderNo) {
            // ...注文を登録...
            notification.sendOrderMail(orderNo); // 別の Bean 経由で呼ぶ
        }
    }
    ```

ほかにも次の点に注意します。

- **戻り値**: `void` か `CompletableFuture<T>` にします。結果が要るなら `CompletableFuture` を返します
- **例外**: `void` のメソッドで起きた例外は、呼び出し元に届きません。ログに残す仕組みを用意します
- **トランザクション**: `@Transactional` はスレッドをまたぎません。別スレッドでは別のトランザクションになります
- **コミット前の呼び出し**: トランザクション中に非同期処理を始めると、まだコミットされていないデータを読みにいくことがあります
- **スレッド数**: 既定のスレッドプールの設定を確認し、上限と待ち行列の長さを決めます

### タイムアウトを設定する

外部の API を呼ぶときは、**接続タイムアウト** と **読み取りタイムアウト** を設定します。
接続タイムアウトは「つながるまで」、読み取りタイムアウトは「応答が来るまで」の上限です。

!!! failure "悪い例"
    ```java
    // タイムアウトを指定していない。相手が応答しないと、いつまでも待つ
    RestClient client = RestClient.create();
    String body = client.get().uri("https://partner.example.com/stock").retrieve().body(String.class);
    ```

!!! success "良い例"
    ```java
    SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
    factory.setConnectTimeout(Duration.ofSeconds(2));
    factory.setReadTimeout(Duration.ofSeconds(5));
    RestClient client = RestClient.builder().requestFactory(factory).build();
    ```

DB にも上限を設けます。
MyBatis では、SQL 1 本ごとの上限を設定できます。

例:

```yaml
mybatis:
  configuration:
    default-statement-timeout: 10   # 秒
```

非同期処理の結果を待つときも、上限を付けます。

例:

```java
CompletableFuture<String> future = stockClient.fetchAsync(productCode);
String stock = future.orTimeout(5, TimeUnit.SECONDS).join(); // 5 秒で TimeoutException
```

タイムアウトの値は、勘で決めずに設計書に書きます。
目安は「相手の通常の応答時間に余裕を足した値」です。
また、呼び出し元のタイムアウトより短くします。
利用者がもう待っていないのに処理を続けても、無駄になるからです。

## サンプルアプリでは

sample-app には、`@Async`・`@EnableAsync`・`CompletableFuture` を使うコードはありません。
タイムアウトの設定もありません。
API もバッチも、1 つのスレッドで順に処理する同期処理です。

ただし、システム全体で見ると「後回し」の仕組みはあります。
注文ファイル取込（JOB0001）は、API ではなくバッチとして動きます。
バッチは `sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java` です。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @exercise-base -->
```java
@Component
@ConditionalOnProperty(name = "app.batch.job", havingValue = "JOB0001")
public class OrderImportJob implements ApplicationRunner, ExitCodeGenerator {
```

クラウドでは、このバッチを定刻に起動します。
構成は `dev-environment` の `cloud/modules/batch-workflow/main.tf` にあります。

<!-- src: cloud/modules/batch-workflow/main.tf @exercise-base -->
```hcl
resource "aws_scheduler_schedule" "this" {
  count                        = var.schedule_expression == null ? 0 : 1
  name                         = var.name
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Asia/Tokyo"
```

Step Functions は `arn:aws:states:::ecs:runTask.sync` でバッチを起動し、終了を待ちます。
利用者は待たずに済み、処理の成否は Step Functions の実行結果と終了コードで分かります。
これは「定刻で後回し」の型の非同期処理です。

また、クラウド構成には SQS のキューも用意されています（`cloud/environments/dev1/main.tf` の `module "async_queue"`）。
キューを使う非同期処理は [40-02](40-02-queue-retry-idempotency.md) で学びます。

## もしタイムアウトがなかったら？

外部の在庫 API が、障害で応答を返さなくなったとします。
タイムアウトが無いと、在庫を確認する注文 API のスレッドが 1 本ずつ止まっていきます。
やがてスレッドが尽き、在庫と関係のない会員照会 API まで応答しなくなります。
1 つの外部障害が、システム全体の停止に広がるわけです。

さらに、ロードバランサの側で先にタイムアウトが起きると、利用者にはエラーが返ります。
しかしアプリの中では処理が続き、後で登録だけ成功することがあります。
利用者は失敗したと思って再送し、二重登録になります。
タイムアウトの値は、呼び出しの階層ごとに「内側ほど短く」そろえておく必要があります。

## 理解度チェック

1. 「注文を登録して、確認メールを送る」処理で、メール送信を非同期にしてよい理由を説明してください。

    ??? note "答え"
        メール送信の結果は、注文 API の応答に必要ないからです。
        送信に失敗しても注文は成立しており、後で再送すれば済みます。
        ただし、メールを失ってはいけない業務なら、`@Async` ではなくキューに置きます。

2. 同じクラスの中から `@Async` のメソッドを呼ぶと、非同期にならないのはなぜですか。

    ??? note "答え"
        `@Async` は Spring のプロキシが呼び出しを横取りして、別スレッドに渡す仕組みだからです。
        同じクラスの中の呼び出しは `this` を直接呼ぶので、プロキシを通りません。

3. `@Async` のメソッドの中で `@Transactional` の処理を呼ぶと、呼び出し元と同じトランザクションになりますか。

    ??? note "答え"
        なりません。
        トランザクションはスレッドに結び付いているため、別スレッドでは別のトランザクションになります。
        呼び出し元がロールバックしても、非同期側の更新は残ります。

4. 接続タイムアウトと読み取りタイムアウトの違いを説明してください。

    ??? note "答え"
        接続タイムアウトは、相手につながるまでの上限です。
        読み取りタイムアウトは、つながった後に応答が届くまでの上限です。
        相手が落ちているときは前者、処理が遅いときは後者で打ち切られます。

5. sample-app の JOB0001 は、どのような形の「後回し」で動いていますか。

    ??? note "答え"
        EventBridge Scheduler が定刻に Step Functions を起動し、Step Functions が ECS タスクとしてバッチを動かします。
        利用者の操作とは切り離された、定刻起動の非同期処理です。

## コードを読むときの確認観点

- [ ] 非同期にした処理の結果が、本当に応答に不要か
- [ ] `@Async` のメソッドを、同じクラスの中から呼んでいないか
- [ ] `void` の `@Async` メソッドの例外が、ログなどで確認できるか
- [ ] 失ってはいけない仕事を、スレッドに渡して済ませていないか（キューを使うべきか）
- [ ] 外部呼び出し・DB 操作・非同期の結果待ちに、タイムアウトが設定されているか
- [ ] タイムアウトの値が設計書にあり、呼び出し元の値より短いか

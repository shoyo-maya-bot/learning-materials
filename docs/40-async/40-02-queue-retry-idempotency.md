# 40-02 キュー・再試行・冪等性（SQS）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - メッセージキュー（SQS）を使った非同期処理の流れを説明できる
    - 「少なくとも 1 回の配信」が受信側に何を求めるかを説明できる
    - 再試行・デッドレターキュー（DLQ）・可視性タイムアウトの関係を説明できる
    - 同じメッセージを 2 回受け取っても結果が変わらない（冪等な）受信処理を書ける

## 何か

**メッセージキュー** は、送り手と受け手の間に置く「仕事の待ち行列」です。
送り手はメッセージ（仕事の内容）をキューに入れ、すぐに次へ進みます。
受け手は自分のペースでメッセージを取り出し、処理します。
AWS では **SQS**（Simple Queue Service）がこの役割を持ちます。

SQS の処理は、次の 3 段階で進みます。

1. 送信（`SendMessage`）: 送り手がメッセージを入れる
2. 受信（`ReceiveMessage`）: 受け手が取り出す。この間、メッセージは他の受け手から見えなくなる
3. 削除（`DeleteMessage`）: 処理に成功した受け手が、メッセージを消す

この章で使う用語を先にまとめます。

| 用語 | 意味 |
| --- | --- |
| 少なくとも 1 回の配信 | メッセージは必ず届くが、同じものが 2 回以上届くこともある、という約束 |
| 可視性タイムアウト | 受信したメッセージを、他の受け手から見えなくしておく時間 |
| 再試行 | 失敗した処理をもう一度行うこと。SQS では「削除されずに見えるようになる」ことで起きる |
| デッドレターキュー（DLQ） | 何度試しても失敗するメッセージを移す、隔離用のキュー |
| 冪等性（べきとうせい） | 同じ処理を何回行っても、結果が 1 回行ったときと同じになる性質 |

## なぜ必要か

[40-01](40-01-async-basics.md) で見たように、`@Async` で渡した仕事はアプリが止まると消えます。
キューに入れたメッセージは、アプリが止まっても残ります。
受け手が復旧すれば、続きから処理できます。

また、送り手と受け手を切り離せます。
受け手が一時的に遅くても、メッセージはキューにたまるだけです。
送り手の API の応答は遅くなりません。

ただし、SQS の標準キューは **少なくとも 1 回の配信** です。
同じメッセージが 2 回届くことは、障害ではなく仕様です。
受信処理が冪等でないと、二重登録や二重送信が起きます。
「キューを使う」と「受信処理を冪等にする」は、必ずセットで考えてください。

## どうやるか

### 送信と受信の基本

AWS SDK for Java 2.x の `SqsClient` を使います。
sample-app の依存関係には SQS が無いので、使うときは `software.amazon.awssdk:sqs` を足します。

例（送信）:

```java
String body = "{\"orderNo\":\"" + orderNo + "\"}";
sqs.sendMessage(SendMessageRequest.builder()
        .queueUrl(queueUrl)
        .messageBody(body)
        .build());
```

例（受信して処理し、成功したら削除）:

```java
ReceiveMessageResponse res = sqs.receiveMessage(ReceiveMessageRequest.builder()
        .queueUrl(queueUrl)
        .maxNumberOfMessages(10)
        .waitTimeSeconds(20)   // ロングポーリング: 最大 20 秒、メッセージが来るまで待つ
        .build());
for (Message m : res.messages()) {
    try {
        handler.handle(m.messageId(), m.body());
        sqs.deleteMessage(DeleteMessageRequest.builder()
                .queueUrl(queueUrl)
                .receiptHandle(m.receiptHandle())
                .build());
    } catch (Exception e) {
        // 削除しない → 可視性タイムアウトの後に再び受信される（再試行）
        log.warn("処理に失敗しました messageId={}", m.messageId(), e);
    }
}
```

大切なのは **削除の順番** です。
処理に成功してから削除します。
先に削除すると、処理に失敗したときにメッセージが失われます。

### 可視性タイムアウト

受信したメッセージは、可視性タイムアウトの間だけ他から見えなくなります。
その間に削除されなければ、再び見えるようになり、別の受け手が受信します。

!!! failure "悪い例"
    ```text
    可視性タイムアウト: 30 秒
    1 件の処理時間:     最大 60 秒
    → 処理中に別の受け手が同じメッセージを受信し、同時に 2 回処理される
    ```

!!! success "良い例"
    ```text
    可視性タイムアウト: 300 秒（処理時間の最大値より十分長く）
    1 件の処理時間:     最大 60 秒
    → 処理が長引く場合は ChangeMessageVisibility で延長する
    ```

一方で、長すぎると失敗したメッセージの再試行が遅れます。
「処理時間の最大値 ＜ 可視性タイムアウト」を守った上で、再試行までの待ち時間として妥当な値にします。

### 再試行と DLQ

受け手が失敗すると、メッセージは削除されずに残り、再び受信されます。
これが SQS の再試行です。
同じメッセージが **最大受信回数**（`maxReceiveCount`）を超えると、DLQ に移されます。

失敗には 2 種類あります。

| 種類 | 例 | 再試行で直るか | 扱い |
| --- | --- | --- | --- |
| 一時的な失敗 | DB の接続切れ、相手 API の一時停止、タイムアウト | 直ることが多い | 再試行する |
| 恒久的な失敗 | メッセージの形式誤り、存在しない会員 ID | 何回やっても直らない | ログを残して DLQ へ。原因を直してから再投入 |

DLQ は「捨て場」ではありません。
DLQ にメッセージが入ったら監視で気付けるようにし、運用の手順で原因を調べます。
原因を直したら、DLQ から元のキューへメッセージを戻して処理し直します。

再試行の間隔は、だんだん長くする（**指数バックオフ**）のが一般的です。
すぐに再試行すると、弱っている相手にさらに負荷をかけるからです。

### 冪等な受信処理

同じメッセージが 2 回届いても、結果が変わらないようにします。
よく使う方法は 2 つです。

1. **業務キーの一意制約で重複を弾く**: 注文番号などに一意制約を付け、既にあれば登録しない
2. **処理済みのメッセージを記録する**: メッセージ ID を処理済みテーブルに入れ、既にあれば何もしない

!!! failure "悪い例"
    ```java
    @Transactional
    public void handle(String messageId, String body) {
        OrderMessage msg = parse(body);
        pointMapper.addPoint(msg.memberId(), 100); // 2 回届くと 200 ポイント加算される
    }
    ```

!!! success "良い例"
    ```java
    @Transactional
    public void handle(String messageId, String body) {
        // INSERT ... ON CONFLICT (message_id) DO NOTHING。登録できなければ処理済み
        if (processedMapper.insertIfAbsent(messageId) == 0) {
            log.info("処理済みのため飛ばします messageId={}", messageId);
            return;
        }
        OrderMessage msg = parse(body);
        pointMapper.addPoint(msg.memberId(), 100);
    }
    ```

良い例では、処理済みの記録と業務の更新を **同じトランザクション** で行っています。
途中で失敗すれば両方ロールバックされ、再試行で最初からやり直せます。

!!! warning "DB の更新と送信は同時に確定しない"
    「DB に登録してコミットし、その後に SQS へ送信する」処理では、送信だけ失敗することがあります。
    逆に「送信してから DB をコミット」すると、DB だけ失敗することがあります。
    どちらが起きても困る業務では、送信予定を DB に記録して別の処理で送る方式（アウトボックス）を検討します。
    設計書に「どちらかが失敗したらどうするか」を書いておくことが出発点です。

## サンプルアプリでは

sample-app には、SQS を使うコードはありません。
近い実物を 2 つ見ます。

1 つ目は、SQS のキューそのものです。
`dev-environment` の `cloud/modules/sqs-queue/main.tf` で、キューと DLQ を作っています。

```hcl
resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}
```

`cloud/modules/sqs-queue/variables.tf` の既定値は次のとおりです。

| 変数 | 既定値 | 意味 |
| --- | --- | --- |
| `visibility_timeout_seconds` | 300 | 処理中のメッセージを他から見えなくする時間（処理時間より長く） |
| `max_receive_count` | 5 | この回数失敗したらデッドレターキューへ |

DLQ は `message_retention_seconds = 1209600`（14 日）で、調べる時間を確保しています。

2 つ目は、冪等な登録です。
`sample-app/src/main/resources/mapper/OrderMapper.xml` の `insertIfAbsent` を見ます。

```xml
<!-- 注文番号が既にあれば何もしない（再実行しても重複しない） -->
<insert id="insertIfAbsent">
  INSERT INTO orders (order_no, member_id, product_code, quantity)
  VALUES (#{orderNo}, #{memberId}, #{productCode}, #{quantity})
  ON CONFLICT (order_no) DO NOTHING
</insert>
```

`ON CONFLICT (order_no) DO NOTHING` は、主キーが重複したら何もしない、という PostgreSQL の書き方です。
戻り値は登録した件数なので、既にあれば 0 になります。
`OrderImportService.importLines` はこの値で「登録」と「重複」を数え分けています。

```java
if (mapper.insertIfAbsent(order) == 1) {
    imported++;
} else {
    duplicated++;
}
```

これはバッチの再実行に備えた仕組みですが、考え方は SQS の受信処理と同じです。
「同じものが 2 回来ても、結果は 1 回分」を、DB の一意制約で保証しています。
この性質は、単体テスト `sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java` の `rerunIsIdempotent` で確かめています。
詳しくは [30-11 冪等な登録](../30-reading/30-11-idempotent-insert.md) で読みます。

再試行の実物は、`cloud/modules/batch-workflow/main.tf` の Step Functions にもあります。

```hcl
Retry = [{
  ErrorEquals     = ["ECS.AmazonECSException"]
  IntervalSeconds = 30
  MaxAttempts     = 2
  BackoffRate     = 2
}]
```

ECS タスクの起動の失敗（一時的な失敗）だけを、30 秒・60 秒と間隔を倍にして 2 回まで再試行します。
バッチの業務エラー（終了コード 4 や 8）は再試行の対象にしていません。
「一時的な失敗だけを再試行する」の具体例です。

## もし冪等性がなかったら？

ポイント加算のメッセージを処理した直後、削除する前に受け手のコンテナが止まったとします。
メッセージは削除されていないので、可視性タイムアウトの後に別の受け手が受信します。
冪等でない処理だと、ポイントがもう一度加算されます。

この種の不具合は、テスト環境ではほとんど再現しません。
本番でデプロイや障害が重なったときにだけ起き、原因の調査にも時間がかかります。
「少なくとも 1 回の配信」は、設計の段階で受け入れておくべき前提です。

## 理解度チェック

1. 受信処理で、メッセージの削除を処理の前に行うと何が起きますか。

    ??? note "答え"
        処理に失敗したとき、メッセージが既に消えているので再試行されません。
        仕事が失われます。削除は処理に成功した後に行います。

2. 可視性タイムアウトが処理時間より短いと、何が起きますか。

    ??? note "答え"
        処理中にメッセージが再び見えるようになり、別の受け手が同じメッセージを受信します。
        同じ仕事が同時に 2 回動きます。

3. sample-app のクラウド構成で、同じメッセージの処理に 5 回失敗すると、そのメッセージはどうなりますか。

    ??? note "答え"
        `max_receive_count` の既定値 5 を超えるので、DLQ（`<name>-dlq`）に移されます。
        DLQ では 14 日間保持されるので、その間に原因を調べ、直してから元のキューへ戻します。

4. 「メッセージの形式誤り」で失敗したメッセージを、何度も再試行する意味はありますか。

    ??? note "答え"
        ありません。恒久的な失敗なので、何回やっても直りません。
        ログに理由を残し、DLQ に送って人が調べます。

5. `OrderMapper.xml` の `insertIfAbsent` は、どのようにして冪等性を保証していますか。

    ??? note "答え"
        `orders` テーブルの主キー `order_no` と `ON CONFLICT (order_no) DO NOTHING` で、同じ注文番号の 2 回目の登録を無視しています。
        戻り値が 0 なら登録済みと分かります。

## コードを読むときの確認観点

- [ ] メッセージの削除が、処理に成功した後に行われているか
- [ ] 同じメッセージが 2 回届いても結果が変わらないか（一意制約・処理済みの記録）
- [ ] 処理済みの記録と業務の更新が、同じトランザクションにあるか
- [ ] 一時的な失敗と恒久的な失敗を区別し、恒久的な失敗を無駄に再試行していないか
- [ ] 可視性タイムアウトが、1 件の処理時間の最大値より長いか
- [ ] DLQ に入ったときに気付ける監視と、戻す手順が決まっているか

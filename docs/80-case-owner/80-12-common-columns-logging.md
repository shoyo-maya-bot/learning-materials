# 80-12 共通項目の部品とログレベルの運用

!!! abstract "到達目標"
    - テーブルの共通項目（作成日時・更新日時・作成者など）を、部品にまとめて設定する目的と仕組みを説明できる
    - 共通項目の設定漏れを、自分で見つけて直せる
    - INFO・WARN・ERROR の使い分けと、その理由を運用の観点で説明できる
    - ログレベルを誤ったときに、運用で何が起きるか（監視の見逃し・誤報）を説明できる

## 何か

### 共通項目

多くのテーブルには、業務の項目とは別に、どのテーブルにも同じ形で持つ **共通項目** があります。

| 共通項目の例 | 目的 |
|---|---|
| 作成日時・作成者 | いつ・だれ（どの処理）が作ったかを後から追う |
| 更新日時・更新者 | いつ・だれが最後に変えたかを追う |
| 版番号 | 同時に更新されたことを見つける（楽観的排他制御） |

共通項目は、テーブルごとに手で値を入れると、必ずどこかで漏れます。
そのため、値を入れる処理を **部品** にまとめます。

| 部品のやり方 | 仕組み |
|---|---|
| 共通の基底クラスを継承する | Entity が基底クラスを継承し、基底クラスのメソッドで値を入れる |
| ORM の仕組みで差し込む | SQL の実行の前に、共通の処理を挟む（MyBatis のプラグイン。[設定（MyBatis）](https://mybatis.org/mybatis-3/ja/configuration.html) の plugins） |
| DB の既定値 | 列の `DEFAULT now()` で、INSERT のときに DB が値を入れる |

### ログレベルの運用

ログレベルの基本は [20-14 ログ](../20-basics/20-14-logging.md) で学びました。
この章では、ログが **運用の監視** にどう使われるかから、レベルの選び方を考えます。

| レベル | 運用での扱いの例 |
|---|---|
| ERROR | 監視の仕組みが検知し、担当者に知らせる（夜間でも） |
| WARN | 翌営業日に確認する。件数が急に増えたら調べる |
| INFO | ふだんは見ない。障害の調査や、件数の記録に使う |

## なぜ必要か

作業担当は、手順どおりに部品を使い、指示されたメッセージ ID とレベルで書ければ十分です。
案件担当は、ルールの目的を理解し、漏れや誤りを自分で見つけて直す必要があります。

共通項目が漏れると、障害の調査で「このデータはいつ変わったのか」が分からなくなります。
ログレベルを誤ると、監視の仕組みが正しく働きません。
どちらも、作った直後には何も困らず、運用に入ってから問題になります。

## どうやるか

### 1. 共通項目の部品を正しく使う

例:

```java
// 例: 共通項目を持つ基底クラス
public abstract class AuditedEntity {

    private OffsetDateTime createdAt;
    private String createdBy;
    private OffsetDateTime updatedAt;
    private String updatedBy;

    /** 登録の前に呼ぶ. */
    public void stampForInsert(String user, OffsetDateTime now) {
        this.createdAt = now;
        this.createdBy = user;
        this.updatedAt = now;
        this.updatedBy = user;
    }

    /** 更新の前に呼ぶ. */
    public void stampForUpdate(String user, OffsetDateTime now) {
        this.updatedAt = now;
        this.updatedBy = user;
    }
}
```

### 2. 漏れを見つける

漏れやすいのは、次の場面です。

| 漏れやすい場面 | 理由 |
|---|---|
| UPDATE 文 | DB の `DEFAULT` は、INSERT で列の値を省いたときに使われる（[Default Values（PostgreSQL）](https://www.postgresql.org/docs/current/ddl-default.html)）。UPDATE では変わらないので、更新日時は自分で入れる必要がある |
| 一括の登録・更新（`INSERT ... SELECT` など） | Entity を通らないので、基底クラスのメソッドが呼ばれない |
| 新しく作ったテーブル | 基底クラスの継承や、列の定義を忘れる |

見つけ方です。

1. Mapper XML の `INSERT`・`UPDATE` を全部検索し、共通項目の列があるかを 1 つずつ確かめる
2. テーブル定義（DDL）を検索し、共通項目の列が無いテーブルを探す
3. テストで、登録・更新の後に共通項目が入っているかを確かめる

!!! failure "悪い例"
    ```xml
    <!-- 例: 更新日時を更新していない -->
    <update id="updateQuantity">
      UPDATE orders SET quantity = #{quantity} WHERE order_no = #{orderNo}
    </update>
    ```

!!! success "良い例"
    ```xml
    <!-- 例: 更新日時・更新者も更新する -->
    <update id="updateQuantity">
      UPDATE orders
         SET quantity = #{quantity}, updated_at = #{updatedAt}, updated_by = #{updatedBy}
       WHERE order_no = #{orderNo}
    </update>
    ```

### 3. ログレベルを選ぶ

迷ったら、「このログが出たとき、運用の担当者は何をすべきか」を考えます。

| 運用の担当者がすべきこと | レベル |
|---|---|
| 今すぐ対応する（処理が止まった、データが壊れた可能性がある） | ERROR |
| 後で確認する（処理は続いたが、人の確認が要る） | WARN |
| 何もしない（正常な流れの記録） | INFO |

| 誤り | 運用で起きること |
|---|---|
| 想定内の業務エラー（入力の誤りなど）を ERROR にする | 夜間に担当者が呼び出されるが、対応は要らない（誤報）。誤報が続くと、本当の ERROR も軽く扱われる |
| 処理が止まったのに WARN や INFO にする | 監視が検知せず、だれも気づかない（見逃し）。翌朝、後続の処理が動いていないことで初めて分かる |
| 1 行ごとに INFO を出す | ログが膨らみ、大事なログが埋もれる。保管の費用も増える |

## サンプルアプリでは

sample-app の共通項目は、DB の既定値で入れています。
`local/db/init/01_schema.sql` の `orders` テーブルです。

<!-- src: local/db/init/01_schema.sql @main -->
```sql
imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

`OrderMapper.xml` の INSERT には `imported_at` が書かれていません。
DB の `DEFAULT now()` が、登録した時刻を入れます。
sample-app には注文を更新する SQL が無いので、更新日時は持っていません。
更新の SQL を足すなら、更新日時の列と、その値を入れる仕組みも合わせて足す必要があります。

ログレベルは、ジョブの結果に合わせて使い分けています。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @main -->
```java
r.errors().forEach(e -> log.warn("{} {}", MessageIds.IMPORT_LINE_SKIPPED, e));
r.conflicts().forEach(c -> log.warn("{} {}", MessageIds.IMPORT_CONFLICT, c));
```

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @main -->
```java
log.error("{} JOB0001 異常終了", MessageIds.BATCH_FAILED, e);
```

形式エラーの行は、取込を続けたうえで人が後で確かめればよいので WARN です。
異常終了は、取込が 1 件もされていない（[80-10](80-10-commit-unit.md)）ので ERROR です。
メッセージ ID の形式（`APP` + 種別 + 4 桁）も、種別でレベルが分かるようにしています（[30-05](../30-reading/30-05-message-ids.md)）。

<!-- src: sample-app/src/main/java/com/example/sample/common/MessageIds.java @main -->
```java
 * <p>形式: APP + 種別（I=情報 / W=警告 / E=エラー）+ 4 桁。実案件では社内のメッセージ体系に置き換える。
```

## もし共通項目とログレベルのルールがなかったら？

障害の調査で「この注文はいつ登録されたか」を聞かれても、テーブルに日時が無ければ答えられません。
ログを何日分もさかのぼって探すことになります。

ログレベルの使い分けが担当者ごとにばらばらだと、監視の設定ができません。
ERROR だけを監視すると業務エラーの誤報が鳴り続け、監視を止めてしまう、ということが起きます。
止めた監視の下で本当の障害が起き、翌朝まで気づかれません。

## 理解度チェック

1. DB の `DEFAULT now()` だけで、更新日時を正しく保てない理由は何ですか。
2. 基底クラスを使った共通項目の設定が漏れやすい場面を 1 つ挙げてください。
3. 入力の誤りによる業務エラーを ERROR で出すと、運用で何が起きますか。
4. JOB0001 で、形式エラーの行が WARN、異常終了が ERROR になっている理由は何ですか。

??? note "答え"
    1. `DEFAULT` は INSERT のときにしか効かず、UPDATE では値が変わらないからです。
    2. `INSERT ... SELECT` のような一括の登録・更新です。Entity を通らないので、基底クラスのメソッドが呼ばれません。新しく作ったテーブルで継承を忘れる場合もあります。
    3. 対応の要らない呼び出し（誤報）が増え、本当の ERROR も軽く扱われるようになります。
    4. 形式エラーの行は取込を続け、後で人が確かめればよいからです。異常終了は取込が 1 件もされておらず、すぐ対応が要るからです。

## コードを読むときの確認観点

- [ ] INSERT・UPDATE のすべてで、共通項目が設定されているか（DB の既定値に任せるなら、UPDATE は別に扱っているか）
- [ ] 新しいテーブルに、共通項目の列があるか
- [ ] ERROR は「すぐ対応が要る」ものだけになっているか
- [ ] 処理が止まる場面で、ERROR が出ているか（WARN・INFO で終わっていないか）
- [ ] 1 行ごと・1 件ごとの大量の INFO を出していないか

## 演習

1. sample-app の `member` テーブルと `orders` テーブルの定義（`local/db/init/01_schema.sql`）を読み、
   共通項目にあたる列と、その値を入れる仕組みを答えてください。
2. 会員の名前を変更する UPDATE を足すとします。共通項目について、テーブル・Mapper XML・テストで足すものを挙げてください。
3. 次のログのレベルを ERROR・WARN・INFO から選び、理由を答えてください。
   (a) バッチが開始した (b) 入力ファイルが見つからず、取込をせずに終了した
   (c) 会員が存在しない行を飛ばした (d) 会員登録 API で、メールアドレスが登録済みのため 409 を返した

解答: [80-12 解答](answers/80-12.md)

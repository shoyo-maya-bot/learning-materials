# 30-11 冪等な登録

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 冪等（べきとう）とは何か、バッチでなぜ大事かを説明できる
    - `insertIfAbsent` と `ON CONFLICT DO NOTHING` の組み合わせを読める
    - `ImportResult` の 3 つの件数が、どこで数えられるかを説明できる
    - 再実行したときの件数と終了コードを、実行前に予想できる

## 何か

**冪等**とは、「同じ操作を何回行っても、1 回行ったときと結果が同じ」という性質です。
JOB0001 の設計書 STEP2 は、次のように決めています。

- チェックを通った行を注文テーブルに登録する
- 注文番号が既にある場合は登録しない（再実行しても重複しない）

sample-app は、これを **SQL 1 文** で実現しています。
「あるか調べてから登録する」のではなく、「登録を試み、既にあれば何もしない」書き方です。

## なぜ必要か

バッチは、途中で止まることがあります。
DB の一時的な障害、サーバーの再起動、入力ファイルの再送などが原因です。
そのとき運用担当者は、たいてい **同じジョブを同じファイルでもう一度動かします**。

登録が冪等でないと、再実行のたびに次のどちらかが起きます。

- 主キー（`order_no`）の重複で例外になり、ジョブが毎回異常終了する
- 主キーが無い表なら、同じ注文が 2 件、3 件と増える

冪等にしておけば、「迷ったらもう一度流す」が安全な手順になります。
運用の手順書が単純になり、夜間の障害対応も楽になります。

## どうやるか

「既にあれば登録しない」の書き方は、大きく 2 つあります。

!!! failure "悪い例"
    例: 先に SELECT で存在を確かめ、無ければ INSERT する。

    ```java
    // 例: sample-app には無いコード
    if (!mapper.existsByOrderNo(order.orderNo())) {
        mapper.insert(order);
    }
    ```

    SQL が 2 回になるうえ、SELECT と INSERT の間に別の処理が同じ注文番号を登録すると、INSERT が一意制約違反で失敗します。
    同じジョブが二重に起動された場合などに起こり得ます。

!!! success "良い例"
    INSERT 1 文に「重複したら何もしない」を含め、**登録できた件数**（0 か 1）で結果を判断する。
    判断を DB の一意制約に任せるので、同時に動いても重複しません。

PostgreSQL では、`INSERT ... ON CONFLICT (列) DO NOTHING` と書きます。
詳しくは [PostgreSQL 公式: INSERT](https://www.postgresql.org/docs/16/sql-insert.html) の ON CONFLICT 句を見てください。

## サンプルアプリでは

### Mapper のインタフェース

```java title="sample-app/src/main/java/com/example/sample/order/OrderMapper.java（6〜15 行目）"
@Mapper
public interface OrderMapper {

    /**
     * 注文番号が未登録なら登録する（再実行しても重複しない＝冪等）.
     *
     * @return 登録した件数（既にあれば 0）
     */
    int insertIfAbsent(Order order);
}
```

戻り値の `int` は、SQL が実際に登録した行数です。MyBatis が JDBC から受け取った件数をそのまま返します。

### SQL 本体

```xml title="sample-app/src/main/resources/mapper/OrderMapper.xml（3〜11 行目）"
<mapper namespace="com.example.sample.order.OrderMapper">

  <!-- 注文番号が既にあれば何もしない（再実行しても重複しない） -->
  <insert id="insertIfAbsent">
    INSERT INTO orders (order_no, member_id, product_code, quantity)
    VALUES (#{orderNo}, #{memberId}, #{productCode}, #{quantity})
    ON CONFLICT (order_no) DO NOTHING
  </insert>
</mapper>
```

- 3 行目: `namespace` が `OrderMapper` の完全修飾名と一致することで、インタフェースと SQL が結び付きます
- 6 行目: `id` がメソッド名 `insertIfAbsent` と一致します
- 8 行目: `#{orderNo}` などは、`Order` レコードの項目名です（`Order.java` 11 行目）
- 9 行目: `order_no` が重複したら、エラーにせず何もしません。このとき登録件数は 0 になります

`ON CONFLICT (order_no)` が効くのは、`order_no` に一意制約（ここでは主キー）があるからです。

```sql title="local/db/init/01_schema.sql（9〜15 行目）"
CREATE TABLE orders (
    order_no     VARCHAR(20) PRIMARY KEY,
    member_id    BIGINT      NOT NULL REFERENCES member (id),
    product_code VARCHAR(20) NOT NULL,
    quantity     INTEGER     NOT NULL CHECK (quantity BETWEEN 1 AND 999),
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 件数の数え方

```java title="sample-app/src/main/java/com/example/sample/order/OrderImportService.java（46〜52 行目）"
            if (mapper.insertIfAbsent(order) == 1) {
                imported++;
            } else {
                duplicated++;
            }
        }
        return new ImportResult(imported, duplicated, List.copyOf(errors));
```

```java title="sample-app/src/main/java/com/example/sample/order/ImportResult.java（12〜17 行目）"
public record ImportResult(int imported, int duplicated, List<String> errors) {

    public boolean hasErrors() {
        return !errors.isEmpty();
    }
}
```

1 行は、必ず次の 3 つのどれか 1 つに数えられます（空行を除く）。

| 件数 | 数える場所 | 意味 |
|---|---|---|
| `imported` | 46〜47 行目 | 登録できた（戻り値 1） |
| `duplicated` | 48〜49 行目 | 既にあったので登録しなかった（戻り値 0） |
| `errors` | 42〜44 行目（30-10） | 形式エラーで飛ばした |

`hasErrors()` が見るのは `errors` だけです。**重複は「エラー」ではありません**。
このため、再実行で全件が重複しても、それだけでは終了コードは 4 になりません（30-13）。

### トランザクションの範囲

`importLines` には `@Transactional`（25 行目）が付いています。
ファイル 1 つ分の登録が、1 つのトランザクションにまとまります。

- 最後まで進めば、まとめて確定（コミット）します
- 途中で `RuntimeException`（DB の例外を含む）が起きると、**それまでの登録もすべて取り消されます**（ロールバック）

形式エラー（30-10）は `parse` の中で受け止めるので、ロールバックは起きません。
一方、DB で初めて見つかる誤りは、ファイル全体の取り消しになります。

!!! warning "ON CONFLICT が守るのは order_no だけ"
    `member_id` は `member` 表を参照しています（`01_schema.sql` 11 行目の `REFERENCES member (id)`）。
    存在しない会員 ID の行は、`parse` では見つからず、INSERT で外部キー違反になります。
    `ON CONFLICT (order_no)` はこの違反を受け止めないので、例外になり、ファイル全体が取り消されて終了コード 8 になります。
    設計書 STEP1 にも会員の存在確認はありません。実案件なら、設計者に扱いを確認したい点です。

### ローカルで確かめる

`local/README.md` の 8 にあるとおり、同じファイルで 2 回動かすと件数が変わります。

```text
1 回目: APPI0002 JOB0001 終了 imported=3 duplicated=0 errors=1
2 回目: APPI0002 JOB0001 終了 imported=0 duplicated=3 errors=1
```

DB の中身は次のコマンドで確かめられます（`local` ディレクトリで実行）。

```bash
docker compose exec db psql -U app -d sampledb -c "SELECT order_no, quantity, imported_at FROM orders ORDER BY order_no;"
```

2 回目の後も 3 件のままで、`imported_at` も 1 回目の時刻のままであることを確認してください。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| `ON CONFLICT (order_no) DO NOTHING` | DB ごとの書き方（`MERGE`、`INSERT IGNORE` など）、または存在確認の部品 |
| `order_no` の主キー | 業務キー（注文番号・伝票番号など）に張られた一意制約 |
| `insertIfAbsent` の戻り値 0 / 1 | 登録件数で「新規」と「既存」を分けている箇所 |
| `ImportResult` の 3 つの件数 | 処理件数のログ・実行結果表（運用担当者が見る件数） |
| `@Transactional`（ファイル全体で 1 つ） | コミットの単位（全件一括か、N 件ごとか）。再実行の手順と合わせて確認する |

## もし ON CONFLICT DO NOTHING がなかったら？

1 回目の実行は、何も変わらず成功します。違いが出るのは **2 回目** です。
最初の行 `A0001` の INSERT で主キーの重複が起き、例外になります。
`@Transactional` でロールバックされ、`OrderImportJob` が受け止めて終了コード 8 で終わります。

つまり、「1 回目に途中で止まったファイルを、もう一度流す」という当たり前の復旧手順が使えなくなります。
運用担当者は、どの行まで登録済みかを DB で調べ、未登録の行だけのファイルを作り直す必要が出てきます。

## 理解度チェック

1. 冪等とはどういう性質ですか。JOB0001 の言葉で説明してください。

    ??? note "答え"
        同じファイルで JOB0001 を何回動かしても、注文テーブルの中身が 1 回動かしたときと同じになる性質です。

2. `insertIfAbsent` の戻り値が 0 になるのはどんなときですか。

    ??? note "答え"
        同じ `order_no` の行が、すでに注文テーブルにあるときです。`ON CONFLICT (order_no) DO NOTHING` により、登録されません。

3. 1 つのファイルの中に、同じ注文番号の行が 2 回出てきたら、どう数えられますか。

    ??? note "答え"
        1 回目の行が `imported`、2 回目の行が `duplicated` に数えられます。
        同じトランザクションの中でも、先に登録した行と衝突するからです。2 回目の行の内容（数量など）は使われません。

4. 再実行で全行が重複になったとき、`hasErrors()` は何を返しますか。

    ??? note "答え"
        `errors` が空なら `false` です。重複は `duplicated` に数えるだけで、エラーとは扱いません。

## コードを読むときの確認観点

- [ ] 「既にあれば登録しない」を、どの列の一意性で判断しているか確認したか
- [ ] その列に、DB の一意制約（主キー・ユニーク制約）が本当にあるか確認したか
- [ ] 戻り値（登録件数）を、呼び出し側がどう使っているか確認したか
- [ ] トランザクションの範囲と、途中で例外が起きたときに何が取り消されるかを確認したか
- [ ] 一意制約以外の制約（外部キー・桁数・CHECK）で失敗する入力が無いか確認したか
- [ ] 再実行の手順（同じファイルで流してよいか）を、件数で説明できるか確認したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **動きを予想する**: 空の注文テーブルに対して、`local/data/orders.csv` で JOB0001 を 2 回続けて動かします。それぞれの `imported` / `duplicated` / `errors` と **終了コード** を答えてください。
2. **どのテストが落ちるか**: `OrderMapper.xml` から `ON CONFLICT (order_no) DO NOTHING` の行を消しました。`./gradlew test` で失敗するテストはどれですか。また、ローカルで 2 回目を動かすと何が起きますか。
3. **動きを予想する**: `orders.csv` の末尾に `A0005,3,P-001,1` を足しました（会員 3 は存在しません）。1 回目の実行結果（登録される件数と終了コード）を答えてください。
4. **場所を探す**: 2 回目の実行で `duplicated=3` になったとき、「どの注文番号が重複したか」はログに出ますか。出ないなら、出すにはどのファイルのどこを変えればよいですか。
5. **考える**: `ON CONFLICT (order_no) DO NOTHING` を `DO UPDATE SET quantity = EXCLUDED.quantity` に変えると、再実行や「数量を直したファイルの再送」で何が変わりますか。`insertIfAbsent` の名前と戻り値の意味の面からも考えてください。

解答: [30-11 解答](answers/30-11.md)

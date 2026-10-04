# 20-13 トランザクション

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - トランザクションが何を守る仕組みかを説明できる
    - `@Transactional` をどこに付けるか、どの例外でロールバックされるかを説明できる
    - バッチのコミット単位（ファイル全体・N 件ごと）の違いを説明できる
    - サンプルアプリのトランザクション境界を読める

## 何か

トランザクションとは、複数の DB 操作を「全部成功」か「全部取り消し」のどちらかにする仕組みです。

- **コミット**: 操作を確定させること
- **ロールバック**: 操作を取り消し、始める前の状態に戻すこと
- **トランザクション境界**: どこで始まり、どこでコミットするか

Spring では、メソッドに `@Transactional` を付けると、次の動きになります。

1. メソッドの開始時にトランザクションを始める
2. 正常に終われば、コミットする
3. 例外（既定では非検査例外）で終われば、ロールバックする

この仕組みは **プロキシ** で動きます。
Spring が Bean の前に代理のオブジェクトを置き、メソッド呼び出しの前後で開始・コミットを行います。

## なぜ必要か

例えば「注文を登録し、在庫を減らす」処理で、途中でエラーが起きたとします。
トランザクションが無いと、注文だけ登録されて在庫が減らない、という食い違いが残ります。

トランザクションは、こうした **中途半端な状態** を残さないために使います。
また、どこまでを 1 つの単位にするか（コミット単位）は、障害時の再実行のしかたに直結します。
そのため設計書で決め、レビューでも確かめます（品質ゲート N4「トランザクション境界」）。

## どうやるか

### 1. Service の public メソッドに付ける

チームの規約では、トランザクションは Service の責務です。
Controller や Mapper には付けません。

例:

```java
@Service
public class ProductService {

    @Transactional(readOnly = true)  // 読むだけ
    public Product get(String code) { ... }

    @Transactional                   // 書き込みあり
    public void changePrice(String code, int price) { ... }
}
```

`readOnly = true` は「読むだけ」の宣言です。意図が読み手に伝わり、DB やドライバーの最適化にも使われます。

### 2. ロールバックの規則を知る

| 例外の種類 | 既定の動き |
|---|---|
| 非検査例外（`RuntimeException` とその子） | ロールバック |
| `Error` | ロールバック |
| 検査例外（`IOException` など） | **コミット** |

検査例外でもロールバックしたいときは、`rollbackFor` を指定します。

例:

```java
@Transactional(rollbackFor = Exception.class)
public void importFile(Path file) throws IOException { ... }
```

### 3. 例外を握りつぶさない

`@Transactional` のメソッドの中で例外を catch して終えると、Spring は「正常終了」と見てコミットします。

!!! failure "悪い例"
    ```java
    // 例: 例外を捕まえてログだけ出すと、途中までの更新がコミットされる
    @Transactional
    public void transfer(...) {
        try {
            mapper.decrease(...);
            mapper.increase(...);
        } catch (RuntimeException e) {
            log.warn("失敗", e);
        }
    }
    ```

!!! success "良い例"
    ```java
    // 例: 例外はそのまま外へ出し、ロールバックさせる。ログは受け取った側で 1 回出す
    @Transactional
    public void transfer(...) {
        mapper.decrease(...);
        mapper.increase(...);
    }
    ```

### 4. プロキシの落とし穴

プロキシを通らない呼び出しには、`@Transactional` が効きません。

- 同じクラスの中から呼ぶ（`this.other()`）と、プロキシを通らない
- `private` メソッドに付けても効かない
- Spring を使わず `new` したオブジェクトには効かない（単体テストがこれに当たる）

### 5. バッチのコミット単位を決める

ファイル取込のようなバッチでは、どの単位でコミットするかを設計で決めます。

| コミット単位 | よい点 | 注意点 |
|---|---|---|
| ファイル全体で 1 回 | 失敗したら何も残らず、分かりやすい | 大量件数だとロックや DB の負荷が長く続く。1 件の DB エラーで全件取り消し |
| N 件ごと（例: 1,000 件） | 負荷が分散し、途中までの結果が残る | 途中で失敗すると一部だけ登録済みになる。再実行が冪等である必要がある |
| 1 件ごと | 失敗した行だけを飛ばせる | コミット回数が多く遅い |

N 件ごとにする場合、Spring の `TransactionTemplate` で区切る方法があります。

例:

```java
// 例: 1,000 件ごとに別のトランザクションでコミットする（再実行は冪等な登録が前提）
for (List<Order> chunk : chunks) {
    txTemplate.executeWithoutResult(status -> chunk.forEach(mapper::insertIfAbsent));
}
```

!!! failure "悪い例"
    ```java
    // 例: 1 つのトランザクションの中で、DB エラーの行だけ catch して続けようとする
    @Transactional
    public void importAll(List<Order> orders) {
        for (Order o : orders) {
            try {
                mapper.insertIfAbsent(o);
            } catch (DataIntegrityViolationException e) {
                // PostgreSQL では、ここで以降の SQL がすべて失敗する
            }
        }
    }
    ```
    PostgreSQL は、トランザクション内で 1 回エラーが起きると、そのトランザクションを中断状態にします。
    以降の SQL は「current transaction is aborted」で失敗し続けます。

!!! success "良い例"
    DB に送る前に、アプリ側のチェックで不正な行を除きます。
    DB エラーで行ごとに飛ばしたい要件なら、コミット単位を 1 件ごとにする設計にします。

## サンプルアプリでは

### 会員 API

`sample-app/src/main/java/com/example/sample/member/MemberService.java` の 19〜33 行目です。

```java
@Transactional(readOnly = true)
public Member get(long id) {
    return mapper.findById(id).orElseThrow(() -> new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id));
}

@Transactional
public Member register(String name, String email) {
    String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
    if (mapper.existsByEmail(normalized)) {
        throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
    }
    MemberRecord rec = new MemberRecord(name.trim(), normalized);
    mapper.insert(rec);
    return rec.toMember();
}
```

- 照会は `readOnly = true`、登録は通常の `@Transactional` です
- `BusinessException` は `RuntimeException` の子なので、投げるとロールバックされます
- 「`existsByEmail` で確かめてから `insert`」の間に、別のリクエストが同じメールアドレスを登録する可能性はあります
- その場合も DB の `UNIQUE` 制約が二重登録を止めます。ただし DB の例外になり、`ApiExceptionHandler` に対応が無いため、`APPE0003` の 409 応答にはなりません

### 注文ファイル取込（JOB0001）

`sample-app/src/main/java/com/example/sample/order/OrderImportService.java` の 25〜26 行目です。

```java
@Transactional
public ImportResult importLines(List<String> lines) {
```

- コミット単位は **ファイル全体で 1 回** です
- 形式エラーの行は `parse` で DB に送る前に除くので、トランザクションに影響しません
- 注文番号の重複は `ON CONFLICT DO NOTHING` でエラーにならないので、これも影響しません
- 見出し行が不正なときの `IllegalArgumentException` は非検査例外なので、ロールバックされます

呼び出し側は `sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java` の 50〜59 行目です。

```java
try {
    ImportResult r = service.importLines(fetcher.readLines(input.get(0)));
    r.errors().forEach(e -> log.warn("{} {}", MessageIds.IMPORT_LINE_SKIPPED, e));
    log.info("{} JOB0001 終了 imported={} duplicated={} errors={}",
            MessageIds.IMPORT_FINISHED, r.imported(), r.duplicated(), r.errors().size());
    exitCode = r.hasErrors() ? WARN : OK;
} catch (Exception e) {
    log.error("JOB0001 異常終了", e);
    exitCode = ERROR;
}
```

Job は Spring が作った `service`（プロキシ）を呼ぶので、`@Transactional` が効きます。
`importLines` の中で例外が起きると、ロールバックされてから Job の catch に届き、終了コード 8 になります。

!!! note "存在しない会員の注文があったら"
    `parse` は会員の実在を確かめません。存在しない会員 ID の行があると、外部キー違反の DB 例外になります。
    コミット単位がファイル全体なので、**それまでに登録した行もすべてロールバック** され、終了コード 8 になります。
    データを直して再実行すれば、冪等な登録なので重複は起きません。
    これが要件どおりか（全件取り消しでよいか）は、設計書のコミット単位と突き合わせて判断します。

### 単体テストでは効かない

`MemberServiceTest` や `OrderImportServiceTest` は、Spring を使わず `new` で Service を作ります。
そのため `@Transactional` は動いていません。
単体テストで確かめているのは業務ロジックで、トランザクションの動きは DB を使う結合テストで確かめます。

## もしトランザクションがなかったら？

`OrderImportService.importLines` から `@Transactional` を外すと、SQL は 1 文ずつ自動でコミットされます。
途中で DB エラーが起きると、そこまでの行だけが登録された状態で終わります。
冪等な登録なので再実行で回復はできますが、「全件取り消し」という設計上の約束は守れなくなります。

複数のテーブルを更新する処理では、もっと深刻です。
片方のテーブルだけが更新され、データの食い違いが残り、手作業での修正が必要になります。

## 理解度チェック

1. `@Transactional` のメソッドから `IOException`（検査例外）が投げられると、既定ではどうなりますか。

    ??? note "答え"
        コミットされます。検査例外でロールバックしたいときは `rollbackFor` を指定します。

2. `MemberService.register` で `BusinessException` が投げられたとき、トランザクションはどうなりますか。

    ??? note "答え"
        ロールバックされます。`BusinessException` は `RuntimeException` を継承した非検査例外だからです。

3. `OrderImportService` の中で `this.importLines(...)` のように自分のメソッドを呼んだ場合、`@Transactional` は効きますか。

    ??? note "答え"
        効きません。同じクラスの中からの呼び出しはプロキシを通らないからです。

4. JOB0001 で 3 行目までを登録した後、4 行目で外部キー違反が起きました。DB にはどの行が残りますか。

    ??? note "答え"
        何も残りません。コミット単位がファイル全体なので、1〜3 行目もロールバックされます。
        Job は終了コード 8 で終わります。

5. N 件ごとにコミットする設計にするとき、再実行のために必要な性質は何ですか。

    ??? note "答え"
        冪等性です。途中まで登録済みの状態から再実行しても、重複や不整合が起きない必要があります。
        サンプルアプリでは `ON CONFLICT DO NOTHING` がこれに当たります。

## コードを読むときの確認観点

- [ ] `@Transactional` が Service の public メソッドに付いている（Controller・Mapper・private メソッドではない）
- [ ] 読むだけのメソッドに `readOnly = true` が付いている
- [ ] トランザクション内で例外を握りつぶしていない
- [ ] 検査例外でロールバックが必要な場合に `rollbackFor` がある
- [ ] 同じクラス内の呼び出しで、トランザクションが効く前提になっていない
- [ ] バッチのコミット単位が設計書どおりで、途中失敗後の再実行が安全である

参考: [Spring Framework: 宣言的トランザクション](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative.html)、[PostgreSQL 文書: トランザクション](https://www.postgresql.org/docs/16/tutorial-transactions.html)

# 60-04 AI の出力を疑う（テストと公式ドキュメントで確かめる）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - AI の回答を「確かめる前の主張」の集まりとして読み、主張ごとに分けられる
    - 主張を、テスト・実行結果・公式ドキュメントのどれで確かめるかを選べる
    - 誤った主張を、小さなテストや公式ドキュメントの記述で反証できる
    - 確かめた結果と根拠を、レビューや質問で他の人に示せる

## 何か

AI（GitHub Copilot Chat など）の回答には、正しい内容と誤った内容が混ざります。
しかも、誤った内容も正しい内容と同じくらい自信のある文で書かれます。

この章でいう「AI の出力を疑う」とは、回答を次の手順で扱うことです。

1. 回答を、1 つずつ確かめられる **主張** に分ける
2. 主張ごとに、確かめる方法（テスト・実行・公式ドキュメント）を決める
3. 実際に確かめ、結果と根拠を残す
4. 確かめた主張だけを使う

疑うことは、AI を使わないことではありません。
AI の回答を「下書き」として使い、自分で確かめてから採用する、という使い方です（[10-06](../10-setup/10-06-copilot.md)）。

## なぜ必要か

AI は、もっともらしい誤りを書きます。たとえば次のようなものです。

- 古い版の情報（今の版では動きが変わった API や設定）
- 存在しないメソッドや設定項目
- 似た別の仕組みとの取り違え（ある DB の動きを、別の DB の動きとして説明する）
- 実行していないのに「テストが通りました」と報告する

誤りに気づかずにコードへ入れると、レビューやテストの後ろの工程で見つかります。
後ろで見つかるほど、原因を探す時間がかかります。
また「AI がそう言った」は、レビューで根拠になりません。根拠になるのは、テストの結果と公式ドキュメントの記述です。

## どうやるか

### 1. 回答を主張に分ける

AI の回答を、「〜は〜する」の形の短い主張に分けます。1 つの主張は 1 つの方法で確かめられる大きさにします。

### 2. 確かめる方法を選ぶ

| 主張の種類 | 確かめる方法 | 例 |
| --- | --- | --- |
| 言語・ライブラリの動き | 小さな単体テストを書いて実行する | 「このメソッドは null を返す」 |
| DB や外部サービスの動き | ローカル環境（[10-04](../10-setup/10-04-docker-local.md)）で実行する | 「この SQL は重複でエラーになる」 |
| 仕様・設定・推奨 | 公式ドキュメントの該当箇所を読む（版を確認する） | 「この設定は既定で有効」 |
| 「テストが通った」「実装した」 | 自分でコマンドを実行し、結果を見る | `.\gradlew.bat test` の結果 |

公式ドキュメントは [外部参照](../appendix/references.md) にまとめています。
ブログや Q&A サイトは、古い版の情報が混ざるので、根拠にはしません。

### 3. 確かめた結果を残す

確かめた結果は、主張・方法・結果・根拠（テスト名や URL）の 4 つを書きます。
レビューで「なぜこう書いたか」を聞かれたときに、そのまま答えになります。

!!! failure "悪い例"
    AI の回答をそのまま貼り付け、「Copilot によると問題ありません」とレビューに書く。
    レビューする人は、どこが確かめ済みかが分からず、全部を最初から調べ直すことになります。

!!! success "良い例"
    「`List.of` の戻り値に `add` できる」という AI の主張を、単体テストで確かめた。
    `UnsupportedOperationException` が出たので誤り。根拠: テスト `ListOfTest`、Java SE 17 API の `List` の「Unmodifiable Lists」。

## サンプルアプリでは

sample-app の注文ファイル取込（JOB0001）は、注文を登録するときに `ON CONFLICT (order_no) DO NOTHING` を使っています（[30-11](../30-reading/30-11-idempotent-insert.md)）。

<!-- src: sample-app/src/main/resources/mapper/OrderMapper.xml#L5-L10 @exercise-base -->
```xml title="sample-app/src/main/resources/mapper/OrderMapper.xml" linenums="5"
  <!-- 注文番号が既にあれば何もしない（再実行しても重複しない） -->
  <insert id="insertIfAbsent">
    INSERT INTO orders (order_no, member_id, product_code, quantity)
    VALUES (#{orderNo}, #{memberId}, #{productCode}, #{quantity})
    ON CONFLICT (order_no) DO NOTHING
  </insert>
```

この SQL の動きについて AI に聞くと、誤った説明が返ってくることがあります。
下の演習では、その誤りを自分で確かめて反証します。

### 演習: 誤りが混ざった AI の回答を確かめる

次は、ある開発者が AI に質問し、返ってきた回答です（**この教材のために作った架空の例** です）。

> **質問**: 注文の取込で、同じ注文番号を 2 回登録しようとしたらどうなりますか。あと、`List.of` で作った注文番号の一覧に、あとから番号を足せますか。
>
> **AI の回答（架空）**:
>
> 1. PostgreSQL の `INSERT ... ON CONFLICT DO NOTHING` は、重複したときに一意制約違反の例外を投げます。なので呼び出し側で例外を捕まえる必要があります。
> 2. `List.of(...)` で作ったリストは普通の `ArrayList` なので、`add` で要素を足せます。
> 3. `Optional` の引数なしの `orElseThrow()` は、値が無いときに `NoSuchElementException` を投げます。
> 4. `@Transactional` は private メソッドに付けても効きます。同じクラスの中から呼んでもトランザクションになります。

主張 1〜4 のそれぞれについて、次の表を埋めてください。

| 主張 | 確かめる方法 | 結果（正しい / 誤り） | 根拠 |
| --- | --- | --- | --- |
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |

手順のヒント:

- 主張 1 は、ローカルの DB で確かめます（`local` で、`docker compose up -d --wait` の後）。一時テーブルなので、DB の中身は変わりません

    ```powershell
    docker compose exec db psql -U app -d sampledb -c "CREATE TEMP TABLE t (id int PRIMARY KEY); INSERT INTO t VALUES (1); INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING;"
    ```

- 主張 2 と 3 は、単体テストで確かめます。手元で一時的に作り、確かめたら消します（コミットしない）

    例: `sample-app/src/test/java/com/example/sample/ListOfTest.java` として置く

    ```java
    package com.example.sample;

    import static org.junit.jupiter.api.Assertions.assertThrows;

    import java.util.List;
    import java.util.NoSuchElementException;
    import java.util.Optional;
    import org.junit.jupiter.api.Test;

    class ListOfTest {

        @Test
        void listOfCannotAdd() {
            List<String> orderNos = List.of("ORD-0001");
            assertThrows(UnsupportedOperationException.class, () -> orderNos.add("ORD-0002"));
        }

        @Test
        void orElseThrowWithoutArgument() {
            assertThrows(NoSuchElementException.class, () -> Optional.empty().orElseThrow());
        }
    }
    ```

    実行（`sample-app` で）: `.\gradlew.bat test --tests "*ListOfTest"`（Git Bash は `./gradlew test --tests "*ListOfTest"`）

- 主張 4 は、Spring Framework の公式リファレンスの「Using `@Transactional`」を読みます（[宣言的トランザクション](https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html)）

??? note "答え"
    | 主張 | 確かめる方法 | 結果 | 根拠 |
    | --- | --- | --- | --- |
    | 1 | ローカルの DB で実行 | **誤り** | 2 つ目の INSERT はエラーにならず、`INSERT 0 0`（0 行登録）と出る。PostgreSQL 公式の [INSERT](https://www.postgresql.org/docs/current/sql-insert.html) の ON CONFLICT 句の説明 |
    | 2 | 単体テスト | **誤り** | `UnsupportedOperationException` が出る（`listOfCannotAdd` が成功する）。Java SE 17 API の `List` の「Unmodifiable Lists」 |
    | 3 | 単体テスト | 正しい | `orElseThrowWithoutArgument` が成功する。Java SE 17 API の `Optional.orElseThrow()` |
    | 4 | 公式ドキュメント | **誤り** | 既定のプロキシ方式では、プロキシを通る外からの呼び出しだけがトランザクションになる。private メソッドや、同じクラスの中からの呼び出し（自己呼び出し）には効かない |

    主張 3 のように、正しい主張も混ざっています。「全部疑って全部捨てる」のではなく、主張ごとに確かめて、確かめたものだけを使います。

    主張 1 を信じると、起きない例外を捕まえるコードを書き、「重複したら 0 行」という本当の動きを見落とします。
    sample-app は、この 0 行を「重複」として数えています（[30-11](../30-reading/30-11-idempotent-insert.md)）。

## もし確かめる習慣がなかったら？

主張 4 を信じて、private メソッドに `@Transactional` を付けたとします。
コンパイルもテストも通り、普段は正しく動きます。
ところが途中で失敗したときだけ、一部の更新が残ってデータが食い違います。
この種の誤りは、本番で障害が起きて初めて気づくことが多く、原因の特定にも時間がかかります。

確かめる習慣があれば、公式ドキュメントを 1 つ読むだけで、書く前に防げました。

## 理解度チェック

1. AI の回答を確かめるとき、最初にすることは何ですか。

    ??? note "答え"
        回答を、1 つずつ確かめられる短い主張に分けることです。
        まとめて「正しそう」と判断すると、正しい主張と誤った主張の区別が付きません。

2. 「この SQL は重複でエラーになる」という主張は、何で確かめるのがよいですか。

    ??? note "答え"
        ローカルの DB（コンテナの PostgreSQL）で実際に実行し、公式ドキュメントの記述とも突き合わせます。
        DB の動きは製品や版で違うので、チームが使う製品と同じ版で確かめます。

3. AI が「テストが通りました」と言ったとき、どうしますか。

    ??? note "答え"
        自分でテストのコマンド（例: `.\gradlew.bat test`）を実行し、結果を見ます。
        AI の報告は、実行した証拠になりません。

4. 確かめた結果をレビューに書くとき、何を書きますか。

    ??? note "答え"
        主張・確かめた方法・結果・根拠（テスト名や公式ドキュメントの URL）です。
        「AI がそう言った」は根拠になりません。

## コードを読むときの確認観点

- [ ] AI が書いたコードや説明を、主張に分けて確かめたか
- [ ] 確かめた方法（テスト・実行・公式ドキュメント）と結果を残したか
- [ ] 公式ドキュメントの版が、チームの使っている版と合っているか
- [ ] 「テストが通った」「実装した」を、自分でコマンドを実行して確かめたか
- [ ] 確かめるために作った一時的なテストやテーブルを、コミットせずに片付けたか

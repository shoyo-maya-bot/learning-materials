# 50-05 ページングと検索

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 一覧 API で件数の上限（ページング）が必要な理由を説明できる
    - ページ番号方式とキー方式（続きの位置を渡す方式）の違いを説明できる
    - 検索条件と並び順を、SQL インジェクションを起こさずに MyBatis で書ける

## 何か

**ページング** は、一覧の結果を一定の件数ずつ区切って返す仕組みです。
「1 ページ 20 件の 3 ページ目」のように、利用者が欲しい範囲だけを受け取ります。

**検索** は、一覧を条件で絞り込むことです。
API では、条件をクエリパラメータで受け取ります。

例:

```text
GET /api/v1/members?name=山田&page=0&size=20&sort=id
```

| パラメータ | 意味 |
| --- | --- |
| `name` | 絞り込み条件（氏名の前方一致など） |
| `page` | 何ページ目か（0 から数える、などと規約で決める） |
| `size` | 1 ページの件数（上限を決める） |
| `sort` | 並び順（使える項目を決める） |

## なぜ必要か

件数の上限が無い一覧 API は、データが増えると壊れます。
会員が 100 万人になったとき、全件を 1 回で返そうとすると次のことが起きます。

- DB からの読み込みと JSON への変換で、メモリが足りなくなる
- 応答に時間がかかり、タイムアウトになる（[40-01](../40-async/40-01-async-basics.md)）
- 画面側も全件を表示できず、結局は使われない

開発中はデータが少ないので、この問題は表に出ません。
本番のデータ量を見積もって、最初から上限を設けておく必要があります。

並び順を決めることも大切です。
SQL は `ORDER BY` を書かないと、行の順番を保証しません。
並び順が決まっていないと、ページをまたいで同じ行が出たり、出なかったりします。

## どうやるか

### ページ番号方式

`LIMIT`（件数）と `OFFSET`（読み飛ばす件数）を使います。
sample-app には一覧 API が無いので、次は「例:」です。

例（Mapper XML）:

```xml
<select id="search" resultType="com.example.sample.member.Member">
  SELECT id, name, email FROM member
  <where>
    <if test="name != null and name != ''">
      name LIKE #{namePrefix}
    </if>
  </where>
  ORDER BY id
  LIMIT #{size} OFFSET #{offset}
</select>
```

- `namePrefix` は、Java 側で `name + "%"` を作って渡します（`%` や `_` を含む入力の扱いも決めます）
- `ORDER BY id` で、並び順を一意に決めています
- `offset` は `page * size` で求めます

例（応答）:

```json
{
  "items": [{"id": 21, "name": "山田 一郎", "email": "..."}],
  "page": 1,
  "size": 20,
  "totalCount": 135
}
```

`size` には上限を設け、超えたら入力誤り（400）にします。

例:

```java
@GetMapping
public MemberPage search(@RequestParam(name = "name", required = false) String name,
                         @RequestParam(name = "page", defaultValue = "0") @Min(0) int page,
                         @RequestParam(name = "size", defaultValue = "20") @Min(1) @Max(100) int size) {
    return service.search(name, page, size);
}
```

パラメータに付けた入力チェックの誤りは、`@RequestBody` の誤り（`MethodArgumentNotValidException`）とは別の例外になります。
エラー応答の形をそろえるなら、その例外のハンドラも用意します（[50-03](50-03-status-error.md)）。

### キー方式（大量データ向け）

`OFFSET` は、読み飛ばす行も DB が数えるため、後ろのページほど遅くなります。
データが多い一覧では、「最後に受け取った ID より後ろ」を条件にするキー方式を使います。

例:

```sql
SELECT id, name, email FROM member
WHERE id > #{afterId}
ORDER BY id
LIMIT #{size}
```

| 方式 | 長所 | 短所 |
| --- | --- | --- |
| ページ番号方式 | 「3 ページ目」に直接移動できる | 後ろのページほど遅い。途中で行が増減するとずれる |
| キー方式 | 何ページ目でも速い。ずれにくい | 任意のページに飛べない |

### 総件数を数えるか

`totalCount` を返すには、別に `COUNT(*)` の SQL が要ります。
件数が多いと、この SQL が一番重くなることもあります。
画面に総件数が本当に必要かを、設計の段階で確かめます。

### 並び順は「許可した項目」だけ

並び順を利用者に選ばせるとき、受け取った文字列を SQL に埋め込んではいけません。

!!! failure "悪い例"
    ```xml
    <!-- ${} は文字列をそのまま SQL に埋め込む。sort=id;DROP TABLE member のような入力が通る -->
    ORDER BY ${sort}
    ```

!!! success "良い例"
    ```java
    // 使える並び順を列挙し、それ以外は入力誤りにする
    enum MemberSort { ID, NAME }
    ```
    ```xml
    <choose>
      <when test="sort.name() == 'NAME'">ORDER BY name, id</when>
      <otherwise>ORDER BY id</otherwise>
    </choose>
    ```

MyBatis の `#{}` は、値を安全に渡す仕組み（プレースホルダ）です。
`${}` は文字列をそのまま埋め込むので、SQL インジェクションの原因になります。
チームの品質ゲートでも、Mapper XML に `${}` が無いことを確かめています（`D9 SQL の安全性`）。

## サンプルアプリでは

sample-app には、一覧 API・検索 API・ページングはありません。
会員 API は ID を指定した 1 件の照会だけです。

近い実物として、`sample-app/src/main/resources/mapper/MemberMapper.xml` の値の渡し方を見ます。

<!-- src: sample-app/src/main/resources/mapper/MemberMapper.xml @exercise-base -->
```xml
<select id="findById" resultType="com.example.sample.member.Member">
  SELECT id, name, email FROM member WHERE id = #{id}
</select>

<select id="existsByEmail" resultType="boolean">
  SELECT EXISTS (SELECT 1 FROM member WHERE email = #{email})
</select>
```

- 条件の値は、どちらも `#{}` で渡しています。検索条件を足すときも同じにします
- `existsByEmail` は、行を取らずに「あるかどうか」だけを返します。件数が要らないときに `COUNT(*)` を使わない書き方です

一覧を足すときは、DB 側の準備も確かめます。
`dev-environment` の `local/db/init/01_schema.sql` では、`member` の `id` が主キー、`email` が一意制約です。

<!-- src: local/db/init/01_schema.sql @exercise-base -->
```sql
CREATE TABLE member (
    id         BIGSERIAL PRIMARY KEY,
    name       VARCHAR(50)  NOT NULL,
    email      VARCHAR(254) NOT NULL UNIQUE,
```

主キーと一意制約には索引が作られますが、`name` にはありません。
`name` で検索・並び替えをするなら、索引の要否を DB の設計で決めます。

SQL の基本と MyBatis の書き方は、[20-11 SQL の基本](../20-basics/20-11-sql.md) と [20-12 MyBatis](../20-basics/20-12-mybatis.md) で復習してください。

## もしページングがなかったら？

リリース直後は会員が少なく、一覧 API は問題なく動きます。
1 年後に会員が数十万人になると、一覧 API を呼ぶたびにメモリを大量に使うようになります。
同時に何人かが呼ぶと、API のコンテナがメモリ不足で落ちます。
落ちたコンテナが入れ替わる間、他の API も使えなくなります。

並び順が決まっていないと、利用者が「次のページ」を押したときに、同じ会員が 2 回出たり、出なかったりします。
データの件数や DB の状態によって起きたり起きなかったりするので、再現が難しい不具合になります。

## 理解度チェック

1. 一覧 API に `size` の上限を設ける理由を説明してください。

    ??? note "答え"
        データが増えたときに、全件を 1 回で返そうとしてメモリ不足やタイムアウトになるのを防ぐためです。
        開発中はデータが少ないので、問題が表に出ません。

2. ページングの SQL に `ORDER BY` が必要なのはなぜですか。

    ??? note "答え"
        SQL は `ORDER BY` が無いと行の順番を保証しないからです。
        順番が変わると、ページをまたいで同じ行が出たり、出なかったりします。

3. 並び順を `ORDER BY ${sort}` で受け取ってはいけない理由を説明してください。

    ??? note "答え"
        `${}` は文字列をそのまま SQL に埋め込むので、SQL インジェクションの原因になるからです。
        使える並び順を列挙して選ばせ、Mapper XML には `${}` を使いません。

4. ページ番号方式とキー方式のどちらが、100 万件の一覧の後ろのページを速く返せますか。

    ??? note "答え"
        キー方式です。
        ページ番号方式の `OFFSET` は読み飛ばす行も DB が数えるため、後ろのページほど遅くなります。

## コードを読むときの確認観点

- [ ] 一覧 API の `size` に上限があり、超えたら入力誤りになるか
- [ ] SQL に `ORDER BY` があり、並び順が一意に決まるか（同じ値の行がある列だけで並べていないか）
- [ ] Mapper XML で `${}` を使っていないか
- [ ] 並び順や検索条件の項目が、許可した一覧に限られているか
- [ ] 総件数（`COUNT(*)`）が本当に必要か、重くならないか
- [ ] 検索条件の列に、データ量に見合った索引があるか

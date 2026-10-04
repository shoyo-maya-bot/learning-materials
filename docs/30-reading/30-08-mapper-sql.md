# 30-08 Mapper と SQL

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - Mapper インタフェースのメソッドと、XML の SQL を対応づけて読める
    - `#{...}`・`resultType`・`useGeneratedKeys` の意味を説明できる
    - `MemberRecord` が `record` ではなく可変のクラスである理由を説明できる
    - SQL とテーブル定義（制約）を合わせて読み、起こりうる DB のエラーを挙げられる

## 何か

Mapper は、MyBatis（SQL を XML に書いて Java から呼ぶライブラリ）でデータベースを読み書きする部品です。
2 つのファイルが対になっています。

| ファイル | 書くこと |
| --- | --- |
| Mapper インタフェース（`MemberMapper.java`） | Java から呼ぶメソッドの名前・引数・戻り値 |
| Mapper XML（`MemberMapper.xml`） | メソッドごとの SQL の本体 |

インタフェースには実装クラスがありません。
MyBatis が起動時に XML を読み、実装を自動で作ります。

MyBatis の基本は [20-12 MyBatis](../20-basics/20-12-mybatis.md)、SQL は [20-11 SQL の基本](../20-basics/20-11-sql.md) で学びました。

## なぜ必要か

業務の不具合の多くは、データの読み書きで起きます。
「どの SQL が、どのテーブルの、どの列を、どの条件で読み書きするか」を読めないと、原因を追えません。

また、SQL はテーブルの制約（主キー、一意、外部キー、CHECK）と一緒に読む必要があります。
制約に違反すると、Java のコードからは見えないところで例外が起きるからです。

## どうやるか

### インタフェースと XML を 4 点で対応づける

| Java 側 | XML 側 | 一致させるもの |
| --- | --- | --- |
| インタフェースの完全な名前 | `<mapper namespace="...">` | パッケージ名 + インタフェース名 |
| メソッド名 | `<select id="...">` などの `id` | 名前 |
| 引数（値、またはオブジェクトの項目） | `#{...}` | 引数名、または項目名 |
| 戻り値 | `resultType` | 型（1 行を何に詰めるか） |

### #{...} と ${...} を見分ける

`#{...}` は、値を SQL の「パラメータ」として安全に渡します。
`${...}` は、値を SQL の文字列にそのまま埋め込みます。

!!! failure "悪い例"
    ```xml
    <!-- 例: 値を文字列としてそのまま埋め込む -->
    <select id="existsByEmail" resultType="boolean">
      SELECT EXISTS (SELECT 1 FROM member WHERE email = '${email}')
    </select>
    ```
    入力に `'` を含めると SQL の意味を書き換えられます（SQL インジェクション）。

!!! success "良い例"
    ```xml title="sample-app/src/main/resources/mapper/MemberMapper.xml" linenums="9"
      <select id="existsByEmail" resultType="boolean">
        SELECT EXISTS (SELECT 1 FROM member WHERE email = #{email})
      </select>
    ```
    値はパラメータとして渡され、SQL の一部として解釈されません。

### SQL とテーブル定義を並べて読む

SQL を読んだら、対象のテーブルの定義を開きます。
サンプルアプリでは `dev-environment` の `local/db/init/01_schema.sql` です。
列ごとに「型・長さ」「NULL を許すか」「制約」を確かめ、Java 側の値が違反しうるかを考えます。

## サンプルアプリでは

### 設定（application.yml 12〜15 行目）

```yaml title="sample-app/src/main/resources/application.yml" linenums="12"
mybatis:
  mapper-locations: classpath:mapper/*.xml
  configuration:
    map-underscore-to-camel-case: true
```

- `mapper-locations`: `src/main/resources/mapper/` の XML をすべて読みます
- `map-underscore-to-camel-case`: SELECT の結果の列名 `order_no` を、Java の項目名 `orderNo` に対応づけます

### 会員の Mapper

```java title="sample-app/src/main/java/com/example/sample/member/MemberMapper.java" linenums="6"
/** 会員テーブルの SQL（本体は resources/mapper/MemberMapper.xml）. */
@Mapper
public interface MemberMapper {

    Optional<Member> findById(long id);

    boolean existsByEmail(String email);

    /** 登録し、採番された ID を member.id に入れる（useGeneratedKeys）. */
    int insert(MemberRecord member);
}
```

```xml title="sample-app/src/main/resources/mapper/MemberMapper.xml" linenums="3"
<mapper namespace="com.example.sample.member.MemberMapper">

  <select id="findById" resultType="com.example.sample.member.Member">
    SELECT id, name, email FROM member WHERE id = #{id}
  </select>

  <select id="existsByEmail" resultType="boolean">
    SELECT EXISTS (SELECT 1 FROM member WHERE email = #{email})
  </select>

  <insert id="insert" useGeneratedKeys="true" keyProperty="id" keyColumn="id">
    INSERT INTO member (name, email) VALUES (#{name}, #{email})
  </insert>
</mapper>
```

4 点の対応を表にします。

| メソッド | XML | `#{...}` の出どころ | 戻り値 |
| --- | --- | --- | --- |
| `findById(long id)` | 5〜7 行目 | 引数 `id` | 0 件なら空の `Optional`、1 件なら `Member` |
| `existsByEmail(String email)` | 9〜11 行目 | 引数 `email` | `EXISTS` の結果（真偽値） |
| `insert(MemberRecord member)` | 13〜15 行目 | `MemberRecord` の `getName()`、`getEmail()` | 登録した行数 |

`insert` の読みどころは、13 行目の 3 つの属性です。

| 属性 | 意味 |
| --- | --- |
| `useGeneratedKeys="true"` | DB が採番した値（`BIGSERIAL` の `id`）を受け取る |
| `keyColumn="id"` | 受け取る列は `id` |
| `keyProperty="id"` | 受け取った値を、引数のオブジェクトの `id` 項目に入れる |

`INSERT` の列に `id` が無いのは、DB が採番するからです（`01_schema.sql` の `id BIGSERIAL PRIMARY KEY`）。

### MemberRecord が可変である理由

```java title="sample-app/src/main/java/com/example/sample/member/MemberRecord.java" linenums="3"
/** 登録用の可変オブジェクト（MyBatis が採番した ID を書き戻すため）. */
public class MemberRecord {

    private Long id;
    private String name;
    private String email;
```

```java title="sample-app/src/main/java/com/example/sample/member/MemberRecord.java" linenums="19"
    public void setId(Long id) {
        this.id = id;
    }
```

MyBatis は、採番した ID を `setId` で書き戻します。
`Member` は `record` なので、作った後で項目を変えられません。
そのため、登録には可変の `MemberRecord` を使い、ID が入った後で `toMember()`（31〜33 行目）で `Member` に変換します。
`setId` 以外のセッターが無いのは、変えてよいのが ID だけだからです。

### 注文の Mapper

```java title="sample-app/src/main/java/com/example/sample/order/OrderMapper.java" linenums="9"
    /**
     * 注文番号が未登録なら登録する（再実行しても重複しない＝冪等）.
     *
     * @return 登録した件数（既にあれば 0）
     */
    int insertIfAbsent(Order order);
```

```xml title="sample-app/src/main/resources/mapper/OrderMapper.xml" linenums="5"
  <!-- 注文番号が既にあれば何もしない（再実行しても重複しない） -->
  <insert id="insertIfAbsent">
    INSERT INTO orders (order_no, member_id, product_code, quantity)
    VALUES (#{orderNo}, #{memberId}, #{productCode}, #{quantity})
    ON CONFLICT (order_no) DO NOTHING
  </insert>
```

- `#{orderNo}` などは、引数 `Order`（`record`）の項目です
- `ON CONFLICT (order_no) DO NOTHING` は PostgreSQL の書き方で、「`order_no` が重複したら何もしない」という意味です
- 何もしなかったときは登録件数が 0 なので、戻り値が 0 になります
- 呼び出し側の `OrderImportService.importLines`（46〜50 行目）は、この 1 / 0 で「登録」と「重複」を数え分けます

冪等（べきとう。何度実行しても結果が同じ）の考え方は [30-11](30-11-idempotent-insert.md) で詳しく読みます。

### テーブル定義と合わせて読む

```sql title="local/db/init/01_schema.sql（dev-environment）"
CREATE TABLE orders (
    order_no     VARCHAR(20) PRIMARY KEY,
    member_id    BIGINT      NOT NULL REFERENCES member (id),
    product_code VARCHAR(20) NOT NULL,
    quantity     INTEGER     NOT NULL CHECK (quantity BETWEEN 1 AND 999),
    imported_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`ON CONFLICT (order_no)` が受け止めるのは、`order_no` の重複だけです。
それ以外の制約に違反すると、例外になります。

| 制約 | Java 側で防いでいるか |
| --- | --- |
| `order_no` の主キー（重複） | `ON CONFLICT` で 0 件として扱う |
| `quantity` の CHECK（1〜999） | `OrderImportService.parse`（70〜72 行目）で事前に弾く |
| `member_id` の外部キー（存在する会員か） | 防いでいない |
| `order_no`・`product_code` の `VARCHAR(20)` | 防いでいない |

防いでいない制約に違反したときの動きは、演習 4 で考えます。

### テストとの関係

Mapper の SQL そのものは、単体テストでは実行されません。

| テスト | Mapper の扱い |
| --- | --- |
| `MemberServiceTest`、`MemberControllerTest` | `InMemoryMapper`（Java の `Map` で代用） |
| `OrderImportServiceTest` | ラムダ式 `o -> stored.add(o.orderNo()) ? 1 : 0`（16 行目） |
| `members.feature`（Karate） | 起動中のアプリを通して、本物の DB で `MemberMapper.xml` を実行する |

`OrderMapper.xml` を本物の DB で確かめる自動テストはありません。
SQL を変えたら、ローカルの DB でバッチを実行して確かめる必要があります。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `MemberMapper.java` / `.xml` | Mapper（または DAO、Repository）と SQL の置き場所。注釈で SQL を書く流儀もある |
| `namespace` と `id` | 対応づけの規則。自動生成された Mapper（基本の CRUD）と手書きの Mapper の区別 |
| `#{...}` | `${...}` の使用箇所。並び順の指定などでやむを得ず使うときの対策 |
| `useGeneratedKeys` | 採番の方式（シーケンス、自動採番列、アプリでの採番） |
| `01_schema.sql` | テーブル定義書と、DB の変更を管理するツールのファイル |
| `ON CONFLICT` | DB 製品ごとの書き方（MERGE など）と、重複時の業務ルール |
| SQL の自動テストが無い | DB を使う結合テストの有無と、その実行方法 |

## もし Mapper と XML の対応づけがなかったら？

SQL がコードのあちこちに文字列で書かれることになります。
どの SQL がどのテーブルを触るかを探すのに、コード全体を検索する必要があります。
値を文字列の連結で SQL に埋め込みがちになり、SQL インジェクションの危険も増えます。

Mapper があれば、「このテーブルを触る SQL」は XML を見れば一覧できます。
テーブルの列を変えるときの影響範囲も、XML の検索で分かります。

## 理解度チェック

**問 1.** `MemberMapper.findById` の SQL が `MemberMapper.xml` のどれかは、何と何の一致で決まりますか。

??? note "答え"
    `namespace`（`com.example.sample.member.MemberMapper`）とインタフェースの完全な名前、
    `id`（`findById`）とメソッド名の一致で決まります。

**問 2.** `#{...}` と `${...}` の違いは何ですか。

??? note "答え"
    `#{...}` は値をパラメータとして安全に渡します。
    `${...}` は値を SQL の文字列にそのまま埋め込むので、SQL インジェクションの危険があります。

**問 3.** `insert` で採番された ID が `MemberRecord` に入るのは、どの属性のためですか。

??? note "答え"
    `MemberMapper.xml` 13 行目の `useGeneratedKeys="true"`、`keyProperty="id"`、`keyColumn="id"` のためです。

**問 4.** `insertIfAbsent` が 0 を返すのは、どんなときですか。

??? note "答え"
    `order_no` が既に登録されていて、`ON CONFLICT (order_no) DO NOTHING` により何も登録しなかったときです。

## コードを読むときの確認観点

- [ ] Mapper のメソッドと XML の `id` が、1 対 1 で対応しているか
- [ ] `${...}` が使われていないか。使われているなら、値がどこから来るか
- [ ] SQL の対象テーブルの制約（主キー、一意、外部キー、CHECK、長さ）を確かめたか
- [ ] 制約違反のうち、Java 側で事前に防いでいないものはどれか
- [ ] 戻り値（件数、`Optional`、真偽値）が、呼び出し側で正しく使われているか
- [ ] その SQL を本物の DB で確かめるテストがあるか

## 演習

1. `MemberMapper.existsByEmail` について、Java のメソッドと XML の対応を、4 点（`namespace`、`id`、`#{...}`、`resultType`）それぞれの行を示して説明しなさい。
2. 会員を登録したとき、API の応答の `id` に値が入るまでの流れを、XML・`MemberRecord`・`MemberService` の行を示して説明しなさい。
3. 同じ注文ファイル（2 行の注文）を 2 回取り込みました。
   2 回目の `insertIfAbsent` の戻り値と、`ImportResult` の値を、行を示して答えなさい。
4. 注文ファイルに、存在しない会員 ID（例: 99999）の行が 1 行だけ混ざっていました。
   他の行は正しいとします。取込の結果はどうなりますか。
   SQL・テーブル定義・`OrderImportService`・`OrderImportJob` の行を示して説明しなさい。
   また、この動きに単体テストが気づけない理由を答えなさい。
5. `MemberMapper.xml` の `#{email}` を `'${email}'` に書き換えると、どんな問題が起きますか。
   入力の例を挙げて説明しなさい。

解答は [30-08 解答](answers/30-08.md) にあります。

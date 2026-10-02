# 20-12 MyBatis（Mapper インターフェースと XML）

!!! abstract "到達目標"
    - Mapper インターフェースと Mapper XML の対応関係を説明できる
    - `#{}` と `${}` の違いと、`${}` を使ってはいけない理由を説明できる
    - 採番された ID を受け取る `useGeneratedKeys` の仕組みを読める
    - 新しい SQL を Mapper に追加できる

## 何か

MyBatis は、Java と SQL をつなぐライブラリです。
SQL は自分で書き、結果を Java のオブジェクトに詰める作業を MyBatis が行います。

MyBatis では、次の 2 つを組にして使います。

| もの | 置き場所 | 書くこと |
|---|---|---|
| Mapper インターフェース | `src/main/java/.../XxxMapper.java` | メソッドの名前・引数・戻り値 |
| Mapper XML | `src/main/resources/mapper/XxxMapper.xml` | メソッドごとの SQL |

インターフェースの実装クラスは書きません。
起動時に MyBatis が XML を読み、実装を自動で作って Spring の Bean にします。

## なぜ必要か

JDBC（Java 標準の DB 接続 API）だけで書くと、接続・SQL 実行・結果の詰め替え・後始末を毎回書くことになります。
MyBatis を使うと、その定型部分が無くなり、SQL と業務ロジックに集中できます。

また、SQL を XML に分けておくと、SQL だけを見てレビューできます。
チームの規約でも「SQL は Mapper XML に書く」と決めています。

## どうやるか

### 1. インターフェースと XML を対応させる

対応のルールは 3 つです。

- XML の `namespace` = インターフェースの完全修飾名（パッケージ名 + クラス名）
- XML の `id` = メソッド名
- 戻り値の型 = `resultType`（`SELECT` のとき）

例:

```java
@Mapper
public interface ProductMapper {
    Optional<Product> findByCode(String code);
}
```

```xml
<mapper namespace="com.example.app.product.ProductMapper">
  <select id="findByCode" resultType="com.example.app.product.Product">
    SELECT code, name, price FROM product WHERE code = #{code}
  </select>
</mapper>
```

`id` やメソッド名を打ち間違えると、呼び出したときに `BindingException` になります。

### 2. 列名とプロパティ名の対応

DB の列は `snake_case`（`product_code`）、Java は `camelCase`（`productCode`）が普通です。
設定 `map-underscore-to-camel-case: true` にすると、自動で対応付けます。

### 3. 値は `#{}` で渡す（`${}` は使わない）

| 書き方 | 動き | 安全性 |
|---|---|---|
| `#{name}` | SQL に `?` を置き、値は別に渡す（PreparedStatement） | 安全。値は SQL として解釈されない |
| `${name}` | 値の文字列を SQL にそのまま埋め込む | 危険。SQL インジェクションになる |

**SQL インジェクション**とは、入力に SQL の断片を混ぜて、意図しない SQL を実行させる攻撃です。

!!! failure "悪い例"
    ```xml
    <!-- 例: ${} は文字列をそのまま埋め込む -->
    <select id="findByEmail" resultType="com.example.app.member.Member">
      SELECT id, name, email FROM member WHERE email = '${email}'
    </select>
    ```
    `email` に `' OR '1'='1` を渡すと、SQL は次のようになり、全会員が返ります。
    ```sql
    SELECT id, name, email FROM member WHERE email = '' OR '1'='1'
    ```

!!! success "良い例"
    ```xml
    <!-- 例: #{} なら値は ? に束縛され、SQL の一部として解釈されない -->
    <select id="findByEmail" resultType="com.example.app.member.Member">
      SELECT id, name, email FROM member WHERE email = #{email}
    </select>
    ```

チームの品質ゲート D9 は、Mapper XML に `${}` があると失敗します。
並び順の列名のように、どうしても SQL の一部を切り替えたいときは、決まった候補から選ぶ形にします。

例:

```xml
<!-- 例: 並び順は、入力をそのまま埋め込まず、決まった候補から選ぶ -->
<select id="search" resultType="com.example.app.member.Member">
  SELECT id, name, email FROM member
  <choose>
    <when test="sort == 'name'">ORDER BY name</when>
    <otherwise>ORDER BY id</otherwise>
  </choose>
</select>
```

### 4. 引数が複数のとき

引数が 1 つなら `#{名前}` で参照できます。
複数のときは、`@Param("名前")` を付けるか、コンパイル時に `-parameters` を付けて引数名を残します。
オブジェクトを 1 つ渡すと、`#{orderNo}` のようにプロパティ名で参照できます。

### 5. 戻り値の型

| 戻り値 | 意味 |
|---|---|
| `Optional<T>` | 0 件または 1 件（0 件なら空） |
| `List<T>` | 0 件以上 |
| `boolean` | `SELECT EXISTS (...)` の結果など |
| `int`（INSERT / UPDATE / DELETE） | 更新した件数 |

## サンプルアプリでは

### 設定

`sample-app/src/main/resources/application.yml` の 12〜15 行目です。

```yaml
mybatis:
  mapper-locations: classpath:mapper/*.xml
  configuration:
    map-underscore-to-camel-case: true
```

- `mapper-locations` で XML の置き場所を指定しています
- `map-underscore-to-camel-case` で `product_code` → `productCode` と対応付けます

### 会員の Mapper

`sample-app/src/main/java/com/example/sample/member/MemberMapper.java` です。

```java
/** 会員テーブルの SQL（本体は resources/mapper/MemberMapper.xml）. */
@Mapper
public interface MemberMapper {

    Optional<Member> findById(long id);

    boolean existsByEmail(String email);

    /** 登録し、採番された ID を member.id に入れる（useGeneratedKeys）. */
    int insert(MemberRecord member);
}
```

対応する `sample-app/src/main/resources/mapper/MemberMapper.xml` です。

```xml
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

- `namespace` がインターフェースの完全修飾名、各 `id` がメソッド名と一致しています
- 値はすべて `#{}` で渡しています
- `findById` は `Optional<Member>` を返します。0 件なら空の `Optional` になり、Service が `NotFoundException` に変えます

### 採番された ID の受け取り

`insert` の `useGeneratedKeys="true" keyProperty="id"` は、DB が採番した `id` を引数のオブジェクトに書き戻す指定です。
書き戻すには setter が要るため、登録用に可変のクラスを用意しています。
`sample-app/src/main/java/com/example/sample/member/MemberRecord.java` です。

```java
/** 登録用の可変オブジェクト（MyBatis が採番した ID を書き戻すため）. */
public class MemberRecord {

    private Long id;
```

`MemberService.register` は `insert` の後に `rec.toMember()` で、ID 入りの `Member`（record）に変えて返します。
読み取り用は不変の record、登録用は可変のクラス、と使い分けている点に注目してください。

### 注文の Mapper

`sample-app/src/main/java/com/example/sample/order/OrderMapper.java` は `insertIfAbsent(Order order)` だけを持ちます。
XML では引数 `Order` の項目を `#{orderNo}`、`#{memberId}` のように参照しています。

```xml
  <insert id="insertIfAbsent">
    INSERT INTO orders (order_no, member_id, product_code, quantity)
    VALUES (#{orderNo}, #{memberId}, #{productCode}, #{quantity})
    ON CONFLICT (order_no) DO NOTHING
  </insert>
```

戻り値 `int` は登録した件数で、既にあれば 0 です（[20-11 SQL の基本](20-11-sql.md)）。

### 引数名を残すコンパイル設定

`sample-app/build.gradle` の 14〜18 行目で `-parameters` を付けています。

```groovy
tasks.withType(JavaCompile).configureEach {
    options.release = 17
    options.encoding = 'UTF-8'
    options.compilerArgs += ['-parameters']
}
```

これにより、引数が複数あるメソッドでも `#{引数名}` で参照できます。

## もし MyBatis がなかったら？

DB を読むたびに、接続の取得・`PreparedStatement` の準備・結果の 1 列ずつの詰め替え・後始末を書くことになります。
同じ定型コードがあちこちに増え、後始末の漏れで接続が枯渇する事故も起きやすくなります。

一方、MyBatis を使っていても `${}` を使えば、SQL インジェクションの穴が開きます。
MyBatis が守ってくれるのは `#{}` を使ったときだけです。

## 理解度チェック

1. `MemberMapper` の実装クラスはどこにありますか。

    ??? note "答え"
        ソースにはありません。起動時に MyBatis が `MemberMapper.xml` を読み、実装を自動で作ります。

2. `#{email}` と `'${email}'` の違いを説明してください。

    ??? note "答え"
        `#{email}` は SQL に `?` を置き、値を別に渡します。値は SQL として解釈されません。
        `'${email}'` は値の文字列を SQL に埋め込むため、SQL インジェクションの原因になります。

3. `MemberRecord` が record ではなく、setter のある普通のクラスなのはなぜですか。

    ??? note "答え"
        `useGeneratedKeys` で、DB が採番した `id` を MyBatis が書き戻すためです。
        record は不変で setter が無いため、書き戻せません。

4. XML の `<select id="findById">` を `findByID` に書き間違えると、何が起きますか。

    ??? note "答え"
        `MemberMapper.findById` に対応する SQL が見つからず、呼び出したときに `BindingException` になります。

5. 一覧の並び順を利用者が選べるようにしたいとき、`ORDER BY ${sort}` と書いてはいけないのはなぜですか。代わりにどうしますか。

    ??? note "答え"
        `sort` に SQL の断片を入れられるためです（品質ゲート D9 でも失敗します）。
        `<choose>` などで、決まった候補の中から選ぶ形にします。

## コードを読むときの確認観点

- [ ] XML の `namespace` と `id` が、インターフェースとメソッド名に一致している
- [ ] 値はすべて `#{}` で渡しており、`${}` が無い
- [ ] 戻り値の型（`Optional` / `List` / `int`）が、SQL の件数の性質に合っている
- [ ] 採番した ID を使う場合、`useGeneratedKeys` と `keyProperty` が設定されている
- [ ] SQL に業務判断（条件分岐の多用など）が入り込んでいない
- [ ] 列名とプロパティ名の対応（`snake_case` ↔ `camelCase`）が取れている

参考: [MyBatis 3 リファレンス（Mapper XML）](https://mybatis.org/mybatis-3/ja/sqlmap-xml.html)、[MyBatis Spring Boot Starter](https://mybatis.org/spring-boot-starter/mybatis-spring-boot-autoconfigure/)

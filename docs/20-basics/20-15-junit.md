# 20-15 JUnit 5 と AssertJ

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - JUnit 5 の `@Test` と `@ParameterizedTest` で単体テストを書ける
    - AssertJ の `assertThat` / `assertThatThrownBy` で期待値を確かめられる
    - テスト名から確かめている内容が分かる名前を付けられる
    - Given / When / Then の形でテストを読める

## 何か

**単体テスト**は、クラスやメソッドを 1 つずつ取り出して、期待どおりに動くかを確かめるプログラムです。

| ライブラリ | 役割 |
|---|---|
| JUnit 5 | テストを見つけて実行する土台。`@Test` などのアノテーションを提供 |
| AssertJ | 「結果がこうであるべき」を読みやすく書くためのライブラリ |

どちらも `spring-boot-starter-test` に含まれています。
`./gradlew test` で実行し、結果は `build/reports/tests/test/index.html` で見られます。

## なぜ必要か

- **壊していないことを確かめるため**: 修正のたびに手で全部を試すのは不可能です。テストなら数秒で確かめられます
- **仕様を残すため**: 「重複したメールアドレスは登録できない」のような決まりが、動くコードとして残ります
- **品質ゲートのため**: チームでは単体テストの全件成功（D3）と、Service・Job の分岐網羅率（D4。既定 80%、目標 100%）が必須です

テストの期待値は **設計書** から決めます。
実装を動かして出た値を期待値に書くと、実装の誤りまで「正しい」ことになってしまいます。

## どうやるか

### 1. Given / When / Then で並べる

テストの中身を 3 つに分けると読みやすくなります。

- **Given**（前提）: テストの準備
- **When**（操作）: 確かめたい処理を 1 回呼ぶ
- **Then**（確認）: 結果を確かめる

コメントを書かなくても、空行で 3 つを区切るだけで十分伝わります。

### 2. AssertJ で確かめる

例:

```java
assertThat(result).isEqualTo(3);                 // 等しい
assertThat(list).containsExactly("a", "b");      // 中身と順序が一致
assertThat(list).isEmpty();                      // 空
assertThat(text).contains("見出し");              // 部分一致
assertThatThrownBy(() -> service.get(99))        // 例外が投げられる
        .isInstanceOf(NotFoundException.class);
```

`assertThat(実際の値)` から書き始め、`.` の後に候補が出るので、IDE の補完で選べます。

!!! failure "悪い例"
    ```java
    // 例: 確かめる内容が弱い。null でないことしか分からない
    @Test
    void test1() {
        Member m = service.register("A", "a@example.com");
        assertThat(m).isNotNull();
    }
    ```

!!! success "良い例"
    ```java
    // 例: 名前で観点が分かり、設計書の期待値をそのまま確かめている
    @Test
    void register_assignsIdAndKeepsName() {
        Member m = service.register("A", "a@example.com");

        assertThat(m.id()).isEqualTo(1L);
        assertThat(m.name()).isEqualTo("A");
    }
    ```

### 3. テスト名の付け方

チームの規約では、`対象_条件_期待` か、期待を文にした名前にします。

| よい名前 | 分かること |
|---|---|
| `register_rejectsDuplicateEmailIgnoringCase` | `register` が、大文字小文字違いの重複を拒否する |
| `get_throwsNotFoundForUnknownId` | `get` が、無い ID で NotFound を投げる |
| `rerunIsIdempotent` | 再実行しても結果が変わらない |

`test1` や `testRegister` では、失敗したときに何が壊れたか分かりません。

### 4. 1 テスト 1 観点

1 つのテストで確かめる観点は 1 つにします。
アサーションが複数あってもかまいませんが、同じ観点のためのものにします。
観点が混ざると、失敗したときに原因を絞りにくくなります。

### 5. 境界値は `@ParameterizedTest` でまとめる

正常系・異常系に加え、**境界値**（範囲の端。1〜999 なら 0・1・999・1000）を必ず確かめます。
同じ形のテストを値だけ変えて並べるときは、`@ParameterizedTest` でまとめます。

### 6. アサーションの無いテストは書かない

アサーションが無いテストは、例外が出なければ必ず成功します。
何も確かめていないのに「テスト済み」に見えてしまうため、品質ゲート D7 でも検出します。

## サンプルアプリでは

### 会員の業務ロジック

`sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java` の 42〜59 行目です。

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java @exercise-base -->
```java
@Test
void register_normalizesEmailAndAssignsId() {
    Member m = service.register(" 山田 太郎 ", " Taro@Example.COM ");

    assertThat(m.id()).isEqualTo(1L);
    assertThat(m.name()).isEqualTo("山田 太郎");
    assertThat(m.email()).isEqualTo("taro@example.com");
}

@Test
void register_rejectsDuplicateEmailIgnoringCase() {
    service.register("A", "a@example.com");

    assertThatThrownBy(() -> service.register("B", "A@EXAMPLE.com"))
            .isInstanceOf(BusinessException.class)
            .extracting(e -> ((BusinessException) e).getMessageId())
            .isEqualTo(MessageIds.EMAIL_ALREADY_USED);
}
```

- 1 つ目は When（`register` の呼び出し）と Then（`assertThat` 3 つ）を空行で分けています。Given はフィールドの初期化です
- 2 つ目は Given（1 件目の登録）の後に空行を置き、When と Then を `assertThatThrownBy` で 1 つにまとめています
- `extracting` で例外からメッセージ ID を取り出し、例外の種類だけでなく **どの業務エラーか** まで確かめています

### 注文取込の業務ロジック

`sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java` の 34〜52 行目です。

<!-- src: sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java @exercise-base -->
```java
@Test
void rerunIsIdempotent() {
    List<String> lines = List.of(OrderImportService.HEADER, "A001,1,P-01,2");
    service.importLines(lines);

    ImportResult second = service.importLines(lines);

    assertThat(second.imported()).isZero();
    assertThat(second.duplicated()).isEqualTo(1);
}

@Test
void badLinesAreReportedWithLineNumbersAndOthersContinue() {
    ImportResult r = service.importLines(List.of(
            OrderImportService.HEADER, "A001,x,P-01,2", "A002,1,P-02,0", "A003,1,P-03,5"));

    assertThat(r.imported()).isEqualTo(1);
    assertThat(r.errors()).containsExactly("2: member_id が数値ではありません", "3: quantity は 1〜999 です（0）");
}
```

- `rerunIsIdempotent` は Given（1 回目の取込）・When（2 回目）・Then がきれいに分かれた例です
- `containsExactly` は、要素と **順序** の両方を確かめます。行番号の順にエラーが並ぶことまで保証できます

同じファイルの 61〜70 行目は、パラメータ化テストです。

<!-- src: sample-app/src/test/java/com/example/sample/order/OrderImportServiceTest.java @exercise-base -->
```java
@ParameterizedTest
@CsvSource(delimiter = '|', value = {
    "A001,1,P-01        | 列数が 4 ではありません（3 列）",
    "' ,1,P-01,1'       | order_no が空です",
    "'A001,1, ,1'       | product_code が空です",
    "A001,1,P-01,1000   | quantity は 1〜999 です（1000）"
})
void parseRejects(String line, String message) {
    assertThatThrownBy(() -> OrderImportService.parse(line)).hasMessage(message);
}
```

- 入力の CSV にカンマが含まれるので、区切り文字を `|` に変えています
- `' ,1,P-01,1'` のように `'` で囲むと、先頭の空白も値として残ります
- `1000` は上限 999 のすぐ外側で、境界値の確認です
- `hasMessage` はメッセージの完全一致です。部分一致でよいときは `hasMessageContaining` を使います（同じファイルの `wrongHeaderIsRejected`）

### テスト名のスタイル

サンプルアプリには、`register_normalizesEmailAndAssignsId`（`対象_期待`）と `importsValidLinesAndSkipsDuplicates`（期待を文で）の 2 つのスタイルがあります。
どちらも規約で認められています。1 つのテストクラスの中ではそろえると読みやすくなります。

### カバレッジ

`sample-app/build.gradle` の 38〜43 行目で、`test` の後に JaCoCo のレポートを作ります。

<!-- src: sample-app/build.gradle @exercise-base -->
```groovy
tasks.named('test') {
    useJUnitPlatform {
        excludeTags 'karate'
    }
    finalizedBy jacocoTestReport
}
```

`./gradlew test` の後、`build/reports/jacoco/test/html/index.html` で行と分岐の網羅率を見られます。
緑でない分岐（通っていない `if` の片側）が、足りないテストの候補です。

## もし単体テストがなかったら？

修正のたびに、画面や API を手で操作して確かめることになります。
時間がかかるうえ、確かめ漏れが必ず出ます。
「メールアドレスの大文字小文字を区別しない」のような細かい決まりは、誰かが気付かずに壊してしまいます。

また、テストが無いと、コードを整理する（リファクタリング）勇気が持てません。
壊したかどうか分からないからです。結果として、読みにくいコードがそのまま残り続けます。

## 理解度チェック

1. `test1` という名前のテストが失敗しました。何が問題ですか。

    ??? note "答え"
        名前から確かめている内容が分からず、何が壊れたかをテストの中身を読むまで判断できません。
        `対象_条件_期待` などの名前にします。

2. `containsExactly("2: ...", "3: ...")` と `contains("2: ...", "3: ...")` の違いは何ですか。

    ??? note "答え"
        `containsExactly` は要素の過不足と順序まで確かめます。
        `contains` は指定した要素が含まれていればよく、他の要素や順序は問いません。

3. `quantity` が 1〜999 のとき、境界値として確かめる値を挙げてください。

    ??? note "答え"
        0・1・999・1000 です。範囲のすぐ内側と、すぐ外側を確かめます。

4. `rerunIsIdempotent` の Given・When・Then はそれぞれどの行ですか。

    ??? note "答え"
        Given は `lines` の用意と 1 回目の `importLines`、When は 2 回目の `importLines`、Then は 2 つの `assertThat` です。

5. 実装を動かして出た値を、そのまま期待値に書いてはいけないのはなぜですか。

    ??? note "答え"
        実装に誤りがあっても、テストがその誤りを「正しい」と確かめてしまうからです。期待値は設計書から決めます。

## コードを読むときの確認観点

- [ ] テスト名から、対象・条件・期待が分かる
- [ ] Given / When / Then が空行などで区切られ、When が 1 回だけになっている
- [ ] アサーションがあり、`isNotNull()` だけのような弱い確認で済ませていない
- [ ] 正常系・異常系・境界値がそろっている
- [ ] 例外のテストで、種類だけでなくメッセージ ID やメッセージまで確かめている
- [ ] 期待値が設計書から決められている

参考: [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)、[AssertJ](https://assertj.github.io/doc/)

# 20-17 Karate の API テスト

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - Karate の feature ファイル（Given / When / Then）を読める
    - `match` とあいまい一致（`#number` など）で応答を確かめられる
    - `karate-config.js` で接続先を環境ごとに切り替える仕組みを説明できる
    - サンプルアプリの API テストを Gradle で実行できる

## 何か

**Karate** は、API を外から呼んで確かめるテストツールです。
テストは `.feature` という拡張子のファイルに、英語に近い文で書きます。

| テストの種類 | 確かめる範囲 | サンプルアプリの道具 |
|---|---|---|
| 単体テスト | クラス 1 つ（DB は使わない） | JUnit 5 + AssertJ（[20-15](20-15-junit.md)） |
| Controller のテスト | Controller と例外ハンドラ（サーバーは起動しない） | MockMvc（[20-16](20-16-mock.md)） |
| API テスト（結合） | 起動したアプリ + DB を HTTP で呼ぶ | Karate（この章） |

feature ファイルの基本の形は次のとおりです。

- `Feature:` テスト対象の説明
- `Background:` 各シナリオの前に毎回実行する準備
- `Scenario:` 1 つのテストケース
- `Given` / `And` / `When` / `Then` / `*` で始まる 1 行が 1 ステップ（`*` は種類を問わない書き方）

## なぜ必要か

単体テストと MockMvc のテストは、DB を使いません。
そのため、次のことは確かめられていません。

- Mapper XML の SQL が正しく動くか
- DB の制約（`UNIQUE` など）とトランザクションが期待どおりか
- JSON の変換や設定ファイルを含め、アプリ全体として正しく応答するか

Karate のテストは、本物のアプリと DB に HTTP でリクエストを送るので、これらをまとめて確かめられます。
チームの品質ゲート D10 では、設計書の結合シナリオが実在し、`Then` / `match` があることを確かめます。

## どうやるか

### 1. リクエストを組み立てて送る

例:

```gherkin
Scenario: 商品を照会できる
  Given url 'http://localhost:8080'
  And path '/api/v1/products', 'P-001'
  When method get
  Then status 200
```

- `url` で接続先、`path` でパスを指定します。`path` にカンマで値を並べると `/` でつながります
- `request` で送る本文（JSON）を指定します
- `method get` / `method post` で送信します
- `status` で HTTP ステータスを確かめます

### 2. `match` で応答を確かめる

| 書き方 | 意味 |
|---|---|
| `match response == { ... }` | JSON 全体が一致（余分な項目があれば失敗） |
| `match response contains { ... }` | 指定した項目を含む |
| `match response.email == email` | 項目 1 つを確かめる |
| `'#number'` / `'#string'` / `'#notnull'` | 値の中身ではなく **型や存在** を確かめる（あいまい一致） |
| `'#(変数名)'` | 変数の値を JSON の中に埋め込む |

採番される ID のように、毎回値が変わる項目は `'#number'` で確かめます。

!!! failure "悪い例"
    ```gherkin
    # 例: ステータスしか見ておらず、応答の中身が誤っていても成功する
    When method post
    Then status 201
    ```

!!! success "良い例"
    ```gherkin
    # 例: ステータスに加えて、応答の中身を match で確かめる
    When method post
    Then status 201
    And match response == { id: '#number', name: '会員 一郎', email: '#(email)' }
    ```

### 3. 何度実行しても通るデータにする

API テストは、同じ DB に対して何度も実行します。
決まったメールアドレスで登録すると、2 回目は「登録済み」で失敗します。
実行ごとに一意な値（UUID など）を作るか、テストの前後でデータを整えます。

### 4. 接続先は `karate-config.js` で切り替える

接続先の URL をシナリオに直接書くと、環境を変えるたびに直す必要があります。
`karate-config.js` で環境（`karate.env`）ごとの値を返し、シナリオでは変数を使います。

## サンプルアプリでは

### シナリオ

`sample-app/src/test/resources/karate/members.feature` の 1〜18 行目です。

```gherkin
Feature: 会員 API（API0001 照会 / API0002 登録）

  Background:
    * url baseUrl
    * def email = 'karate-' + java.util.UUID.randomUUID() + '@example.com'

  Scenario: 登録した会員を照会できる
    Given path '/api/v1/members'
    And request { name: '結合 テスト', email: '#(email)' }
    When method post
    Then status 201
    And match response == { id: '#number', name: '結合 テスト', email: '#(email)' }
    * def id = response.id

    Given path '/api/v1/members', id
    When method get
    Then status 200
    And match response.email == email
```

- `Background` で、接続先を `baseUrl` に設定し、毎回違うメールアドレスを作ります。何度実行しても重複しません
- 登録の応答は `match response ==` で全体を確かめます。`id` は採番されるので `'#number'` です
- `* def id = response.id` で ID を変数に取り、次の照会のパスに使っています

同じファイルの 20〜36 行目では、異常系を確かめています。

```gherkin
  Scenario: 同じメールアドレスは登録できない
    Given path '/api/v1/members'
    And request { name: 'A', email: '#(email)' }
    When method post
    Then status 201

    Given path '/api/v1/members'
    And request { name: 'B', email: '#(email)' }
    When method post
    Then status 409
    And match response.messageId == 'APPE0003'

  Scenario: 存在しない会員は 404
    Given path '/api/v1/members', 999999999
    When method get
    Then status 404
    And match response.messageId == 'APPE0002'
```

- ステータスだけでなく、`messageId` まで確かめています。設計書のメッセージ ID と突き合わせられます
- 重複のシナリオは、本物の DB で `existsByEmail` の SQL が動くことの確認にもなっています

### 接続先の設定

`sample-app/src/test/resources/karate-config.js` です。

```javascript
function fn() {
  var env = karate.env || 'local';
  var config = { baseUrl: 'http://localhost:8080' };
  if (env === 'dev') {
    // クラウドの開発環境に向けるとき: -Dkarate.env=dev -DbaseUrl=https://<your-dev-host>
    config.baseUrl = karate.properties['baseUrl'];
  }
  return config;
}
```

- 既定（`local`）では、ローカルで起動したアプリ（`http://localhost:8080`）に向けます
- `dev` のときは、実行時に `-DbaseUrl=...` で渡した URL に向けます
- 返したオブジェクトの項目（`baseUrl`）が、feature ファイルで変数として使えます

### JUnit から実行するクラス

`sample-app/src/test/java/karate/ApiKarateTest.java` の 14〜21 行目です。

```java
@Tag("karate")
class ApiKarateTest {

    @Karate.Test
    Karate members() {
        return Karate.run("classpath:karate/members.feature");
    }
}
```

- Karate のシナリオは、JUnit 5 のテストとして実行されます
- `@Tag("karate")` で、通常の単体テストと区別しています

### Gradle のタスク

`sample-app/build.gradle` の 37〜56 行目です。

```groovy
// 単体テスト（DB・外部サービス不要）。API テスト（Karate）は起動中のアプリが要るので除外する
tasks.named('test') {
    useJUnitPlatform {
        excludeTags 'karate'
    }
    finalizedBy jacocoTestReport
}

// API テスト: アプリを起動してから ./gradlew karateTest
tasks.register('karateTest', Test) {
    description = 'Karate による API テスト（アプリを先に起動しておく）'
    group = 'verification'
    testClassesDirs = sourceSets.test.output.classesDirs
    classpath = sourceSets.test.runtimeClasspath
    useJUnitPlatform {
        includeTags 'karate'
    }
    systemProperty 'karate.env', System.getProperty('karate.env', 'local')
    outputs.upToDateWhen { false }
}
```

- `test` は `karate` タグを **除外** し、`karateTest` は `karate` タグ **だけ** を実行します
- `karate.env` は、Gradle の実行時に `-Dkarate.env=dev` と指定すれば切り替わります。無ければ `local` です
- テストは Gradle とは別の JVM で動きます。`systemProperty` で渡した値だけが、テスト側に届きます

!!! note "気付いておきたい点"
    この `build.gradle` がテストの JVM に渡しているのは `karate.env` だけです。
    `./gradlew karateTest -Dkarate.env=dev -DbaseUrl=...` としても、`baseUrl` はテスト側に届きません。
    `dev` に向けて実行するには、`systemProperty 'baseUrl', System.getProperty('baseUrl')` のような 1 行を足す必要があります。
- `outputs.upToDateWhen { false }` で、ソースに変更が無くても毎回実行します。相手はアプリなので、毎回確かめる必要があるからです

### 実行のしかた

1. DB と S3 エミュレータを起動します（`dev-environment/local` で `docker compose up -d --wait`）
2. 別のターミナルでアプリを起動します（`./gradlew bootRun --args='--spring.profiles.active=local'`）
3. `sample-app` で `./gradlew karateTest` を実行します
4. コンソールに表示される HTML レポートを開き、シナリオごとの結果を確かめます

## もし API テストがなかったら？

単体テストがすべて成功していても、Mapper XML の列名の打ち間違いや、設定ファイルの誤りは見つかりません。
こうした誤りは、画面から操作したときや本番で初めて見つかります。

手で API を呼んで確かめる方法もありますが、毎回同じ手順を正確に繰り返すのは困難です。
Karate のシナリオにしておけば、誰でも同じ確認を何度でも実行でき、確認の記録も残ります。

## 理解度チェック

1. `./gradlew test` で `ApiKarateTest` が実行されないのはなぜですか。

    ??? note "答え"
        `test` タスクが `excludeTags 'karate'` で、`@Tag("karate")` の付いたテストを除外しているからです。
        API テストは起動中のアプリが要るため、単体テストとは分けています。

2. `Background` でメールアドレスに UUID を入れているのはなぜですか。

    ??? note "答え"
        何度実行しても、メールアドレスが重複しないようにするためです。
        決まった値だと、2 回目の実行で「登録済み」（409）になり、正常系のシナリオが失敗します。

3. `match response == { id: '#number', ... }` の `'#number'` は何を確かめていますか。

    ??? note "答え"
        `id` が数値であることです。採番される値は毎回変わるので、値そのものではなく型を確かめています。

4. クラウドの開発環境に向けて Karate を実行するには、どう指定しますか。

    ??? note "答え"
        `karate.env` を `dev` にし、`baseUrl` のシステムプロパティで接続先を渡します。
        ただし今の `build.gradle` は `karate.env` しかテストの JVM に渡さないため、`baseUrl` を渡す設定を足す必要があります。
        足した後は `./gradlew karateTest -Dkarate.env=dev -DbaseUrl=https://<開発環境のホスト>` で実行できます。

5. `Then status 201` だけで終わるシナリオの問題は何ですか。

    ??? note "答え"
        応答の中身が誤っていても成功してしまいます。`match` で応答の項目（ID・メッセージ ID など）も確かめます。

## コードを読むときの確認観点

- [ ] シナリオがステータスだけでなく、`match` で応答の中身（メッセージ ID など）を確かめている
- [ ] 何度実行しても通るように、テストデータが一意になっている
- [ ] 接続先の URL がシナリオに直書きされず、`karate-config.js` の変数を使っている
- [ ] 正常系だけでなく、異常系（409・404・400 など）のシナリオがある
- [ ] シナリオが `@ignore` で無効化されていない
- [ ] 単体テストと API テストが Gradle のタスクで分けられている

参考: [Karate（GitHub）](https://github.com/karatelabs/karate)、[Karate ドキュメント](https://docs.karatelabs.io/)

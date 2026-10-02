# 30-15 Karate のシナリオを読む

!!! abstract "到達目標"
    - `members.feature` のシナリオを読み、どの API をどう確かめているか説明できる
    - `karate-config.js` と `build.gradle` で、接続先と実行方法が決まる仕組みを読める
    - 単体テストと Karate のテストが、それぞれ何を確かめているかを区別できる
    - シナリオを 1 つ追加できる

## 何か

**Karate** は、API に実際に HTTP の要求を送り、応答を確かめるテストの道具です。
テストは `.feature` という、英語の文に近い形式のファイルに書きます。

sample-app の Karate のテストは、次の 3 つのファイルでできています。

| ファイル | 役割 |
|---|---|
| `sample-app/src/test/resources/karate/members.feature` | シナリオ（何を送り、何を期待するか） |
| `sample-app/src/test/resources/karate-config.js` | 環境ごとの設定（接続先 `baseUrl`） |
| `sample-app/src/test/java/karate/ApiKarateTest.java` | JUnit から `.feature` を実行する入口 |

公式ドキュメントは [Karate](https://karatelabs.github.io/karate/) にあります。

## なぜ必要か

30-14 で読んだ単体テストは、DB も Spring の起動も使いません。
そのため、次のような「つないでみないとわからない」誤りは見つけられません。

- `MemberMapper.xml` の SQL の誤り
- `messages.properties` の本文の誤り
- DB の一意制約（`member.email` の `UNIQUE`）や自動採番の動き
- 実際の JSON の形（項目名、型）

Karate は、起動したアプリに外から要求を送るので、これらをまとめて確かめられます。
その代わり、アプリと DB を起動しておく必要があり、単体テストより時間がかかります。

## どうやるか

`.feature` は、**Given（準備）→ When（実行）→ Then（確認）** の順に読みます。

!!! failure "悪い例"
    `Scenario` の題名だけを読んで「登録と照会をテストしている」で済ませる。
    どの項目を、どの厳しさ（完全一致か一部か）で確かめているかを見ていない。

!!! success "良い例"
    1 つの要求ごとに、次の 4 点を書き出す。

    | 要求 | 送るもの | 期待するステータス | 確かめる項目と厳しさ |
    |---|---|---|---|
    | POST /api/v1/members | 名前・メール | 201 | 応答全体を完全一致（`==`） |
    | GET /api/v1/members/{id} | ― | 200 | `email` だけ |

主な書き方は次のとおりです。

| 書き方 | 意味 |
|---|---|
| `* url baseUrl` | 接続先の URL を設定する |
| `Given path '/api/v1/members', id` | URL のパスを組み立てる（`/api/v1/members/123`） |
| `And request { ... }` | 送る JSON |
| `When method post` | 要求を送る |
| `Then status 201` | ステータスコードを確かめる |
| `And match response == { ... }` | 応答が完全に一致することを確かめる |
| `'#number'` | 「数値なら何でもよい」という型の指定 |
| `'#(email)'` | 変数 `email` の値を埋め込む |
| `* def id = response.id` | 応答の値を変数に取っておく |

## サンプルアプリでは

### Background とシナリオ 1

```gherkin title="sample-app/src/test/resources/karate/members.feature（1〜18 行目）"
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

- 3〜5 行目: `Background` は、**各シナリオの前に毎回** 実行されます。シナリオごとに新しいメールアドレスが作られます
- 5 行目: メールアドレスに UUID（重複しない乱数の文字列）を入れています。同じ DB で何回実行しても、一意制約にぶつかりません
- 12 行目: `==` は完全一致です。`id`・`name`・`email` 以外の項目が応答にあると失敗します
- 13 行目: 採番された ID を取っておき、15 行目の照会に使います

### シナリオ 2・3

```gherkin title="sample-app/src/test/resources/karate/members.feature（20〜36 行目）"
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

- 29 行目: 409 は `ApiExceptionHandler.java` 31〜35 行目（`BusinessException` → `HttpStatus.CONFLICT`）から来ます
- 30 行目: `APPE0003` は `MessageIds.EMAIL_ALREADY_USED`（`MessageIds.java` 12 行目）です
- 33 行目: 999999999 番の会員は無いという前提です。DB の初期データ（`local/db/init/02_data.sql`）は会員 2 件だけです

### 接続先の設定

```javascript title="sample-app/src/test/resources/karate-config.js（全体）"
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

Karate は、実行のはじめにこの関数を呼び、返したオブジェクトの項目（`baseUrl`）を `.feature` から使えるようにします。
`karate.env` は環境の名前、`karate.properties` は Java のシステムプロパティ（`-D` で渡す値）です。

### 実行の入口と Gradle のタスク

```java title="sample-app/src/test/java/karate/ApiKarateTest.java（14〜21 行目）"
@Tag("karate")
class ApiKarateTest {

    @Karate.Test
    Karate members() {
        return Karate.run("classpath:karate/members.feature");
    }
}
```

```groovy title="sample-app/build.gradle（37〜56 行目）"
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

- `ApiKarateTest.java` 14 行目の `@Tag("karate")` が目印です
- `build.gradle` 40 行目: `test` タスクは `karate` の目印が付いたテストを **除外** します
- `build.gradle` 52 行目: `karateTest` タスクは、その目印が付いたテスト **だけ** を実行します
- `build.gradle` 54 行目: Gradle に渡した `-Dkarate.env=...` を、テストを実行する JVM に引き継ぎます
- `build.gradle` 55 行目: 毎回必ず実行します（前回の結果を使い回しません）

結果は `build/karate-reports/` に HTML で出ます（`local/README.md` の 9）。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| `members.feature` | API ごとのシナリオファイルと、API ID（API0001 など）との対応表 |
| `karate-config.js` の `env` 分岐 | 環境ごとの接続先・認証トークンの取り方 |
| UUID 入りのメールアドレス | テストデータの作り方と後片付けの方針（毎回作るか、決まったデータを使うか） |
| `@Tag("karate")` と `karateTest` | API テストを流すタスク・CI のジョブ。いつ（push ごと・夜間）流すか |
| `999999999` 番の会員 | 「存在しないこと」を前提にしたデータ。共有の環境で本当に無いか確認する |

## もし Karate のテストがなかったら？

単体テストがすべて通っても、`MemberMapper.xml` の列名を打ち間違えれば、API は 500 エラーを返します。
`messages.properties` から `APPE0003` の行を消しても、単体テストは気づきません。
こうした誤りは、手で `curl` を打つか、結合テストの段階まで見つからなくなります。

また、`build.gradle` の除外の設定（40 行目）が無ければ、`./gradlew test` がアプリの起動を前提にしてしまいます。
単体テストだけを素早く回す、という使い分けができなくなります。

## 理解度チェック

1. `Background` は、`members.feature` の実行中に何回実行されますか。

    ??? note "答え"
        3 回です。シナリオが 3 つあり、`Background` は各シナリオの前に毎回実行されます。
        そのため、シナリオごとに別のメールアドレスが使われます。

2. `./gradlew test` で Karate のテストが動かないのはなぜですか。

    ??? note "答え"
        `build.gradle` 40 行目の `excludeTags 'karate'` で、`@Tag("karate")` の付いた `ApiKarateTest` が除外されるからです。

3. シナリオ 1 の 12 行目と 18 行目で、確かめ方の厳しさはどう違いますか。

    ??? note "答え"
        12 行目は応答全体の完全一致（`==` で JSON 全体）です。項目の過不足があれば失敗します。
        18 行目は `email` の項目だけを確かめています。

4. 409 の応答は、sample-app のどこで作られますか。

    ??? note "答え"
        `MemberService.java` 27〜29 行目で `BusinessException` が投げられ、`ApiExceptionHandler.java` 31〜35 行目で 409（`CONFLICT`）に変換されます。

## コードを読むときの確認観点

- [ ] 各シナリオで、送る要求・期待するステータス・確かめる項目を書き出したか
- [ ] `==`（完全一致）と、一部の項目だけの確認を区別したか
- [ ] テストデータが、繰り返し実行しても衝突しない作りか確認したか
- [ ] 接続先（`baseUrl`）がどこから来るか、環境ごとに確認したか
- [ ] 単体テストと API テストの実行タスク・実行条件を確認したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **考える**: `members.feature` 5 行目のメールアドレスを、固定の `'karate@example.com'` に変えました。同じ DB で `./gradlew karateTest` を 2 回続けて実行すると、どのシナリオが、何回目に、どう失敗しますか。
2. **動きを予想する**: アプリを起動しないまま `./gradlew karateTest` を実行すると、どうなりますか。`./gradlew test` ではどうですか。
3. **小さな変更**: 「入力に誤りがあれば 400」を確かめるシナリオを `members.feature` に追加してください。名前を空、メールアドレスを `not-an-email` にし、ステータス・`messageId`・`details` の件数を確かめます。
4. **場所を探す（不具合の可能性）**: `karate-config.js` 5 行目のコメントどおり、`./gradlew karateTest -Dkarate.env=dev -DbaseUrl=https://<開発環境のホスト>` と実行しました。`baseUrl` はテストに届くでしょうか。`build.gradle` の該当行を根拠に答え、届かないなら直し方も書いてください。
5. **どのテストが落ちるか**: 会員の応答に、登録日時の項目 `createdAt` を足しました（`Member` レコードに項目を追加）。`members.feature` のどの行が失敗しますか。単体テストはどうですか。

解答: [30-15 解答](answers/30-15.md)

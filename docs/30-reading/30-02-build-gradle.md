# 30-02 build.gradle を読む

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `build.gradle` を「プラグイン → コンパイル設定 → 依存 → タスク」の順で読める
    - 依存の構成（`implementation` / `runtimeOnly` / `testImplementation`）の違いを説明できる
    - `./gradlew test` と `./gradlew karateTest` で、どのテストが動くかを説明できる
    - 依存の実際の版を、コマンドで確かめられる

## 何か

`build.gradle` は、Gradle（Java のビルドツール）にビルドの方法を教えるファイルです。
次の 4 つが書かれています。

| 部分 | 書かれていること |
| --- | --- |
| `plugins` | 使う機能（Java、Spring Boot、カバレッジ計測など）と、その版 |
| コンパイル設定 | どの Java の版向けに、どの文字コードでコンパイルするか |
| `dependencies` | 使うライブラリと、使う場面（本体用・実行時のみ・テスト用） |
| タスク | `test` などの作業の中身と、追加の作業（`karateTest`） |

Gradle の基本は [20-06 Gradle](../20-basics/20-06-gradle.md) で学びました。
この章では、サンプルアプリの `build.gradle` を 1 行ずつ読みます。

## なぜ必要か

`build.gradle` には、プロジェクトの「前提」が詰まっています。
Java の版、Spring Boot の版、使うデータベース、テストの分け方などです。
これを読まずにコードを書くと、次のような失敗をします。

- 手元の Java 21 では動くのに、CI（自動ビルド）の Java 17 でコンパイルできない
- `./gradlew test` が通ったのに、API テストを一度も実行していなかった
- 必要なライブラリを自分で追加し、版の食い違いでエラーになる

## どうやるか

### 上から 4 つの塊に分けて読む

`build.gradle` は、空行とコメントで塊に分かれています。
塊ごとに「これは 4 つのどれか」を判断しながら読みます。

### 依存の構成を読み分ける

依存（ライブラリ）は、使う場面ごとに構成（コンフィギュレーション）が分かれています。

| 構成 | コンパイル時 | 実行時 | テスト |
| --- | --- | --- | --- |
| `implementation` | 使える | 使える | 使える |
| `runtimeOnly` | 使えない | 使える | 使える（実行時） |
| `testImplementation` | 本体では使えない | 本体には入らない | 使える |
| `testRuntimeOnly` | 使えない | 本体には入らない | 実行時だけ使える |

版を書いていない依存は、BOM（版をまとめて決める一覧）から版が決まります。
Spring Boot の依存は `io.spring.dependency-management` プラグインが、AWS SDK は `platform(...)` が版を決めます。

### 読んだ内容はコマンドで確かめる

ファイルを読んで推測した内容は、Gradle のコマンドで確かめられます。

```bash
./gradlew tasks --all                                   # タスクの一覧
./gradlew dependencies --configuration runtimeClasspath  # 実行時に使われる依存と版
./gradlew dependencyInsight --dependency postgresql      # 特定の依存がどこから来たか
```

!!! failure "悪い例"
    ```groovy
    // 例: 版が分からないので、Spring Boot の依存に自分で版を書き足す
    implementation 'org.springframework.boot:spring-boot-starter-web:3.2.0'
    ```
    プラグインの Spring Boot と版が食い違い、起動時に原因の分かりにくいエラーになります。

!!! success "良い例"
    ```bash
    # 例: 版は書き足さず、実際に解決された版をコマンドで確かめる
    ./gradlew dependencyInsight --dependency spring-boot-starter-web
    ```
    版は `plugins` の Spring Boot に揃えて管理されている、と確認してから作業します。

## サンプルアプリでは

ファイルは `sample-app/build.gradle` です。
プロジェクト名は `sample-app/settings.gradle` の `rootProject.name = 'sample-app'` で決まります。

### プラグイン（3〜8 行目）

```groovy title="sample-app/build.gradle" linenums="3"
plugins {
    id 'java'
    id 'jacoco'
    id 'org.springframework.boot' version '4.0.7'
    id 'io.spring.dependency-management' version '1.1.7'
}
```

- `java`: Java のコンパイル・テスト・jar 作成のタスクを使えるようにします
- `jacoco`: テストのカバレッジ（どの行が実行されたか）を計測します
- `org.springframework.boot`: `bootRun`（起動）や `bootJar`（実行可能 jar）を使えるようにします
- `io.spring.dependency-management`: Spring Boot の依存の版を揃えます

1〜2 行目のコメントは「版はここで固定する」という運用ルールです。
コメントの運用ルールも、コードと同じくらい大切な情報です。

### コンパイル設定（13〜18 行目）

```groovy title="sample-app/build.gradle" linenums="13"
// 本番・CI は Java 17。ローカルが 21 でも 17 向けにコンパイルする（21 固有の API を使わせない）
tasks.withType(JavaCompile).configureEach {
    options.release = 17
    options.encoding = 'UTF-8'
    options.compilerArgs += ['-parameters']
}
```

- `release = 17`: Java 17 の API だけを使ってコンパイルします。手元の JDK が 21 でも、21 で追加された API はコンパイルエラーになります
- `encoding = 'UTF-8'`: 日本語のコメントや文字列を正しく読みます
- `-parameters`: メソッドの引数名をクラスファイルに残します。Spring などが引数名を使って値を結びつける場面で必要です

CI でも Java 17 を使っています（`dev-environment/.github/workflows/ci.yml` の `java-version: "17"`）。

### 依存（24〜35 行目）

```groovy title="sample-app/build.gradle" linenums="24"
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.mybatis.spring.boot:mybatis-spring-boot-starter:4.0.1'
    implementation platform('software.amazon.awssdk:bom:2.29.0')
    implementation 'software.amazon.awssdk:s3'
    runtimeOnly 'org.postgresql:postgresql'

    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'io.karatelabs:karate-junit5:1.5.1'
    testRuntimeOnly 'org.junit.platform:junit-platform-launcher'
}
```

| 行 | 依存 | コードのどこで使うか |
| --- | --- | --- |
| 25 | Web（REST API） | `MemberController`、`ApiExceptionHandler` |
| 26 | 入力チェック | `@NotBlank`、`@Email`、`@Valid` |
| 27 | MyBatis | `MemberMapper`、`OrderMapper` と XML |
| 28〜29 | AWS SDK（S3） | `S3Config`、`DefaultFileFetcher` |
| 30 | PostgreSQL の JDBC ドライバ | コードからは直接使わない（実行時に DB へ接続するだけ） |
| 32 | Spring のテスト一式（JUnit、AssertJ、MockMvc） | `MemberControllerTest` など |
| 33 | Karate | `ApiKarateTest`、`members.feature` |

MyBatis と Karate は Spring Boot の管理外なので、版（`4.0.1`、`1.5.1`）を書いています。
PostgreSQL のドライバは `runtimeOnly` です。
コードは JDBC の標準の仕組みで DB を使うので、ドライバのクラスを直接 `import` しません。

### テストタスク（37〜56 行目）

```groovy title="sample-app/build.gradle" linenums="37"
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

- `test` は、タグ `karate` の付いたテストを除外します
- `ApiKarateTest` にはクラスに `@Tag("karate")` が付いています（`ApiKarateTest.java` 14 行目）
- `karateTest` は逆に、タグ `karate` の付いたテストだけを実行します
- `systemProperty 'karate.env', ...` は、Gradle に渡した `-Dkarate.env` をテストの JVM に引き渡します
- `outputs.upToDateWhen { false }` は「前回から変更が無くても毎回実行する」という意味です。起動中のアプリの状態は、Gradle には分からないからです

`test` の後には、`finalizedBy` によりカバレッジのレポートが作られます（58〜63 行目で XML と HTML を出力）。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `build.gradle` 1 ファイル | 複数モジュールなら `settings.gradle` の `include` と、各モジュールの `build.gradle`。Maven なら `pom.xml` |
| `mavenCentral()` | 社内のリポジトリ（ミラー）の設定。`settings.gradle` や `init.gradle` にあることも多い |
| `options.release = 17` | 本番環境の Java の版。設計書・環境定義書と食い違っていないか |
| `excludeTags 'karate'` | テストの種類の分け方（単体・結合・E2E）と、CI でどのタスクを実行しているか |
| `jacocoTestReport` | カバレッジの基準値と、レポートの置き場所 |
| `gradle/wrapper/gradle-wrapper.properties` | Gradle 自体の版（サンプルは 8.14.3） |

実案件では、CI の定義ファイルも一緒に読みます。
`build.gradle` にタスクがあっても、CI が実行していなければ守られていないからです。

## もし build.gradle の版固定や設定がなかったら？

`release = 17` が無いと、手元の JDK 21 で書いたコードが 21 の API を使ってしまいます。
手元ではビルドが通るのに、CI や本番の Java 17 で初めて失敗します。

テストタスクの分け方が無いと、`./gradlew test` が起動中のアプリを必要とします。
アプリを起動していない CI では、毎回 API テストが失敗します。
逆に、単体テストと API テストを区別せずに実行していると、どちらが何を保証しているかが分からなくなります。

## 理解度チェック

**問 1.** `options.release = 17` があると、手元の JDK が 21 のときに何が起きますか。

??? note "答え"
    Java 17 向けにコンパイルされます。
    Java 21 で追加された API を使うと、コンパイルエラーになります（15 行目）。

**問 2.** PostgreSQL のドライバが `runtimeOnly` なのはなぜですか。

??? note "答え"
    サンプルアプリのコードは、ドライバのクラスを直接使わないからです。
    ドライバは実行時に DB へ接続するためだけに必要です（30 行目）。

**問 3.** `./gradlew test` で Karate のテストが動かないのは、どの行のためですか。

??? note "答え"
    `build.gradle` 39〜41 行目の `excludeTags 'karate'` と、
    `ApiKarateTest.java` 14 行目の `@Tag("karate")` の組み合わせのためです。

**問 4.** `spring-boot-starter-web` に版が書かれていないのに、版が決まるのはなぜですか。

??? note "答え"
    `io.spring.dependency-management` プラグイン（7 行目）が、
    Spring Boot の版（6 行目の 4.0.7）に合った版を決めるからです。

## コードを読むときの確認観点

- [ ] Java の版（`release`）と、CI・本番の Java の版が一致しているか
- [ ] 新しく足す依存に、管理外なのに版が無い、または管理内なのに版を書いていないものがないか
- [ ] 依存の構成（`implementation` / `runtimeOnly` / `test*`）が、使い方に合っているか
- [ ] どのテストがどのタスクで実行されるかを説明できるか
- [ ] CI が実行しているタスク（`./gradlew build` など）を確かめたか

## 演習

1. `MemberService` の中で、Java 21 で追加された `List.getFirst()` を使ったとします。
   手元の JDK が 21 のとき、`./gradlew build` はどうなりますか。根拠の行を示して答えなさい。
2. 誰かが `OrderImportService` の中で `org.postgresql` パッケージのクラスを `import` しました。
   `./gradlew build` はどうなりますか。根拠の行を示し、その結果が望ましい理由も説明しなさい。
3. クラウドの開発環境に向けて、次のコマンドで API テストを実行しました。

    ```bash
    ./gradlew karateTest -Dkarate.env=dev -DbaseUrl=https://dev.example.com
    ```

    テストは `https://dev.example.com` に接続できますか。
    `build.gradle` と `sample-app/src/test/resources/karate-config.js` の行を示して説明し、必要なら修正案を書きなさい。
4. `testRuntimeOnly` と `testImplementation` の違いを、33〜34 行目を例に説明しなさい。
5. `./gradlew test` の実行後、カバレッジの HTML レポートが作られるのはなぜですか。
   関係する行をすべて示しなさい。

解答は [30-02 解答](answers/30-02.md) にあります。

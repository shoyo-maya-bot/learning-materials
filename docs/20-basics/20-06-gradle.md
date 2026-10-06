# 20-06 Gradle（ビルドと依存関係）

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - Gradle と Gradle Wrapper（`gradlew`）が何をするかを説明できる
    - `build.gradle` の `plugins` / `dependencies` / タスク定義を読める
    - `implementation` / `runtimeOnly` / `testImplementation` の違いを説明できる
    - `test` と `karateTest` の違いを説明し、使い分けられる

## 何か

Gradle はビルドツールです。ビルドとは、ソースからアプリを動く形にする一連の作業です。

- 依存ライブラリ（Spring Boot、MyBatis など）をダウンロードする
- Java のソースをコンパイルする
- テストを実行する
- 実行できる jar ファイルにまとめる

これらの作業の 1 つ 1 つを **タスク** と呼びます（`compileJava`、`test`、`bootJar` など）。
設定は `build.gradle` に書きます。
公式ドキュメントは [Gradle User Manual](https://docs.gradle.org/current/userguide/userguide.html) と [Spring Boot Gradle Plugin](https://docs.spring.io/spring-boot/gradle-plugin/index.html) です。

### Gradle Wrapper

Gradle Wrapper は、プロジェクトが指定した版の Gradle を自動で取ってきて実行する仕組みです。
`gradlew`（Windows は `gradlew.bat`）がその入口です。
PC に Gradle を入れる必要はなく、全員が同じ版でビルドできます。

## なぜ必要か

ビルドツールがなければ、必要な jar を手で集め、`javac` の長い引数を各自で打つことになります。
人によってライブラリの版が違えば、「自分の PC では動く」問題が起きます。

`build.gradle` に依存関係と手順を書いておけば、誰がどこで実行しても同じ結果になります。
CI（自動ビルドの仕組み）も同じ `build.gradle` を使います。

## どうやるか

### よく使うコマンド

`sample-app` のディレクトリで実行します。

| コマンド | 内容 |
| --- | --- |
| `./gradlew build` | コンパイル、単体テスト、jar 作成までまとめて行う |
| `./gradlew test` | 単体テストだけ実行する |
| `./gradlew bootRun` | アプリを起動する |
| `./gradlew karateTest` | API テスト（Karate）を実行する（アプリを先に起動しておく） |
| `./gradlew dependencies` | 依存ライブラリの一覧（ツリー）を表示する |
| `./gradlew tasks` | 使えるタスクの一覧を表示する |
| `./gradlew clean` | `build` ディレクトリを消す |

Windows では `gradlew.bat test` のように実行します。

### 依存関係の種類

| 書き方 | 使われる場面 |
| --- | --- |
| `implementation` | コンパイルと実行の両方 |
| `runtimeOnly` | 実行時だけ（コードからは直接使わない。JDBC ドライバなど） |
| `testImplementation` | テストのコンパイルと実行 |
| `testRuntimeOnly` | テストの実行時だけ |

### 版を固定する

!!! failure "悪い例"
    ```groovy
    // 例: 版を書かない、または範囲指定にする
    implementation 'org.mybatis.spring.boot:mybatis-spring-boot-starter:+'
    ```
    実行するたびに違う版が入る可能性があり、昨日通ったビルドが今日は失敗します。

!!! success "良い例"
    ```groovy
    // 例: 版を固定する
    implementation 'org.mybatis.spring.boot:mybatis-spring-boot-starter:4.0.1'
    ```

Spring Boot のスターター（`spring-boot-starter-web` など）に版が書かれていないのは、
`io.spring.dependency-management` プラグインが Spring Boot の版に合う版を決めているためです。
「書いていない」のではなく「Spring Boot の版で固定している」と読みます。

### gradle で直接実行しない

!!! failure "悪い例"
    ```bash
    # 例: PC に入っている Gradle を使う（版が人によって違う）
    gradle build
    ```

!!! success "良い例"
    ```bash
    # 例: Wrapper を使う
    ./gradlew build
    ```

## サンプルアプリでは

### プラグインと Java の版

`sample-app/build.gradle`

<!-- src: sample-app/build.gradle @exercise-base -->
```groovy
plugins {
    id 'java'
    id 'jacoco'
    id 'org.springframework.boot' version '4.0.7'
    id 'io.spring.dependency-management' version '1.1.7'
}
```

- `java`: Java のコンパイルやテストのタスクを足す
- `jacoco`: テストのカバレッジ（どの行がテストで実行されたか）を測る
- `org.springframework.boot`: `bootRun` や `bootJar` を足す
- `io.spring.dependency-management`: Spring Boot に合う依存ライブラリの版をそろえる

<!-- src: sample-app/build.gradle @exercise-base -->
```groovy
// 本番・CI は Java 17。ローカルが 21 でも 17 向けにコンパイルする（21 固有の API を使わせない）
tasks.withType(JavaCompile).configureEach {
    options.release = 17
    options.encoding = 'UTF-8'
    options.compilerArgs += ['-parameters']
}
```

`options.release = 17` により、手元の JDK が 21 でも、Java 17 にない API を使うとコンパイルエラーになります。
`-parameters` は、メソッドの引数名をクラスファイルに残す指定です。Spring が引数名を読むときに使います。

### 依存関係

<!-- src: sample-app/build.gradle @exercise-base -->
```groovy
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

- `platform(...bom...)` は BOM（部品表）です。AWS SDK の各ライブラリの版を一括でそろえます。そのため `s3` には版がありません
- PostgreSQL の JDBC ドライバは、コードから直接使わないので `runtimeOnly` です

### test と karateTest

<!-- src: sample-app/build.gradle @exercise-base -->
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

| | `test` | `karateTest` |
| --- | --- | --- |
| 対象 | `karate` タグ **以外** のテスト | `karate` タグ **だけ** |
| 必要なもの | なし（DB 不要） | 起動中のアプリと DB |
| 実行後 | カバレッジレポートを作る | なし |

`karate` タグは、`sample-app/src/test/java/karate/ApiKarateTest.java` の `@Tag("karate")` で付いています。
`outputs.upToDateWhen { false }` は「前回から変更がなくても毎回実行する」指定です。
API テストはアプリの状態に左右されるため、省略させません。

### Wrapper の版

`sample-app/gradle/wrapper/gradle-wrapper.properties`

<!-- src: sample-app/gradle/wrapper/gradle-wrapper.properties @exercise-base -->
```properties
distributionUrl=https\://services.gradle.org/distributions/gradle-8.14.3-bin.zip
```

`./gradlew` を実行すると、この版の Gradle が使われます。
版を上げるときは、このファイルと `gradlew` 一式を一緒に更新し、CI が通ることを確かめます。

## もし〇〇がなかったら？

もし `test` タスクから `karate` タグを除外していなかったら、
`./gradlew build` のたびに API テストも動き、アプリが起動していないため失敗します。
CI も常に失敗し、本当の失敗に誰も気づかなくなります。

もし Wrapper がなければ、各自の PC の Gradle の版でビルドされます。
ある人の環境だけビルドが通らない、CI と手元で結果が違う、といった問題が起き、調査に時間を取られます。

## 理解度チェック

1. `./gradlew test` を実行したとき、`ApiKarateTest` は実行されますか。理由も答えてください。

    ??? note "答え"
        実行されません。
        `ApiKarateTest` には `@Tag("karate")` が付いており、`test` タスクは `excludeTags 'karate'` で除外しているためです。

2. `runtimeOnly 'org.postgresql:postgresql'` が `implementation` でないのはなぜですか。

    ??? note "答え"
        JDBC ドライバはコードから直接使わず、実行時にだけ必要なためです。
        コンパイル時に見えないので、誤って直接使うことも防げます。

3. `spring-boot-starter-web` に版が書かれていないのに、版が決まるのはなぜですか。

    ??? note "答え"
        `io.spring.dependency-management` プラグインが、Spring Boot 4.0.7 に合う版を決めているためです。

4. JDK 21 の PC で、Java 21 にしかない API を使うとどうなりますか。

    ??? note "答え"
        コンパイルエラーになります。`options.release = 17` で Java 17 向けにコンパイルしているためです。

## コードを読むときの確認観点

- [ ] 追加した依存ライブラリの版が固定されているか（`+` や範囲指定になっていないか）
- [ ] 依存の種類（`implementation` / `runtimeOnly` / `testImplementation`）が適切か
- [ ] テスト用のライブラリが `implementation` に入っていないか
- [ ] 外部の環境が要るテストに、タグで区別が付いているか
- [ ] Wrapper の版を変えたとき、`gradle-wrapper.properties` と `gradlew` 一式が更新されているか

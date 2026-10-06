# 20-14 ログ

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - ログレベル（ERROR / WARN / INFO / DEBUG）を使い分けられる
    - SLF4J のプレースホルダ `{}` を使ってログを書ける
    - ログに書いてはいけない情報（個人情報・秘密情報）を説明できる
    - メッセージ ID を先頭に置く理由を説明できる

## 何か

ログとは、アプリが動いた記録をテキストで残すものです。
本番で問題が起きたとき、開発者がアプリの中を直接見ることはできません。
手がかりになるのはログだけ、という場面がほとんどです。

Java では **SLF4J**（ログ出力の共通窓口）を通してログを書きます。
Spring Boot では、裏で Logback が実際の出力を行います。

ログには **レベル** があります。

| レベル | 使う場面 | 例 |
|---|---|---|
| ERROR | 処理を続けられない異常。運用者の対応が要る | バッチの異常終了、DB に接続できない |
| WARN | 処理は続くが、注意が要る | 形式エラーの行を飛ばした、業務エラーを返した |
| INFO | 正常な流れの節目 | バッチの開始・終了と件数 |
| DEBUG | 開発中の調査用。本番では通常出さない | メソッドの入口、途中の値 |
| TRACE | DEBUG より細かい | ほぼ使わない |

設定したレベル以上のログだけが出力されます。
例えば INFO に設定すると、ERROR・WARN・INFO が出て、DEBUG・TRACE は出ません。

## なぜ必要か

- **障害の調査**: いつ・どの処理で・何が起きたかを、後から追えるようにします
- **運用の監視**: ERROR や特定のメッセージ ID を監視ツールで検知し、担当者に知らせます
- **処理の証跡**: バッチが何件を処理したかを、記録として残します

一方で、ログは多くの人や仕組み（監視・集約の基盤）が見ます。
個人情報や秘密情報を書くと、そこから漏えいします。

## どうやるか

### 1. ロガーを用意する

チームの規約では、ロガーの変数名は `log` です。`System.out` と `printStackTrace` は使いません。

例:

```java
private static final Logger log = LoggerFactory.getLogger(ProductService.class);
```

### 2. プレースホルダ `{}` で値を埋め込む

!!! failure "悪い例"
    ```java
    // 例: 文字列連結は、DEBUG が出力されない設定でも連結の処理が走る
    log.debug("商品を検索します code=" + code);
    ```

!!! success "良い例"
    ```java
    // 例: {} はログを実際に出すときだけ値を埋め込む
    log.debug("商品を検索します code={}", code);
    ```

### 3. 例外は最後の引数に渡す

例外オブジェクトを最後の引数に渡すと、スタックトレース（例外が起きた場所の履歴）も出力されます。

!!! failure "悪い例"
    ```java
    // 例: getMessage() だけでは、どこで起きたかが分からない
    log.error("取込に失敗しました: " + e.getMessage());
    ```

!!! success "良い例"
    ```java
    // 例: 例外を最後の引数に渡し、スタックトレースを残す
    log.error("{} 取込に失敗しました", MessageIds.IMPORT_FAILED, e);
    ```

同じ例外を、捕まえるたびにログに出すのも避けます。同じスタックトレースが何度も出て、読みにくくなります。
最終的に処理する場所で 1 回だけ出します。

### 4. メッセージ ID を先頭に置く

チームの規約では、ログの先頭にメッセージ ID を書きます。

- 監視ツールで「`APPW0001` が出たら通知」のように、ID で検知できます
- 運用手順書で「この ID が出たらこう対応する」と書けます
- 文言を変えても、ID が同じなら検知や集計が壊れません

### 5. 書いてはいけないもの

| 書かない | 例 |
|---|---|
| 個人情報 | 氏名、メールアドレス、住所、電話番号、生年月日 |
| 認証情報 | パスワード、アクセストークン、API キー、DB の接続パスワード |
| 決済情報 | カード番号 |
| リクエストやファイルの中身の丸ごと | JSON の本文、CSV の行全体（個人情報が含まれうる） |

調査に必要なら、ID（会員 ID・注文番号）や件数で代わりにします。

!!! failure "悪い例"
    ```java
    // 例: メールアドレスとパスワードをそのまま出している
    log.info("ログイン email={} password={}", email, password);
    ```

!!! success "良い例"
    ```java
    // 例: 個人を直接示さない ID と結果だけを出す
    log.info("{} ログイン成功 memberId={}", MessageIds.LOGIN_SUCCEEDED, memberId);
    ```

### 6. レベルは設定ファイルで切り替える

パッケージごとのレベルは、`application-<プロファイル>.yml` の `logging.level` で変えられます。
コードを変えずに、ローカルだけ DEBUG を出す、といった切り替えができます。

## サンプルアプリでは

### バッチの開始・終了・警告

`sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java` の 43〜59 行目です。

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java @exercise-base -->
```java
List<String> input = args.getOptionValues("input");
if (input == null || input.size() != 1) {
    log.error("{} 引数 --input=<s3://バケット/キー またはファイル> が必要です", MessageIds.INVALID_INPUT);
    exitCode = ERROR;
    return;
}
log.info("{} JOB0001 開始 input={}", MessageIds.IMPORT_STARTED, input.get(0));
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

- 引数が無い: 続けられないので ERROR（`APPE0001`）
- 開始・終了: 正常な節目なので INFO（`APPI0001` / `APPI0002`）。終了には件数を残します
- 形式エラーで飛ばした行: 処理は続くので WARN（`APPW0001`）。中身は「行番号: 理由」で、行の中身そのものは出しません
- 異常終了: ERROR。例外 `e` を最後の引数に渡し、スタックトレースを残しています

!!! note "気付いておきたい点"
    最後の `log.error("JOB0001 異常終了", e)` には、先頭のメッセージ ID がありません。
    `MessageIds` に異常終了用の ID が無いためです。
    規約どおりにするなら、ID を追加し（例: `APPE` + 4 桁）、`messages.properties` にも本文を足します。

メッセージ ID の一覧は `sample-app/src/main/java/com/example/sample/common/MessageIds.java` です。

<!-- src: sample-app/src/main/java/com/example/sample/common/MessageIds.java @exercise-base -->
```java
public static final String INVALID_INPUT = "APPE0001";
public static final String MEMBER_NOT_FOUND = "APPE0002";
public static final String EMAIL_ALREADY_USED = "APPE0003";
public static final String IMPORT_STARTED = "APPI0001";
public static final String IMPORT_FINISHED = "APPI0002";
public static final String IMPORT_LINE_SKIPPED = "APPW0001";
```

`I` は情報、`W` は警告、`E` はエラーです。ID の種別とログレベルがそろっています。

### 業務エラーのログ

`sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java` の 31〜35 行目です。

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java @exercise-base -->
```java
@ExceptionHandler(BusinessException.class)
public ResponseEntity<ErrorResponse> business(BusinessException e) {
    log.warn("business error: {}", e.getMessageId());
    return body(HttpStatus.CONFLICT, e.getMessageId(), e.getArgs(), List.of());
}
```

- 業務エラーは利用者の操作で起きる想定内のものなので、WARN です
- ログに出すのはメッセージ ID だけです。`e.getArgs()` は出していません
- メールアドレス重複（`APPE0003`）の埋め込み値はメールアドレスです。ログに出すと個人情報が残ります

### ローカルだけ DEBUG にする

`sample-app/src/main/resources/application-local.yml` の 8〜10 行目です。

<!-- src: sample-app/src/main/resources/application-local.yml @exercise-base -->
```yaml
logging:
  level:
    com.example.sample: DEBUG
```

`local` プロファイルのときだけ、サンプルアプリのパッケージを DEBUG まで出します。
共通の `application.yml` には書いていないので、他の環境では Spring Boot の既定（INFO）になります。

## もしログの決まりがなかったら？

障害が起きても、どの処理で何が起きたか分からず、原因の特定に何日もかかります。
人によって書き方が違うと、監視ツールで検知する条件も作れません。

反対に、何でもログに出すと、個人情報やパスワードがログ基盤に残ります。
ログは多くの人が見られ、長く保存されるため、そこが漏えいの入口になります。
「必要なことを、決まった形で、安全に」残すための決まりが要ります。

## 理解度チェック

1. CSV の形式エラーの行を飛ばして処理を続けるとき、ログレベルは何にしますか。

    ??? note "答え"
        WARN です。処理は続けられるが注意が要る事象だからです。サンプルアプリでも `APPW0001` を WARN で出しています。

2. `log.debug("件数=" + count)` を `log.debug("件数={}", count)` に直す理由は何ですか。

    ??? note "答え"
        `{}` を使うと、DEBUG が出力されない設定のときに文字列の組み立てを省けるからです。
        書き方もそろい、読みやすくなります。

3. `ApiExceptionHandler.business` が `e.getArgs()` をログに出していないのはなぜですか。

    ??? note "答え"
        埋め込み値に個人情報（メールアドレスなど）が入ることがあるからです。
        メッセージ ID だけで、どの業務エラーかは分かります。

4. ログの先頭にメッセージ ID を置くと、運用で何が楽になりますか。

    ??? note "答え"
        監視ツールで ID を条件に検知・通知でき、運用手順書で ID ごとの対応を決められます。
        文言を変えても検知条件が壊れません。

5. 例外をログに出すとき、`e.getMessage()` だけでなく例外オブジェクトを渡すのはなぜですか。

    ??? note "答え"
        スタックトレースが出力され、例外が起きたクラスと行が分かるからです。

## コードを読むときの確認観点

- [ ] `System.out` や `printStackTrace` ではなく、SLF4J のロガー `log` を使っている
- [ ] ログの先頭にメッセージ ID があり、ID の種別（I / W / E）とレベルが合っている
- [ ] 値の埋め込みに `{}` を使っている
- [ ] 例外は最後の引数に渡し、同じ例外を何度もログに出していない
- [ ] 個人情報・パスワード・トークン・リクエストの本文を出していない
- [ ] バッチの開始・終了と件数が INFO で残る

参考: [SLF4J マニュアル](https://www.slf4j.org/manual.html)、[Spring Boot: Logging](https://docs.spring.io/spring-boot/reference/features/logging.html)

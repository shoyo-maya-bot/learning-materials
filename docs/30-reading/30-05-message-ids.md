# 30-05 メッセージ ID

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - メッセージ ID の形式（`APPE0001` など）と、その読み方を説明できる
    - `MessageIds`・`messages.properties`・`application.yml` の関係を説明できる
    - 埋め込み値 `{0}` が、どこから来て、どう整形されるかを読める
    - メッセージを追加・変更するときに、直すべき場所とテストを挙げられる

## 何か

メッセージ ID は、利用者向けの文言やログの 1 件 1 件に付ける識別子です。
サンプルアプリでは、次の形式です。

```text
APP + 種別（I=情報 / W=警告 / E=エラー）+ 4 桁の連番
例: APPE0002 = エラーの 2 番（会員が見つかりません）
```

メッセージ ID の仕組みは、次の 3 つのファイルでできています。

| ファイル | 役割 |
| --- | --- |
| `MessageIds.java` | ID を定数として並べる（コードから使う名前） |
| `messages.properties` | ID と本文（文言）の対応 |
| `application.yml` | Spring に `messages.properties` の場所と文字コードを教える |

なお、`API0001`（API の ID）や `JOB0001`（ジョブの ID）は、メッセージ ID とは別の体系です。
どちらも設計書とコードを結びつけるための ID です。

## なぜ必要か

メッセージ ID があると、次のことができます。

- 問い合わせで「APPE0003 が出た」と言われれば、原因の場所がすぐ分かる
- ログを ID で検索・集計でき、監視の条件にも使える
- 文言を変えても、ID で判定している呼び出し側やテストは壊れない
- 文言をコードから分けておけるので、言い回しの修正でコードを触らずに済む

## どうやるか

### ID から本文と使用箇所をたどる

メッセージ ID を見かけたら、次の 3 か所を検索します。

```bash
# 例: APPE0002 をたどる
grep -rn "APPE0002" src/main            # 定数の定義と本文
grep -rn "MEMBER_NOT_FOUND" src/main    # 定数を使っている場所
grep -rn "APPE0002" src/test            # テストで確かめている場所
```

### 埋め込み値の整形に注意する

本文の `{0}`、`{1}` には、例外などで渡した値が入ります。
埋め込み値があるとき、Spring は Java 標準の `MessageFormat` で本文を組み立てます。
`MessageFormat` には、次の注意点があります。

- 数値は、桁区切りのカンマ付きで整形される（例: `1234` → `1,234`）
- 単一引用符 `'` は特別な意味を持つ（文字として出すには `''` と 2 つ重ねる）

!!! failure "悪い例"
    ```java
    // 例: ID と文言をコードに直接書く
    throw new BusinessException("APPE0003");
    log.warn("このメールアドレスは既に登録されています");
    ```
    ID の打ち間違いにコンパイラが気づけません。
    文言を変えるたびにコードを探して直すことになります。

!!! success "良い例"
    <!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java#L27-L29 @exercise-base -->
    ```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="27"
            if (mapper.existsByEmail(normalized)) {
                throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
            }
    ```
    ID は定数で書き、文言は `messages.properties` に置きます。
    定数名で意味が分かり、打ち間違いはコンパイルエラーになります。

## サンプルアプリでは

### 定数の一覧

<!-- src: sample-app/src/main/java/com/example/sample/common/MessageIds.java#L3-L18 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/MessageIds.java" linenums="3"
/**
 * メッセージ ID の一覧（本文は messages.properties）.
 *
 * <p>形式: APP + 種別（I=情報 / W=警告 / E=エラー）+ 4 桁。実案件では社内のメッセージ体系に置き換える。
 */
public final class MessageIds {

    public static final String INVALID_INPUT = "APPE0001";
    public static final String MEMBER_NOT_FOUND = "APPE0002";
    public static final String EMAIL_ALREADY_USED = "APPE0003";
    public static final String IMPORT_STARTED = "APPI0001";
    public static final String IMPORT_FINISHED = "APPI0002";
    public static final String IMPORT_LINE_SKIPPED = "APPW0001";

    private MessageIds() {}
}
```

- `final class` と `private` のコンストラクタで、継承もインスタンス化もできないようにしています
- 定数だけを集める「定数クラス」の典型的な書き方です

### 本文

<!-- src: sample-app/src/main/resources/messages.properties @exercise-base -->
```properties title="sample-app/src/main/resources/messages.properties"
APPE0001=入力内容に誤りがあります。
APPE0002=会員が見つかりません（会員ID: {0}）。
APPE0003=このメールアドレスは既に登録されています（{0}）。
APPI0001=処理を開始します。
APPI0002=処理を終了します。
APPW0001=形式に誤りがある行を飛ばしました。
```

### Spring への登録

<!-- src: sample-app/src/main/resources/application.yml#L5-L7 @exercise-base -->
```yaml title="sample-app/src/main/resources/application.yml" linenums="5"
  messages:
    basename: messages
    encoding: UTF-8
```

- `basename: messages` で、クラスパスの `messages.properties` を読みます
- `encoding: UTF-8` で、日本語の本文を正しく読みます

### 使われ方は 2 通り

ID の使われ方は、API とバッチで違います。

| 使う場所 | 行 | 使い方 |
| --- | --- | --- |
| `ApiExceptionHandler.body` | 47 行目 | ID から本文を引き、`ErrorResponse` の `message` にする |
| `OrderImportJob.run` | 45・49・52・53 行目 | ログの先頭に ID を付ける。本文はコードに直接書いている |

<!-- src: sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java#L46-L49 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java" linenums="46"
    private ResponseEntity<ErrorResponse> body(HttpStatus status, String id, Object[] args, List<String> details) {
        String text = messages.getMessage(id, args, id, Locale.JAPANESE);
        return ResponseEntity.status(status).body(new ErrorResponse(id, text, details));
    }
```

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java#L49-L49 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java" linenums="49"
        log.info("{} JOB0001 開始 input={}", MessageIds.IMPORT_STARTED, input.get(0));
```

バッチのログは `messages.properties` の本文を使っていません。
そのため、`APPI0001` の本文「処理を開始します。」を変えても、ログは変わりません。
読むときは「ID がどこで本文に変換されるか」まで確かめます。

また、45 行目では、引数 `--input` が無いときのログに `INVALID_INPUT`（`APPE0001`）を使っています。
API の入力チェックと同じ ID を、バッチの起動引数の誤りにも使っていることになります。

### 埋め込み値の流れ

`APPE0002` の `{0}` に入る値は、次のように流れます。

```text
MemberService.get の id（21 行目）
→ new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id) の args
→ ApiExceptionHandler.notFound の e.getArgs()（28 行目）
→ messages.getMessage(id, args, ...)（47 行目）で {0} に埋め込む
```

`id` は `long` なので、`MessageFormat` では数値として整形されます。
テストでは ID 42 しか確かめていないので、桁区切りの影響はテストに現れません（演習 1）。

### テストでのメッセージ

`MemberControllerTest` は `messages.properties` を読まず、テスト用の本文を自分で登録しています。

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java#L26-L27 @exercise-base -->
```java title="sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java" linenums="26"
        StaticMessageSource messages = new StaticMessageSource();
        messages.addMessage("APPE0002", Locale.JAPANESE, "会員が見つかりません（会員ID: {0}）。");
```

登録しているのは `APPE0002` だけです。
`messages.properties` の本文を変えても、このテストは気づきません。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `APPE0001` の形式 | 社内・案件のメッセージ ID 体系（桁数、種別の文字、業務ごとの接頭辞） |
| `MessageIds.java` | メッセージ定数クラス、または自動生成されたクラス |
| `messages.properties` | メッセージ一覧（設計書）と、そこから作られるファイル。多言語なら `messages_<言語>.properties` |
| `ApiExceptionHandler.body` | ID から本文を引く共通処理 |
| `OrderImportJob` のログ | ログ出力の共通部品、監視で検知する ID の一覧 |

実案件では、設計書のメッセージ一覧とファイルの中身が一致しているかも確かめます。

## もしメッセージ ID がなかったら？

エラーやログは、文言だけで区別することになります。
文言を少し直しただけで、監視の条件や呼び出し側の判定が壊れます。
問い合わせでも「どの画面で、どんな文言が出たか」を細かく聞き取らないと、原因の場所が分かりません。

また、同じ意味のメッセージが、場所ごとに違う言い回しで書かれがちです。
利用者には同じ失敗が違う失敗に見え、混乱を招きます。

## 理解度チェック

**問 1.** `APPW0001` の `W` は何を表しますか。

??? note "答え"
    種別の「警告」です（`MessageIds.java` 6 行目の Javadoc）。

**問 2.** `messages.properties` を Spring が読むための設定は、どのファイルのどこですか。

??? note "答え"
    `application.yml` 5〜7 行目の `spring.messages.basename` と `spring.messages.encoding` です。

**問 3.** `APPI0001` の本文を「取込を開始します。」に変えると、バッチのログは変わりますか。

??? note "答え"
    変わりません。
    `OrderImportJob` はログの先頭に ID を付けるだけで、本文はコードに直接書いているからです（49 行目）。

**問 4.** `MessageFormat` で本文を組み立てるときの注意点を 2 つ挙げてください。

??? note "答え"
    数値が桁区切りのカンマ付きで整形されることと、単一引用符 `'` が特別な意味を持つことです。

## コードを読むときの確認観点

- [ ] 新しい ID が、形式（種別の文字、桁数）と連番の規則に合っているか
- [ ] ID を文字列で直接書かず、定数を使っているか
- [ ] 定数と `messages.properties` の両方に追加されているか（片方だけになっていないか）
- [ ] `{0}` に入る値の型と、整形結果（桁区切りなど）を確かめたか
- [ ] 本文に個人情報が埋め込まれる場合、それがログに出ないか

## 演習

1. 会員 ID 1234 の会員を照会し、存在しなかったとします。
   応答の `message` は、どんな文字列になりますか。行を示して説明しなさい。
   また、「会員ID: 1234」と表示したい場合の修正案と、それを守るテストを書きなさい。
2. `APPE0003` の `{0}` には、何が入りますか。
   `MemberService.register` の引数 `email` に ` Member@Example.COM `（前後に空白）が渡され、既に登録済みだった場合の値を、行を示して答えなさい。
3. 「商品が見つかりません（商品コード: {0}）。」というエラーメッセージを新しく追加します。
   ID を決め、変更するファイルと行、追加すべきテストを挙げなさい。
4. `application.yml` の `basename` を、誤って `message`（末尾の `s` が無い）にしました。
   API のエラー応答の `message` はどうなりますか。
   また、この誤りに気づけるテストは今ありますか。無ければ、どのテストをどう変えるとよいかを書きなさい。
5. `MemberControllerTest` の `StaticMessageSource` には `APPE0001` が登録されていません。
   それでも `invalidInputReturns400` が通るのはなぜですか。行を示して説明しなさい。

解答は [30-05 解答](answers/30-05.md) にあります。

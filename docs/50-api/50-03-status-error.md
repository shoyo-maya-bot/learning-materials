# 50-03 ステータスコードとエラー応答

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 結果ごとに適切な HTTP ステータスコードを選べる
    - エラー応答の形（`ErrorResponse`）とメッセージ ID を統一する理由を説明できる
    - sample-app の `ApiExceptionHandler` が、例外をどのステータスに変換しているかを読める
    - エラー応答に含めてはいけない情報を説明できる

## 何か

**HTTP ステータスコード** は、リクエストの結果を表す 3 桁の数字です。
最初の 1 桁で大まかな種類が分かります。

| 範囲 | 意味 | 主なもの |
| --- | --- | --- |
| 2xx | 成功 | 200 OK、201 Created、204 No Content |
| 4xx | 利用者側の誤り（リクエストを直せば成功しうる） | 400、401、403、404、409、422 |
| 5xx | サーバ側の誤り（利用者には直せない） | 500、503 |

**エラー応答** は、失敗したときに返す本文（JSON）です。
ステータスだけでは「何が悪かったか」が分からないので、本文で詳しく伝えます。

**メッセージ ID** は、メッセージ 1 つ 1 つに付ける番号です（例: `APPE0002`）。
画面の表示・ログ・問い合わせ・設計書のメッセージ表を、同じ番号でつなげます。

## なぜ必要か

利用者（画面や他システム）は、ステータスで処理を分けます。
たとえば 400 なら入力欄に誤りを表示し、503 なら少し待って再試行します。
ステータスがいい加減だと、利用者は正しく振る舞えません。

エラー応答の形が API ごとに違うと、利用者は API ごとに読み方を変える必要があります。
形を 1 つに決めれば、共通の処理で扱えます。

メッセージ ID があると、問い合わせや障害調査が速くなります。
「会員が見つかりません」という文言は変わることがありますが、ID は変わりません。
ログを ID で検索すれば、どこで何が起きたかすぐに分かります。

## どうやるか

### ステータスの選び方

| 結果 | ステータス | 例 |
| --- | --- | --- |
| 照会・更新の成功 | 200 | 会員の照会 |
| 登録の成功 | 201 + `Location` | 会員の登録 |
| 本文なしの成功 | 204 | 削除 |
| 入力の形式誤り | 400 | 必須項目が空、メールアドレスの形式誤り |
| 認証されていない | 401 | トークンが無い・期限切れ（[50-06](50-06-auth.md)） |
| 権限がない | 403 | 他人のデータを更新しようとした |
| 対象が無い | 404 | 存在しない会員 ID |
| 業務上の競合 | 409 | メールアドレスが登録済み |
| 想定外の誤り | 500 | プログラムの不具合、DB の障害 |
| 一時的に使えない | 503 | 保守中、過負荷 |

400 と 409 の違いは「リクエストだけを見て誤りと分かるか」です。
形式の誤りはリクエストだけで分かるので 400 です。
「メールアドレスが登録済み」は DB の状態と照らして初めて分かるので、409 にします。
業務ルール違反に 422 を使うチームもあります。どれを使うかは規約で決めます。

!!! failure "悪い例"
    ```json
    HTTP/1.1 200 OK
    {"result": "NG", "error": "member not found"}
    ```
    失敗なのに 200 を返しています。利用者は本文を読むまで失敗に気付けません。

!!! success "良い例"
    ```json
    HTTP/1.1 404 Not Found
    {"messageId": "APPE0002", "message": "会員が見つかりません（会員ID: 42）。", "details": []}
    ```

### エラー応答に入れてはいけないもの

- スタックトレース、例外クラス名、SQL 文
- DB のテーブル名・列名、サーバのファイルパス
- 他人の個人情報

これらは攻撃の手がかりになります。
詳しい情報はログにだけ出し、応答にはメッセージ ID と利用者向けの文言だけを返します。

### 例外を 1 か所で変換する

Spring では `@RestControllerAdvice` を付けたクラスで、例外を応答に変換できます。
Controller や Service は例外を投げるだけにし、ステータスの決定は 1 か所に集めます。

!!! failure "悪い例"
    ```java
    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable("id") long id) {
        try {
            return ResponseEntity.ok(service.get(id));
        } catch (NotFoundException e) {
            return ResponseEntity.status(404).body(Map.of("error", "not found")); // API ごとに形が違ってしまう
        }
    }
    ```

!!! success "良い例"
    ```java
    @GetMapping("/{id}")
    public Member get(@PathVariable("id") long id) {
        return service.get(id); // 例外は ApiExceptionHandler が ErrorResponse に変換する
    }
    ```

## サンプルアプリでは

エラー応答の形は `sample-app/src/main/java/com/example/sample/common/ErrorResponse.java` です。

```java
public record ErrorResponse(String messageId, String message, List<String> details) {}
```

| 項目 | 内容 |
| --- | --- |
| `messageId` | メッセージ ID（例: APPE0001） |
| `message` | 利用者向けメッセージ |
| `details` | 入力チェックの項目別エラー（無ければ空） |

例外とステータスの対応は `sample-app/src/main/java/com/example/sample/common/ApiExceptionHandler.java` にあります。

```java
@ExceptionHandler(NotFoundException.class)
public ResponseEntity<ErrorResponse> notFound(NotFoundException e) {
    return body(HttpStatus.NOT_FOUND, e.getMessageId(), e.getArgs(), List.of());
}

@ExceptionHandler(BusinessException.class)
public ResponseEntity<ErrorResponse> business(BusinessException e) {
    log.warn("business error: {}", e.getMessageId());
    return body(HttpStatus.CONFLICT, e.getMessageId(), e.getArgs(), List.of());
}

@ExceptionHandler(MethodArgumentNotValidException.class)
public ResponseEntity<ErrorResponse> invalid(MethodArgumentNotValidException e) {
```

| 例外 | ステータス | メッセージ ID の出どころ |
| --- | --- | --- |
| `NotFoundException` | 404 | 例外が持つ ID（例: APPE0002） |
| `BusinessException` | 409 | 例外が持つ ID（例: APPE0003） |
| `MethodArgumentNotValidException`（入力チェック） | 400 | 固定で `MessageIds.INVALID_INPUT`（APPE0001） |

`NotFoundException` は `BusinessException` を継承しています。
Spring は、投げられた例外に最も近い型のハンドラを選ぶので、`NotFoundException` は 404 になります。

文言は `body` メソッドで、メッセージ ID をキーに `messages.properties` から引いています。

```java
String text = messages.getMessage(id, args, id, Locale.JAPANESE);
```

`sample-app/src/main/resources/messages.properties` の該当行です。

```properties
APPE0001=入力内容に誤りがあります。
APPE0002=会員が見つかりません（会員ID: {0}）。
APPE0003=このメールアドレスは既に登録されています（{0}）。
```

ID の一覧は `sample-app/src/main/java/com/example/sample/common/MessageIds.java` にあり、
形式は「APP + 種別（I=情報 / W=警告 / E=エラー）+ 4 桁」です。
詳しくは [30-04 エラー応答](../30-reading/30-04-error-response.md) と [30-05 メッセージ ID](../30-reading/30-05-message-ids.md) で読みます。

### ハンドラが無い例外

`ApiExceptionHandler` が扱うのは、上の 3 種類だけです。
それ以外の例外は、Spring Boot の既定のエラー処理に任されます。
たとえば次のものは、`ErrorResponse` の形にはなりません。

- `/api/v1/members/abc`（数値に変換できない）: 400 だが、本文は Spring Boot の既定の形
- DB の障害などの想定外の例外: 500 で、本文は Spring Boot の既定の形

すべてのエラーを同じ形にそろえるなら、残りの例外のハンドラを足します。
次のコードは sample-app には無い「例:」です。`APPE9999` も架空の ID です。

例:

```java
@ExceptionHandler(Exception.class)
public ResponseEntity<ErrorResponse> unexpected(Exception e) {
    log.error("unexpected error", e); // 詳細はログにだけ出す
    return body(HttpStatus.INTERNAL_SERVER_ERROR, "APPE9999", new Object[0], List.of());
}
```

足すときは、`messages.properties` と `MessageIds`、設計書のメッセージ表も同時に更新します。

## もしエラー応答の統一がなかったら？

API ごとにエラーの形が違うと、画面側は API ごとに読み取り処理を書くことになります。
ある API では `error`、別の API では `errorMessage` を読む、といった分岐が増えていきます。
一部の API だけ形が違う状態は、テストでも見落とされがちです。

メッセージ ID が無いと、問い合わせの「エラーが出た」から原因にたどり着くのが難しくなります。
文言で検索しても、埋め込み値（会員 ID など）のせいで一致しません。
ID があれば、画面・ログ・設計書を 1 つの番号で結び付けられます。

## 理解度チェック

1. 「メールアドレスが登録済み」のエラーに、400 ではなく 409 を使うのはなぜですか。

    ??? note "答え"
        リクエストの形式は正しく、DB の状態と照らして初めて誤りと分かるからです。
        400 はリクエストだけを見て誤りと分かる場合に使います。

2. sample-app で、存在しない会員を照会したときの応答のステータスと `messageId` を答えてください。

    ??? note "答え"
        ステータスは 404、`messageId` は `APPE0002` です。
        `MemberService.get` が `NotFoundException` を投げ、`ApiExceptionHandler.notFound` が変換します。

3. `NotFoundException` は `BusinessException` の子クラスです。なぜ 409 ではなく 404 になるのですか。

    ??? note "答え"
        Spring は、投げられた例外の型に最も近いハンドラを選ぶからです。
        `NotFoundException` 専用のハンドラ（`notFound`）があるので、そちらが使われます。

4. エラー応答にスタックトレースを含めてはいけない理由を説明してください。

    ??? note "答え"
        クラス名・ライブラリ・SQL などの内部情報が漏れ、攻撃の手がかりになるからです。
        詳細はログにだけ出し、応答にはメッセージ ID と利用者向けの文言だけを返します。

5. sample-app で DB が停止しているときに会員を照会すると、応答は `ErrorResponse` の形になりますか。

    ??? note "答え"
        なりません。
        `ApiExceptionHandler` に想定外の例外のハンドラが無いため、Spring Boot の既定のエラー処理で 500 が返ります。

## コードを読むときの確認観点

- [ ] 失敗なのに 200 を返していないか
- [ ] 400（形式の誤り）と 409（業務上の競合）を使い分けているか
- [ ] Controller の中で例外を捕まえて、個別にエラー応答を作っていないか
- [ ] 新しいメッセージ ID が `MessageIds`・`messages.properties`・設計書のメッセージ表にそろっているか
- [ ] エラー応答にスタックトレースや SQL などの内部情報が含まれていないか
- [ ] 例外ハンドラで扱わない例外が、どんな応答になるか確かめたか

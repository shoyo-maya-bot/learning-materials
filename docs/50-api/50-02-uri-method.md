# 50-02 URI と HTTP メソッド

!!! abstract "到達目標"
    - URI の付け方の決まり（名詞・複数形・階層・クエリ）に沿って URI を設計できる
    - `GET` / `POST` / `PUT` / `PATCH` / `DELETE` の意味を説明できる
    - 「安全」と「冪等」の違いを説明し、再送してよい操作を見分けられる

## 何か

**URI** は、リソースに付ける名前です。
`/api/v1/members/1` は「会員の集まりの中の、ID が 1 の会員」を指します。

**HTTP メソッド** は、そのリソースに対する操作の種類です。
同じ URI でも、メソッドが違えば操作が違います。

| メソッド | 意味 | 安全 | 冪等 | 成功時の主なステータス |
| --- | --- | --- | --- | --- |
| `GET` | 取得する | ○ | ○ | 200 |
| `POST` | 新しく作る（集まりに追加する） | × | × | 201（`Location` 付き） |
| `PUT` | 丸ごと置き換える | × | ○ | 200 または 204 |
| `PATCH` | 一部を変更する | × | 作り方による | 200 または 204 |
| `DELETE` | 削除する | × | ○ | 204 |

- **安全**: サーバのデータを変えない、という意味です
- **冪等**: 同じリクエストを何回送っても、結果が 1 回送ったときと同じ、という意味です

## なぜ必要か

メソッドの意味がそろっていると、利用者や途中の仕組みが「再送してよいか」を判断できます。
通信が切れて応答が分からないとき、`GET` や `PUT` は安心して再送できます。
`POST` を再送すると、二重登録になるおそれがあります。

URI の付け方がそろっていると、利用者が推測で正しく使えます。
`/api/v1/members/{id}` があれば、`/api/v1/orders/{orderNo}` もあるだろう、と分かります。

## どうやるか

### URI の決まり

| 決まり | 良い例 | 悪い例 |
| --- | --- | --- |
| 名詞を使う | `/members` | `/getMembers` |
| 集まりは複数形 | `/members/1` | `/member/1` |
| 単語の区切りはハイフン、小文字 | `/order-imports` | `/orderImports`、`/Order_Imports` |
| 親子関係は階層で | `/members/1/orders` | `/orders-of-member?id=1` |
| 絞り込み・並び順はクエリで | `/members?name=山田` | `/members/name/山田` |
| 版を先頭付近に | `/api/v1/members` | `/api/members-v1` |

ID のような「どれか 1 つを指すもの」はパスに、条件のような「省略できるもの」はクエリに置きます。

### メソッドの選び方

!!! failure "悪い例"
    ```text
    GET  /api/v1/members/1/delete      ← GET でデータを消す（安全でない GET）
    POST /api/v1/members/1             ← 更新なのに POST。何をするか分からない
    ```
    `GET` でデータを変えると、検索エンジンの巡回やブラウザの先読みで消されることがあります。

!!! success "良い例"
    ```text
    DELETE /api/v1/members/1
    PUT    /api/v1/members/1           {"name": "山田", "email": "..."}
    PATCH  /api/v1/members/1           {"name": "山田"}
    ```

`PUT` と `PATCH` の違いは、送らなかった項目の扱いです。
`PUT` は丸ごと置き換えるので、送らなかった項目は消える（または既定値になる）のが本来の意味です。
`PATCH` は送った項目だけを変えます。
チームの API でどちらを使うかを決め、設計書に書いておきます。

### POST の二重登録を防ぐ

`POST` は冪等ではありません。
通信が切れて利用者が再送すると、同じ会員が 2 回登録されるおそれがあります。
防ぐ方法は次のとおりです。

- 業務上一意な項目に一意制約を付ける（会員のメールアドレス、注文番号など）
- 利用者に **冪等キー**（リクエストごとの一意な値）をヘッダで送ってもらい、同じキーの 2 回目は前の結果を返す

例:

```text
POST /api/v1/orders
Idempotency-Key: 6f1c2b0e-...
{"memberId": 1, "productCode": "P001", "quantity": 2}
```

どの方法で防ぐかは、設計書のレビュー観点（office-review の `API-004`「更新系 API の再送時の動きが決まっている」）でも確かめます。

### パスの値の型

パスの値は文字列として届きます。
Spring は `@PathVariable` の型（`long` など）に変換し、変換できなければ 400 にします。
ただし、そのときの応答の形は、自分で決めたエラー応答の形とは限りません（[50-03](50-03-status-error.md) で扱います）。

## サンプルアプリでは

`sample-app/src/main/java/com/example/sample/member/MemberController.java` の URI とメソッドを確認します。

```java
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {
    // ...
    @GetMapping("/{id}")
    public Member get(@PathVariable("id") long id) {
        return service.get(id);
    }

    @PostMapping
    public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
```

| API ID | メソッド | URI | 安全 | 冪等 |
| --- | --- | --- | --- | --- |
| API0001 | `GET` | `/api/v1/members/{id}` | ○ | ○ |
| API0002 | `POST` | `/api/v1/members` | × | × |

- 会員 ID は「1 人を指すもの」なのでパスに置いています
- `@PathVariable("id") long id` なので、`/api/v1/members/abc` は数値に変換できず 400 になります

登録（`POST`）は冪等ではありません。
sample-app では、メールアドレスの重複を確かめることで二重登録を防いでいます。
`sample-app/src/main/java/com/example/sample/member/MemberService.java` の `register` です。

```java
String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
if (mapper.existsByEmail(normalized)) {
    throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
}
```

DB にも一意制約があります（`dev-environment` の `local/db/init/01_schema.sql`）。

```sql
email      VARCHAR(254) NOT NULL UNIQUE,
```

同じ内容の登録を再送すると、2 回目は 409（メールアドレス登録済み）になり、会員は 1 人のままです。
再送しても「会員が 2 人になる」ことはありません。
ただし応答は 201 と 409 で変わるので、厳密な意味の冪等ではありません。
利用者には「409 が返ったら、既に登録済み」と設計書で伝える必要があります。

## もし HTTP メソッドの決まりがなかったら？

`GET` でデータを変える API を作ると、思わぬところで変更が起きます。
ブラウザの先読み、監視ツールの死活確認、ログからの再実行などは、`GET` を安全とみなして気軽に送ります。
その結果、誰も操作していないのにデータが消える、という調査の難しい障害になります。

`POST` の再送への備えが無いと、通信が不安定なときに二重登録が起きます。
特に注文や支払いのような API では、利用者に直接の損害が出ます。

## 理解度チェック

1. 「安全」と「冪等」の違いを、`DELETE` を例に説明してください。

    ??? note "答え"
        `DELETE` はデータを消すので安全ではありません。
        しかし、同じ `DELETE` を 2 回送っても「消えている」という結果は同じなので、冪等です。

2. 会員を名前で検索する API の URI として、`/api/v1/members/name/山田` と `/api/v1/members?name=山田` のどちらが適切ですか。

    ??? note "答え"
        `/api/v1/members?name=山田` です。
        名前は省略できる絞り込み条件なので、クエリに置きます。

3. sample-app の会員登録を同じ内容で 2 回送ると、どうなりますか。

    ??? note "答え"
        1 回目は 201 で登録されます。
        2 回目は `existsByEmail` で重複が見つかり、`BusinessException`（APPE0003）で 409 になります。
        会員は 1 人のままです。

4. `PUT` で一部の項目だけを送ったとき、本来の意味では送らなかった項目はどうなりますか。

    ??? note "答え"
        `PUT` は丸ごと置き換える操作なので、送らなかった項目は消える（または既定値になる）のが本来の意味です。
        一部だけ変えたいときは `PATCH` を使います。

## コードを読むときの確認観点

- [ ] URI が名詞の複数形で、動詞や大文字が入っていないか
- [ ] ID はパスに、省略できる条件はクエリに置いているか
- [ ] `GET` の処理の中でデータを変えていないか
- [ ] `POST` の再送で二重登録にならない仕組み（一意制約・冪等キー）があるか
- [ ] `PUT` と `PATCH` の使い分けがチームの規約と合っているか

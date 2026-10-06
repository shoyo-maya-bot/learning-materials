# 50-01 REST の原則

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](../30-reading/index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - REST の「リソース」「表現」「ステートレス」を、会員 API を例に説明できる
    - 動詞中心の API と、リソース中心の API の違いを説明できる
    - sample-app の会員 API が REST の原則にどう沿っているかを読める

## 何か

**REST**（Representational State Transfer）は、Web の仕組みに沿って API を設計するための考え方です。
HTTP の機能をそのまま活かすので、多くのツールや利用者にとって分かりやすい API になります。

REST の中心にある考え方は次の 4 つです。

| 考え方 | 意味 | 会員 API での例 |
| --- | --- | --- |
| リソース | API で扱う「もの」。URI で名前を付ける | 会員 `/api/v1/members/1` |
| 表現 | リソースの状態を表すデータ。多くは JSON | `{"id":1,"name":"山田","email":"..."}` |
| 統一インタフェース | 操作は HTTP メソッドで表す | 照会は `GET`、登録は `POST` |
| ステートレス | サーバは前のリクエストを覚えていない。毎回必要な情報を送る | 照会のたびに会員 ID を URI に含める |

**リソース** は名詞です。
「会員」「注文」「商品」のように、業務で扱うものを指します。
**操作** は HTTP メソッドという動詞で表します。
URI に動詞を入れないのが、REST の分かりやすさの源です。

## なぜ必要か

API の作り方がばらばらだと、利用者は API ごとに使い方を覚え直すことになります。
REST の原則にそろえると、URI とメソッドを見ただけで何をするか分かります。

また、HTTP の仕組みをそのまま使えます。

- `GET` は安全な操作なので、キャッシュや再送がしやすい
- ステータスコードで成功・失敗の種類を表せる
- ステートレスなので、同じ API のサーバを何台に増やしても動く

最後の点は、クラウドで特に重要です。
sample-app の API は ECS 上で複数台に増やせます（本番は 2 台）。
前のリクエストを特定のサーバが覚えている設計だと、別のサーバに届いたリクエストが失敗します。

## どうやるか

### リソースを先に決める

API を設計するときは、まず「何を扱うか」を名詞で書き出します。
次に、それぞれに対する操作を HTTP メソッドに割り当てます。

| リソース | URI | 操作 |
| --- | --- | --- |
| 会員の集まり | `/api/v1/members` | `GET` 一覧、`POST` 登録 |
| 1 人の会員 | `/api/v1/members/{id}` | `GET` 照会、`PUT` 更新、`DELETE` 削除 |
| 会員の注文 | `/api/v1/members/{id}/orders` | `GET` その会員の注文一覧 |

!!! failure "悪い例"
    ```text
    POST /api/getMember          {"id": 1}
    POST /api/registerMember     {"name": "山田", ...}
    POST /api/deleteMember       {"id": 1}
    ```
    操作ごとに URI があり、すべて `POST` です。
    URI を見ないと何をするか分からず、照会も再送しにくくなります。

!!! success "良い例"
    ```text
    GET    /api/v1/members/1
    POST   /api/v1/members           {"name": "山田", ...}
    DELETE /api/v1/members/1
    ```
    同じリソースに対して、メソッドで操作を変えています。

### 表現は JSON で、項目名をそろえる

応答の JSON は、リソースの「表現」です。
同じリソースは、どの API で返しても同じ形にします。
項目名の書き方（`memberId` か `member_id` か）もチームで 1 つに決めます。

### ステートレスにする

サーバのメモリに「さっき照会した会員」を覚えておく設計にはしません。
リクエストごとに、必要な情報（リソースの ID、認証情報など）を送ってもらいます。

!!! failure "悪い例"
    ```text
    GET /api/v1/members/1          ← サーバが「今の会員は 1」と覚える
    GET /api/v1/current-member/orders  ← 覚えた会員の注文を返す
    ```

!!! success "良い例"
    ```text
    GET /api/v1/members/1
    GET /api/v1/members/1/orders   ← 毎回 ID を含める
    ```

### REST にこだわりすぎない

業務の操作には、名詞にしにくいものもあります（例: 注文の「確定」）。
その場合は、次のどちらかで表します。

- 状態の変更として表す: `PATCH /api/v1/orders/{orderNo}` に `{"status":"CONFIRMED"}`
- 操作をリソースとみなす: `POST /api/v1/orders/{orderNo}/confirmation`

どちらを選ぶかはチームの規約で決め、API ごとにばらつかせないことが大切です。

## サンプルアプリでは

会員 API は `sample-app/src/main/java/com/example/sample/member/MemberController.java` です。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java @exercise-base -->
```java
/** 会員 API（API ID: API0001 照会 / API0002 登録）. */
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {
```

- `@RequestMapping("/api/v1/members")`: リソース「会員の集まり」の URI です。名詞の複数形で、版 `v1` を含みます
- Javadoc の API ID（API0001・API0002）は、設計書の API 一覧と対応させるための番号です

照会と登録は、同じリソースにメソッドで操作を割り当てています。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java @exercise-base -->
```java
@GetMapping("/{id}")
public Member get(@PathVariable("id") long id) {
    return service.get(id);
}

@PostMapping
public ResponseEntity<Member> register(@Valid @RequestBody RegisterRequest req) {
    Member created = service.register(req.name(), req.email());
    return ResponseEntity.created(URI.create("/api/v1/members/" + created.id())).body(created);
}
```

- 照会は `GET /api/v1/members/{id}` で、会員 1 人の表現（`Member`）を返します
- 登録は `POST /api/v1/members` で、作ったリソースの URI を `Location` ヘッダに入れて返します
- どちらも、サーバに前のリクエストの情報を残していません（ステートレス）

返す表現は `sample-app/src/main/java/com/example/sample/member/Member.java` の record です。

<!-- src: sample-app/src/main/java/com/example/sample/member/Member.java @exercise-base -->
```java
public record Member(Long id, String name, String email) {}
```

照会でも登録でも、同じ `Member` の形で返しています。
同じリソースは同じ表現で返す、という原則どおりです。

## もし REST の原則がなかったら？

API ごとに URI の付け方やメソッドの使い方が違うと、利用者は毎回仕様書を細かく読む必要があります。
照会まで `POST` で作ると、ブラウザやプロキシのキャッシュが効かず、再送してよいかも判断できません。

サーバが前のリクエストを覚える設計だと、台数を増やしたときに動かなくなります。
ECS のタスクが入れ替わると、覚えていた情報も消えます。
クラウドでの運用を前提にするなら、ステートレスは必須の条件です。

## 理解度チェック

1. `POST /api/getMember` という API の問題点を 2 つ挙げてください。

    ??? note "答え"
        URI に動詞（get）が入っていて、リソースが何か分かりにくい点です。
        また、照会なのに `POST` を使っているため、安全な操作として扱えず、キャッシュや再送の判断ができません。

2. 「ステートレス」とはどういう意味ですか。sample-app の API が複数台で動ける理由と合わせて説明してください。

    ??? note "答え"
        サーバが前のリクエストの情報を覚えず、毎回必要な情報を受け取る、という意味です。
        sample-app の API は会員 ID を毎回 URI で受け取り、状態は DB にだけ置いています。
        そのため、どのサーバにリクエストが届いても同じ結果になります。

3. 会員登録 API が `Location` ヘッダに入れているのは何ですか。

    ??? note "答え"
        登録した会員の URI（`/api/v1/members/{採番された ID}`）です。
        利用者はこの URI で、作られたリソースを照会できます。

4. 注文の「確定」のように名詞にしにくい操作は、どう表せばよいですか。

    ??? note "答え"
        状態の変更として `PATCH` で表すか、操作をリソースとみなして `POST .../confirmation` のように表します。
        どちらにするかはチームの規約で決め、API ごとにばらつかせません。

## コードを読むときの確認観点

- [ ] URI が名詞（リソース）になっていて、動詞が入っていないか
- [ ] 操作が HTTP メソッドで表され、照会に `POST` を使っていないか
- [ ] 同じリソースを、API によって違う形の JSON で返していないか
- [ ] サーバのメモリに、リクエストをまたぐ状態を持っていないか
- [ ] Controller の Javadoc などで、設計書の API ID と対応が取れるか

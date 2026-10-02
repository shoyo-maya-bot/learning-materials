# 50-04 OpenAPI

!!! abstract "到達目標"
    - OpenAPI が何のためにあるかを説明できる
    - パス・パラメータ・リクエスト・応答・エラー応答を OpenAPI で書ける
    - `x-api-id` で設計書の API ID と OpenAPI の operation を対応付けられる
    - design-diff の `spec` コマンドで、設計書と OpenAPI のずれを確かめる流れを説明できる

## 何か

**OpenAPI** は、REST API の仕様を YAML（または JSON）で書くための標準の形式です。
どんなパスがあり、何を送り、何が返るかを、機械が読める形で表します。
以前は Swagger と呼ばれていました。

OpenAPI で書いた仕様からは、次のようなことができます。

- 仕様書の画面を作る（Swagger UI など）
- 利用者側のクライアントコードを生成する
- 実装やテストが仕様どおりかを確かめる
- 設計書（Excel など）と突き合わせる

**`x-api-id`** は、OpenAPI に独自の情報を足す拡張項目（`x-` で始まる項目）の 1 つです。
この教材では、設計書の API ID（例: `API0001`）を operation（パスとメソッドの組）に付けるために使います。

## なぜ必要か

API 仕様が設計書（文章や Excel）にしか無いと、実装との違いに気付くのは人の目だけです。
OpenAPI にしておくと、ツールで差分を取ったり、テストで確かめたりできます。

一方で、設計書と OpenAPI の 2 つを持つと、両者がずれる危険があります。
「設計書では桁が 50、OpenAPI では 60」のようなずれは、実装者がどちらを信じるかで動きが変わります。
そのため、両者を **機械で突き合わせる** 仕組みが要ります。
これがチームで使う design-diff の `spec` コマンドの役割です。

## どうやるか

### 最小の OpenAPI

会員照会（API0001）を OpenAPI で書くと、次のようになります。
sample-app には OpenAPI のファイルが無いので、これは「例:」です。

例:

```yaml
openapi: 3.0.3
info:
  title: 会員 API
  version: 1.0.0
paths:
  /api/v1/members/{id}:
    get:
      operationId: getMember
      x-api-id: API0001
      summary: 会員照会
      parameters:
        - name: id
          in: path
          required: true
          description: 会員 ID
          schema: {type: integer, format: int64, example: 1}
      responses:
        "200":
          description: 照会できた
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Member"}
        "404":
          description: 会員が見つからない（APPE0002）
          content:
            application/json:
              schema: {$ref: "#/components/schemas/ErrorResponse"}
components:
  schemas:
    Member:
      type: object
      required: [id, name, email]
      properties:
        id: {type: integer, format: int64, description: 会員 ID, example: 1}
        name: {type: string, maxLength: 50, description: 氏名, example: 山田 太郎}
        email: {type: string, format: email, maxLength: 254, description: メールアドレス, example: yamada@example.com}
    ErrorResponse:
      type: object
      required: [messageId, message, details]
      properties:
        messageId: {type: string, description: メッセージ ID, example: APPE0002}
        message: {type: string, description: 利用者向けメッセージ}
        details: {type: array, items: {type: string}, description: 項目別のエラー}
```

### 書くときの注意

!!! failure "悪い例"
    ```yaml
    responses:
      "200":
        description: OK
    ```
    成功しか書いていません。利用者は、どんな失敗がありうるか分かりません。

!!! success "良い例"
    ```yaml
    responses:
      "200": {description: 照会できた, content: {application/json: {schema: {$ref: "#/components/schemas/Member"}}}}
      "400": {description: 会員 ID の形式誤り（APPE0001）, content: {application/json: {schema: {$ref: "#/components/schemas/ErrorResponse"}}}}
      "404": {description: 会員が見つからない（APPE0002）, content: {application/json: {schema: {$ref: "#/components/schemas/ErrorResponse"}}}}
    ```
    設計書のエラー表にあるステータスを、すべて `responses` に書いています。

- 必須（`required`）・型（`type`）・桁（`maxLength`）は、設計書の入力項目表・出力項目表と一致させる
- 項目ごとに `description`（日本語）と `example` を書く
- エラー応答は共通の `ErrorResponse` を `$ref` で参照し、形を 1 つにする
- `x-api-id` を全 operation に付け、設計書の API ID と 1 対 1 にする

これらは、設計書レビューの観点（office-review の `config/checks.yaml`）にも入っています。

| 観点 ID | 内容 |
| --- | --- |
| OAS-001 | OAS と API 設計書の項目・必須・型・桁が一致している（design-diff の差分レポートで差異が 0、または差異ごとに理由がある） |
| OAS-002 | 全てのエラー応答（4xx / 5xx）が responses に定義されている |
| OAS-003 | description と example が全項目にある |

### 設計書と OpenAPI を突き合わせる（design-diff spec）

チームの design-diff には、API 定義書（Excel）と OpenAPI を比べる `spec` コマンドがあります。

```bash
design-diff spec --excel samples/spec/API定義書.xlsx --oas samples/spec/openapi.yaml
```

OpenAPI 側は、operation の `x-api-id`（無ければ `operationId`）を API ID として、設計書のシートと対応付けます。
`x-api-id` が無いと、`operationId` の名前（例: `getMember`）が設計書の ID と合わず、対応付けに失敗します。
差分は Markdown で出るので、そのままレビューに貼れます。

CI で使うときは `--fail-on-diff` を付けると、差分があれば終了コード 1 になります。
詳しい使い方は design-diff の README を参照してください。

### 設計を先に書くか、コードから作るか

OpenAPI の作り方には 2 通りあります。

| 方式 | 流れ | 向いている場面 |
| --- | --- | --- |
| 設計先行 | OpenAPI を先に書き、レビューしてから実装する | 利用者（画面・他システム）と先に合意したいとき |
| コード先行 | Controller から OpenAPI を生成する（springdoc-openapi など） | 仕様と実装のずれを無くしたいとき |

どちらでも、設計書との突き合わせは必要です。
コード先行でライブラリを使う場合は、Spring Boot の版に対応した版を選んでください。

## サンプルアプリでは

sample-app には OpenAPI のファイルも、生成するライブラリもありません。
`sample-app/build.gradle` の依存関係にも含まれていません。

API ID は、Controller の Javadoc に書かれています。
`sample-app/src/main/java/com/example/sample/member/MemberController.java` です。

```java
/** 会員 API（API ID: API0001 照会 / API0002 登録）. */
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {
```

OpenAPI を書くなら、この API ID を `x-api-id` に入れます。

| API ID | operation | `x-api-id` |
| --- | --- | --- |
| API0001 | `GET /api/v1/members/{id}` | `API0001` |
| API0002 | `POST /api/v1/members` | `API0002` |

桁や必須は、実装の入力チェックと一致させます。
登録の入力は `MemberController` の `RegisterRequest` です。

```java
public record RegisterRequest(
        @NotBlank @Size(max = 50) String name, @NotBlank @Email @Size(max = 254) String email) {}
```

OpenAPI では `name` を `required`・`maxLength: 50`、`email` を `required`・`format: email`・`maxLength: 254` と書きます。
DB の列定義（`local/db/init/01_schema.sql` の `VARCHAR(50)`・`VARCHAR(254)`）とも同じ桁です。
設計書・OpenAPI・実装・DB の 4 か所で、同じ数字がそろっていることを確かめてください。

## もし OpenAPI と整合チェックがなかったら？

API 仕様が設計書にしか無いと、利用者側の開発者は設計書を読んで手でコードを書きます。
読み違いがあっても、結合テストまで気付きません。
設計書が改訂されても、どこが変わったかを人が探すことになります。

OpenAPI があっても、設計書と突き合わせなければ、ずれは残ります。
「設計書では必須、OpenAPI では任意」のようなずれは、実装者とテスト担当が別の資料を見たときに不具合になります。
機械で突き合わせることで、こうしたずれをレビューの前に見つけられます。

## 理解度チェック

1. OpenAPI の `x-api-id` は何のために付けますか。

    ??? note "答え"
        設計書の API ID と OpenAPI の operation を対応付けるためです。
        design-diff の `spec` コマンドは、`x-api-id`（無ければ `operationId`）で設計書のシートと対応付けます。

2. OpenAPI の `responses` に 200 だけを書くと、どの観点の指摘を受けますか。

    ??? note "答え"
        OAS-002「全てのエラー応答（4xx / 5xx）が responses に定義されている」です。
        設計書のエラー表にあるステータスを、すべて書く必要があります。

3. sample-app の会員登録の `name` を OpenAPI で書くとき、`maxLength` はいくつにしますか。根拠も答えてください。

    ??? note "答え"
        50 です。
        `RegisterRequest` の `@Size(max = 50)` と、DB の `name VARCHAR(50)` が根拠です。

4. 設計先行とコード先行の方式の違いを説明してください。

    ??? note "答え"
        設計先行は、OpenAPI を先に書いてレビューし、それに合わせて実装します。
        コード先行は、Controller から OpenAPI を生成します。
        どちらでも、設計書との突き合わせは必要です。

## コードを読むときの確認観点

- [ ] すべての operation に `x-api-id` があり、設計書の API ID と 1 対 1 か
- [ ] 必須・型・桁が、設計書・入力チェックのアノテーション・DB の列定義と一致しているか
- [ ] 設計書のエラー表のステータスが、すべて `responses` にあるか
- [ ] エラー応答が共通の `ErrorResponse` を参照しているか
- [ ] 項目に `description` と `example` があるか
- [ ] design-diff の `spec` の差分が 0、または差分ごとに理由が書かれているか

# 30-01 コードの読み方の型

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 初めてのコードを「入口 → 流れ → データ → エラー → テスト」の順で読める
    - 読んだ結果を、ファイル名と行番号つきの短いメモにまとめられる
    - テストを「動く仕様書」として読み、自分の理解をテストで確かめられる
    - Copilot にコードを説明させ、その説明をコードとテストで検証できる

## 何か

コードの読み方の型とは、知らないコードを読むときの「決まった順番」です。
この教材では、次の 5 つの手順を型とします。

| 手順 | 問い | 主に見るもの |
| --- | --- | --- |
| 1. 入口 | 処理はどこから始まるか | `main`、`@GetMapping` などの注釈、`ApplicationRunner` |
| 2. 流れ | 入口からどのクラス・メソッドを通るか | メソッド呼び出しの連なり |
| 3. データ | 何を受け取り、何を返し、何を保存するか | `record`、テーブル定義、JSON |
| 4. エラー | 失敗したらどうなるか | `throw`、`catch`、例外ハンドラ |
| 5. テスト | 何が保証されているか | テストクラス、API テストのシナリオ |

30 実ソース読解の各章は、この型でサンプルアプリを読んでいきます。

## なぜ必要か

実案件のコードは、数百〜数千のファイルがあります。
ファイルを上から順に全部読むと、途中で全体が見えなくなります。
読む順番を決めておくと、必要な部分だけを、迷わずに読めます。

また、型があると、読んだ結果を人に伝えやすくなります。
「入口はここ、流れはこう、エラーはこう」と同じ形で話せるからです。
レビューや質問でも、同じ型で説明すると相手の理解が速くなります。

## どうやるか

### 1. 入口を探す

入口（エントリーポイント）とは、外から処理が呼ばれる最初の場所です。
Web API なら URL とメソッドが結びついた場所、バッチなら起動時に動くクラスです。
注釈（アノテーション）で検索すると、入口はすぐ見つかります。

```bash
# 例: API の入口を探す
grep -rn -E "@(Get|Post|Put|Delete|Request)Mapping" src/main/java
# 例: バッチの入口を探す
grep -rn -E "implements .*ApplicationRunner|static void main" src/main/java
```

### 2. 流れを追う

入口のメソッドから、呼び出し先を 1 つずつたどります。
VS Code なら、メソッド名の上で F12（定義へ移動）を使います。
たどった結果は、1 行の矢印で書き残します。

```text
例: GET /api/v1/members/{id}
MemberController.get → MemberService.get → MemberMapper.findById → MemberMapper.xml の findById
```

### 3. データを確かめる

流れの中で受け渡される型を確かめます。
`record` の項目、テーブルの列、JSON のキーが、どう対応するかを見ます。

### 4. エラーを確かめる

`throw` している場所と、それを受け取る場所（`catch` や例外ハンドラ）を対にして読みます。
「どの失敗が、最終的に利用者に何として見えるか」まで追うのがコツです。

### 5. テストで確かめる

テストは「このコードはこう動く」という動く仕様書です。
テストメソッドの名前を一覧すると、そのクラスの仕様の要約になります。
理解が正しいか迷ったら、コードを少し変えてテストを実行します。
落ちたテストが、その行の役割を教えてくれます。

!!! failure "悪い例"
    ```text
    例: パッケージの先頭のファイルから順に、全行を読む。
    common/ApiExceptionHandler.java → common/BusinessException.java → ...
    → 3 ファイル目で「これは何のために使われるのか」が分からなくなる
    ```

!!! success "良い例"
    ```text
    例: 調べたい機能（会員の照会）の入口から読み、メモを残す。
    入口: MemberController.get（31〜34 行目）
    流れ: → MemberService.get → MemberMapper.findById → MemberMapper.xml
    データ: Member(id, name, email)
    エラー: 無ければ NotFoundException → ApiExceptionHandler.notFound → 404
    テスト: MemberControllerTest.notFoundReturns404WithMessageId
    ```

### Copilot に説明させるときの型

Copilot（コード生成・説明を行う AI 支援ツール）は、コードの説明を素早く出せます。
ただし、説明はもっともらしい誤りを含むことがあります。
説明は「仮説」として受け取り、必ずコードとテストで確かめます。

!!! failure "悪い例"
    ```text
    例: 「このクラスを説明して」とだけ聞き、返ってきた説明をメモにそのまま写す。
    → 説明に「会員がいないと null を返す」と書かれていても気づけない
    ```

!!! success "良い例"
    ```text
    例: 「MemberService.get の動きを説明して。根拠となるファイル名と行番号を必ず添えて。
         会員が存在しないときの動きも書いて」と聞く。
    → 示された行を自分で開いて確かめる
    → 該当するテスト（MemberServiceTest.get_throwsNotFoundForUnknownId）を実行して確かめる
    ```

確かめる手順は、次の 3 つです。

1. 説明に書かれた行を開き、本当にそう書いてあるかを見る
2. その動きを保証するテストを探し、実行する
3. テストが無い動きは「未検証」として、メモに印をつける

## サンプルアプリでは

会員の照会 API（`GET /api/v1/members/{id}`）を、型の 5 手順で読みます。

**1. 入口** は `MemberController.get` です。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java#L17-L19 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="17"
@RestController
@RequestMapping("/api/v1/members")
public class MemberController {
```

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberController.java#L31-L34 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/member/MemberController.java" linenums="31"
    @GetMapping("/{id}")
    public Member get(@PathVariable("id") long id) {
        return service.get(id);
    }
```

クラスの `@RequestMapping` と、メソッドの `@GetMapping` を連結した URL が入口になります。

**2. 流れ** は、`MemberService.get` から `MemberMapper.findById` へ進みます。

<!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java#L19-L22 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="19"
    @Transactional(readOnly = true)
    public Member get(long id) {
        return mapper.findById(id).orElseThrow(() -> new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id));
    }
```

`MemberMapper` はインタフェースで、SQL の本体は XML にあります。

<!-- src: sample-app/src/main/resources/mapper/MemberMapper.xml#L5-L7 @exercise-base -->
```xml title="sample-app/src/main/resources/mapper/MemberMapper.xml" linenums="5"
  <select id="findById" resultType="com.example.sample.member.Member">
    SELECT id, name, email FROM member WHERE id = #{id}
  </select>
```

**3. データ** は `Member` です。
項目は `id`、`name`、`email` の 3 つで、そのまま JSON のキーになります。

<!-- src: sample-app/src/main/java/com/example/sample/member/Member.java#L10-L10 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/member/Member.java" linenums="10"
public record Member(Long id, String name, String email) {}
```

**4. エラー** は、会員がいないときの `NotFoundException` です。
これを `ApiExceptionHandler.notFound`（26〜29 行目）が受け取り、404 に変換します。

**5. テスト** は 2 種類あります。
単体テスト `MemberControllerTest.notFoundReturns404WithMessageId`（51〜57 行目）と、
API テスト `members.feature` の「存在しない会員は 404」（32〜36 行目）です。

<!-- src: sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java#L51-L57 @exercise-base -->
```java title="sample-app/src/test/java/com/example/sample/member/MemberControllerTest.java" linenums="51"
    @Test
    void notFoundReturns404WithMessageId() throws Exception {
        mvc.perform(get("/api/v1/members/42"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.messageId").value("APPE0002"))
                .andExpect(jsonPath("$.message").value("会員が見つかりません（会員ID: 42）。"));
    }
```

テストを読むと「42 番の会員はいない → 404 と APPE0002」という仕様が一目で分かります。

### 読んだ結果のメモの形

読んだ結果は、次の形で残すと、あとから自分も他人も使えます。

```text
例:
機能: 会員の照会（API0001）
入口: MemberController.java 31-34
流れ: MemberController.get → MemberService.get(19-22) → MemberMapper.findById → MemberMapper.xml 5-7
データ: Member(id, name, email) / テーブル member
エラー: 該当なし → NotFoundException(APPE0002) → ApiExceptionHandler.notFound → 404
テスト: MemberServiceTest.get_throwsNotFoundForUnknownId / MemberControllerTest.notFoundReturns404WithMessageId
       / members.feature「存在しない会員は 404」
未検証: 会員 ID が数値でないとき（例: /api/v1/members/abc）の応答
```

### 実案件での読み替え

実案件では、同じ型を次のものに当てはめて読みます。

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `@GetMapping` / `@PostMapping` | API 一覧（設計書）の API ID と、対応するコントローラのメソッド |
| `OrderImportJob`（`ApplicationRunner`） | ジョブ一覧のジョブ ID と、起動クラス・ジョブ定義 |
| `MemberService` → `MemberMapper` | 業務ロジック層とデータアクセス層（命名が `*Logic`、`*Dao`、`*Repository` のこともある） |
| `Member` / `member` テーブル | 画面・API の項目定義、テーブル定義書 |
| `ApiExceptionHandler` | 共通の例外処理（共通部品・フレームワーク側にあることが多い） |
| `MemberControllerTest` / `members.feature` | 単体テスト、結合テストのシナリオ、テスト仕様書 |

実案件では、設計書の API ID やジョブ ID で `grep` すると入口が早く見つかります。

## もし読み方の型がなかったら？

型が無いと、読む順番がその日の気分で変わります。
すると、同じ機能を何度も読み直したり、エラー処理を読み飛ばしたりします。
特に「4. エラー」と「5. テスト」は、型が無いと後回しになりがちです。
その結果、正常系だけを理解したつもりで修正し、異常系で障害を起こします。

また、Copilot の説明を検証する手順が無いと、誤った説明がそのままメモや設計書に残ります。
誤ったメモは、次に読む人の誤解も生みます。

## 理解度チェック

**問 1.** 型の 5 手順を、順番どおりに挙げてください。

??? note "答え"
    入口 → 流れ → データ → エラー → テスト です。

**問 2.** 会員の照会 API の入口が `MemberController.get` だと分かるのは、どの注釈からですか。

??? note "答え"
    クラスの `@RequestMapping("/api/v1/members")`（18 行目）と、
    メソッドの `@GetMapping("/{id}")`（31 行目）です。
    2 つを連結した `/api/v1/members/{id}` への GET が、このメソッドに届きます。

**問 3.** テストを「動く仕様書」と呼ぶのはなぜですか。

??? note "答え"
    テストには、入力と期待する結果が具体的に書かれているからです。
    さらに実行できるので、仕様どおりに動くかをその場で確かめられます。

**問 4.** Copilot の説明を検証する 3 つの手順は何ですか。

??? note "答え"
    1. 説明に書かれた行を開いて確かめる
    2. その動きを保証するテストを探して実行する
    3. テストが無い動きは「未検証」として印をつける

## コードを読むときの確認観点

- [ ] 入口（URL、ジョブ ID、`main`）を特定し、ファイル名と行番号をメモしたか
- [ ] 入口から最下層（SQL や外部呼び出し）まで、流れを 1 行で書けるか
- [ ] 受け渡されるデータの型と、テーブル・JSON との対応を確かめたか
- [ ] 例外を投げる場所と、受け取る場所を対で確かめたか
- [ ] その機能のテストを探し、実行したか
- [ ] Copilot の説明を、コードの行とテストで確かめたか

## 演習

1. 会員の登録 API（`POST /api/v1/members`）を、型の 5 手順で読みなさい。
   「サンプルアプリでは」のメモの形で、各手順にファイル名と行番号を添えて書きなさい。
2. 注文ファイル取込バッチ（JOB0001）の入口はどこですか。
   API の入口と比べて「何を見れば入口だと分かるか」が、どう違うかを行を示して説明しなさい。
3. Copilot が「`MemberService.get` は、会員が存在しないと `null` を返します」と説明しました。
   この説明は正しいですか。コードの行と、確かめるためのテストを示して答えなさい。
4. `MemberService.get` の `orElseThrow(...)` を `orElse(null)` に書き換えたとします。
   `./gradlew test` で落ちるテストをすべて挙げ、それぞれが落ちる理由を説明しなさい。

解答は [30-01 解答](answers/30-01.md) にあります。

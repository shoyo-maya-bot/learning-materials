# 30-07 会員サービス

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `MemberService` の `get` と `register` の処理を、1 行ずつ説明できる
    - メールアドレスの正規化と重複チェックの順番と、その理由を説明できる
    - `@Transactional` と `readOnly = true` の意味を説明できる
    - 事前チェックだけでは防げない重複（同時登録）を見つけられる

## 何か

サービスは、業務のルールを書く部品です。
コントローラから呼ばれ、Mapper を使ってデータを読み書きします。

`MemberService` には、2 つのメソッドがあります。

| メソッド | 役割 | 失敗のしかた |
| --- | --- | --- |
| `get(long id)` | 会員を 1 件取得する | 無ければ `NotFoundException`（`APPE0002`） |
| `register(String name, String email)` | 会員を登録する | メールアドレスが登録済みなら `BusinessException`（`APPE0003`） |

トランザクションの基本は [20-13 トランザクション](../20-basics/20-13-transaction.md) で学びました。

## なぜ必要か

業務のルールをサービスに集めると、次の利点があります。

- 同じルールを、API からもバッチからも使える
- HTTP や DB が無くても、単体テストでルールを確かめられる
- ルールを変えるときに、直す場所が 1 か所で済む

サービスを読むと、「この業務では何が許され、何が許されないか」が分かります。
コードを読むときに、最も時間をかけるべき部品の 1 つです。

## どうやるか

### 1 メソッドを 4 つに分けて読む

サービスのメソッドは、たいてい次の 4 つの部分でできています。

1. 入力を整える（正規化）
2. ルールを確かめる（チェック）
3. 読み書きする（Mapper の呼び出し）
4. 結果を返す（変換）

各行がどれに当たるかを、コメントを書き込むつもりで読みます。

### チェックと書き込みの間を疑う

「確かめてから書く」処理では、確かめた後、書く前に、他の処理が割り込めないかを考えます。
同時に 2 つのリクエストが来たとき、両方がチェックを通り抜けることがあります。
これを「チェックと実行の競合」と呼びます。

!!! failure "悪い例"
    ```java
    // 例: 重複チェックを正規化の前に行う
    if (mapper.existsByEmail(email)) {
        throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, email);
    }
    String normalized = email.trim().toLowerCase(Locale.ROOT);
    ```
    大文字・小文字の違うメールアドレスが、別のものとしてチェックを通り抜けます。

!!! success "良い例"
    ```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="26"
            String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
            if (mapper.existsByEmail(normalized)) {
                throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
            }
    ```
    先に正規化し、正規化した値でチェックし、同じ値を保存します。

## サンプルアプリでは

ファイルは `sample-app/src/main/java/com/example/sample/member/MemberService.java` です。

```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="9"
/** 会員の業務ロジック. */
@Service
public class MemberService {

    private final MemberMapper mapper;

    public MemberService(MemberMapper mapper) {
        this.mapper = mapper;
    }

    @Transactional(readOnly = true)
    public Member get(long id) {
        return mapper.findById(id).orElseThrow(() -> new NotFoundException(MessageIds.MEMBER_NOT_FOUND, id));
    }

    @Transactional
    public Member register(String name, String email) {
        String normalized = email.trim().toLowerCase(java.util.Locale.ROOT);
        if (mapper.existsByEmail(normalized)) {
            throw new BusinessException(MessageIds.EMAIL_ALREADY_USED, normalized);
        }
        MemberRecord rec = new MemberRecord(name.trim(), normalized);
        mapper.insert(rec);
        return rec.toMember();
    }
}
```

### クラスとコンストラクタ（10〜17 行目）

- `@Service`: Spring の Bean として登録されます。コントローラに注入されるのはこの Bean です
- 依存は `MemberMapper` だけです。サービスは HTTP のクラス（`ResponseEntity` など）を使いません

### get（19〜22 行目）

| 部分 | 行 | 内容 |
| --- | --- | --- |
| 読み書き | 21 | `mapper.findById(id)` で `Optional<Member>` を得る |
| チェックと結果 | 21 | 空なら `NotFoundException`、あれば `Member` を返す |

`@Transactional(readOnly = true)` は「読むだけのトランザクション」という宣言です。
書き込みをしないことを明示し、DB やドライバが読み取り向けの扱いをできるようにします。

### register（24〜33 行目）

| 部分 | 行 | 内容 |
| --- | --- | --- |
| 正規化 | 26 | メールアドレスの前後の空白を除き、小文字にする |
| チェック | 27〜29 | 正規化した値が登録済みなら `BusinessException` |
| 正規化 | 30 | 氏名の前後の空白を除き、`MemberRecord` を作る |
| 書き込み | 31 | `mapper.insert(rec)`。採番された ID が `rec` に入る |
| 結果 | 32 | `rec.toMember()` で、不変の `Member` に変換して返す |

読みどころは次の 3 つです。

**小文字化に `Locale.ROOT` を使っている（26 行目）。**
`toLowerCase()` を引数無しで呼ぶと、実行環境の言語設定で結果が変わることがあります。
例えばトルコ語の設定では、`I` が `i` ではなく別の文字（点の無い `ı`）になります。
`Locale.ROOT` を渡すと、どの環境でも同じ結果になります。
なお、`java.util.Locale` を `import` せずに完全な名前で書いているのは、書き方の揺れです。

**ID の受け取りに `MemberRecord` を使っている（30〜32 行目）。**
`Member` は `record` なので、作った後で ID を入れられません。
そこで、ID を書き戻せる可変のクラス `MemberRecord` で登録し、最後に `Member` に変換します。
詳しくは [30-08](30-08-mapper-sql.md) で読みます。

**`@Transactional` の範囲。**
`register` 全体が 1 つのトランザクションです。
`insert` の後で例外が起きれば、登録は取り消されます。
ただし、トランザクションがあっても、同時に来た 2 つの登録の両方が 27 行目のチェックを通り抜けることは防げません。
そのとき 2 つ目の `insert` は、DB のメールアドレスの一意制約（`local/db/init/01_schema.sql` の `UNIQUE`）に違反します。
この例外は `BusinessException` ではないので、`ApiExceptionHandler` では扱われず、409 ではなく 500 になります（演習 2）。

### テスト

`sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java` は、DB の代わりに `InMemoryMapper`（17〜37 行目）を使います。

```java title="sample-app/src/test/java/com/example/sample/member/MemberServiceTest.java" linenums="31"
        @Override
        public int insert(MemberRecord member) {
            member.setId(++seq);
            rows.put(member.getId(), member.toMember());
            return 1;
        }
```

本物の DB の採番（`useGeneratedKeys`）の代わりに、`setId` で連番を入れています。

| テスト | 確かめていること |
| --- | --- |
| `register_normalizesEmailAndAssignsId`（42〜49 行目） | 前後に空白のある氏名とメールアドレスが、空白除去・小文字化され、ID が 1 になる |
| `register_rejectsDuplicateEmailIgnoringCase`（51〜59 行目） | 大文字・小文字だけが違うメールアドレスは重複として `APPE0003` になる |
| `get_throwsNotFoundForUnknownId`（61〜67 行目） | 存在しない ID で `NotFoundException`（`APPE0002`） |

このテストは `new MemberService(mapper)` で直接作るので、`@Transactional` は効いていません。
トランザクションの動きは、この単体テストでは確かめられません。

### 実案件での読み替え

| サンプルアプリ | 実案件で探すもの |
| --- | --- |
| `MemberService` | 業務ロジックのクラス。1 クラスが大きいときは、公開メソッドの一覧から読む |
| 正規化（`trim`、小文字化） | 項目定義書の「入力値の扱い」（全角・半角、大文字・小文字、空白） |
| `existsByEmail` による重複チェック | 一意性のルールと、DB の一意制約の両方。両者が揃っているか |
| `@Transactional` | トランザクション境界の方針（サービスの公開メソッド単位が多い） |
| 同時登録で 500 になる問題 | 排他制御の方針（一意制約の例外の変換、楽観ロック、悲観ロック） |
| `InMemoryMapper` | テスト用の差し替え部品、モックライブラリの使い方 |

## もし正規化がなかったら？

`A@EXAMPLE.com` と `a@example.com` が、別の会員として登録できてしまいます。
同じ人が 2 つの会員になり、問い合わせや集計で混乱が起きます。
さらに、正規化をコントローラや画面ごとにばらばらに書くと、入口によって結果が変わります。
サービスの 1 か所で正規化することで、どの入口から来ても同じルールが守られます。

## 理解度チェック

**問 1.** `register` で、正規化を重複チェックより先に行うのはなぜですか。

??? note "答え"
    正規化した値でチェックしないと、大文字・小文字や空白だけが違うメールアドレスが、重複として見つからないからです。

**問 2.** `toLowerCase(java.util.Locale.ROOT)` の `Locale.ROOT` は何のためにありますか。

??? note "答え"
    実行環境の言語設定によらず、同じ小文字化の結果にするためです。

**問 3.** `register` が `Member` ではなく `MemberRecord` で登録するのはなぜですか。

??? note "答え"
    DB が採番した ID を書き戻すためです。
    `Member` は `record` で後から値を入れられないので、可変の `MemberRecord` を使います。

**問 4.** `MemberServiceTest` で `@Transactional` が効いていないのはなぜですか。

??? note "答え"
    Spring を使わず、`new MemberService(mapper)` で直接作っているからです。
    `@Transactional` は、Spring が作った Bean を通して呼んだときにだけ効きます。

## コードを読むときの確認観点

- [ ] 入力の正規化が、チェックや保存より前に、1 か所で行われているか
- [ ] チェックに使う値と、保存する値が同じか
- [ ] 「確かめてから書く」処理で、同時実行のときの動きを考えたか
- [ ] DB の制約違反の例外が、利用者にどう見えるかを確かめたか
- [ ] 書き込みのメソッドに `@Transactional` が付いているか、読み取りだけなら `readOnly = true` か
- [ ] 業務のルールごとに、単体テストがあるか

## 演習

1. `register` の引数 `email` に ` New.Member@Example.COM `（前後に空白）が渡されました。
   保存されるメールアドレスと、そうなる行を示しなさい。
2. 同じメールアドレスの登録リクエストが、ほぼ同時に 2 つ届きました。
   起こりうる結果を、行と DB の定義を示して説明しなさい。
   また、2 つ目も 409（`APPE0003`）で返すための修正案を書きなさい。
3. 30 行目の `name.trim()` を `name` に書き換えました。
   `./gradlew test` で落ちるテストと、落ちる行を答えなさい。
4. `get` の `@Transactional(readOnly = true)` を消しても、`./gradlew test` は通ります。
   それはなぜですか。また、それでも付けておく理由を説明しなさい。

解答は [30-07 解答](answers/30-07.md) にあります。

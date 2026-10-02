# 30-13 バッチの終了コード

!!! abstract "到達目標"
    - 終了コードとは何か、0 / 4 / 8 の決まりが何を意味するかを説明できる
    - `ExitCodeGenerator` と `SpringApplication.exit` で、終了コードがプロセスに渡る流れを読める
    - JOB0001 の入力ごとに、終了コードを予想できる
    - ジョブスケジューラが終了コードをどう使うかを説明できる

## 何か

**終了コード**は、プログラムが終わるときに呼び出し元へ返す整数です。
シェルなら `$?`、PowerShell なら `$LASTEXITCODE` で見られます。
一般に 0 が正常、0 以外が「何かあった」ことを表します。

JOB0001 の設計書 STEP3 は、終了コードを次のように決めています。

| 結果 | 終了コード | メッセージ |
|---|---|---|
| 全行正常 | 0 | APPI0002（件数を出力） |
| 形式エラーの行あり | 4 | APPW0001 + APPI0002 |
| 入力が読めない・引数不足 | 8 | エラーログ |

0 / 4 / 8 のように、**深刻さの順に間を空けた番号** を使う決まりは、業務システムのバッチでよく見られます。
間を空けておくと、後から 2 や 6 のような段階を足す余地が残ります。

## なぜ必要か

夜間のバッチは、人ではなく **ジョブスケジューラ**（ジョブを決まった時刻・順番で起動する仕組み）が動かします。
スケジューラはログの文章を読めません。判断に使うのは終了コードだけです。

- 0 なら、後続のジョブ（例: 注文の集計）を起動する
- 4 なら、後続は起動しつつ、担当者に「確認してください」と通知する
- 8 なら、後続を止め、担当者を呼び出す

終了コードを正しく返さないと、失敗したのに後続が動いたり、成功したのに夜中に呼び出されたりします。
終了コードは、**運用担当者との約束** です。

## どうやるか

終了コードの決め方は、次の 2 点を押さえて読みます。

1. **どこで決めるか**: 終了コードを決める場所が 1 か所にまとまっているか
2. **どうやって渡すか**: 決めた値が、確実にプロセスの終了コードになるか

!!! failure "悪い例"
    例: ジョブの途中で、あちこちから `System.exit(8)` を直接呼ぶ。

    ```java
    // 例: sample-app には無いコード
    if (input == null) {
        System.exit(8);
    }
    ```

    Spring の後片付け（DB 接続を閉じる等）が飛ばされます。単体テストから呼ぶとテストの JVM ごと終わってしまいます。

!!! success "良い例"
    ジョブは終了コードを **フィールドに記録するだけ** にする。
    プロセスを終えるのは起動クラスの 1 か所にまとめ、Spring の終了処理（`SpringApplication.exit`）を通す。

## サンプルアプリでは

### 終了コードの定義と決定

```java title="sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java（24〜34 行目、41〜65 行目を抜粋）"
public class OrderImportJob implements ApplicationRunner, ExitCodeGenerator {

    static final int OK = 0;
    static final int WARN = 4;
    static final int ERROR = 8;
    // ...
    private int exitCode = OK;
    // ...
    public void run(ApplicationArguments args) {
        // 44〜48 行目: 引数が無い・2 つ以上 → exitCode = ERROR; return;
        // ...
        try {
            ImportResult r = service.importLines(fetcher.readLines(input.get(0)));
            // 52〜54 行目: ログ出力
            exitCode = r.hasErrors() ? WARN : OK;
        } catch (Exception e) {
            log.error("JOB0001 異常終了", e);
            exitCode = ERROR;
        }
    }

    @Override
    public int getExitCode() {
        return exitCode;
    }
```

終了コードを決める行は、3 か所だけです。

| 行 | 値 | 条件 |
|---|---|---|
| 46 行目 | 8 | `--input` が無い、または 2 つ以上 |
| 55 行目 | 4 または 0 | 取込が最後まで進んだ。形式エラーの行があれば 4 |
| 58 行目 | 8 | 取得・見出しの確認・登録のどこかで例外 |

`ImportResult.hasErrors()` は `errors` が空でないかだけを見ます（`ImportResult.java` 14〜16 行目）。
**重複（`duplicated`）は 4 の理由になりません**。

### プロセスへの受け渡し

```java title="sample-app/src/main/java/com/example/sample/SampleApplication.java（16〜21 行目）"
    public static void main(String[] args) {
        ConfigurableApplicationContext ctx = SpringApplication.run(SampleApplication.class, args);
        if (ctx.getEnvironment().matchesProfiles("batch")) {
            System.exit(SpringApplication.exit(ctx));
        }
    }
```

流れは次のとおりです。

```text
(1) SpringApplication.run(...)        … 起動。最後に OrderImportJob.run が呼ばれ、exitCode が決まる
(2) SpringApplication.exit(ctx)       … ExitCodeGenerator の Bean（OrderImportJob）から getExitCode() を集め、
                                         アプリを閉じて（DB 接続などの後片付け）、終了コードを返す
(3) System.exit(終了コード)            … JVM を終了し、OS に終了コードを返す
(4) ジョブスケジューラ                  … 終了コードで次の動きを決める
```

`ExitCodeGenerator` の扱いの詳細は、[Spring Boot リファレンス: Application Exit](https://docs.spring.io/spring-boot/reference/features/spring-application.html#features.spring-application.application-exit) にあります。

!!! warning "run から例外を外に出すとどうなるか"
    `OrderImportJob.run` は、すべての例外を受け止めています（56 行目）。
    もし例外を外に出すと、`SpringApplication.run` 自体が例外で終わり、19 行目の `System.exit` まで届きません。
    `main` から例外が出た JVM の終了コードは 1 になり、0 / 4 / 8 の約束から外れます。

### スケジューラ側の例

ジョブスケジューラは、終了コードを次のように扱います（製品ごとに設定方法は違います）。

```bash
# 例: 起動シェルで終了コードを見て分岐する（sample-app には無いスクリプト）
java -jar sample-app-0.1.0.jar --spring.profiles.active=batch \
     --app.batch.job=JOB0001 --input=s3://<バケット>/<キー>
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "正常"                     # 後続ジョブへ
elif [ "$rc" -eq 4 ]; then
  echo "警告: 形式エラーの行あり"   # 後続ジョブへ進み、担当者に通知
else
  echo "異常終了 rc=$rc"            # 後続を止め、担当者を呼び出す
fi
exit "$rc"
```

最後の `exit "$rc"` を忘れると、シェル自体は 0 で終わり、スケジューラに異常が伝わりません。
起動シェルを挟む場合は、終了コードを **そのまま返しているか** を必ず確認します。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| `OK = 0` / `WARN = 4` / `ERROR = 8` | 運用設計書の終了コード体系（値と、それぞれの運用対応） |
| `OrderImportJob.getExitCode` | 終了コードを決める共通部品・ジョブの基底クラス |
| `SampleApplication.main` の `System.exit` | 起動クラスや起動シェルで、終了コードを返している箇所 |
| スケジューラ側の例のシェル | ジョブスケジューラのジョブ定義（終了コードごとの分岐・後続ジョブ・通知先） |
| `log.error("JOB0001 異常終了", e)` | 監視の対象になるログ（監視ツールが拾う文字列・メッセージ ID） |

## もし ExitCodeGenerator がなかったら？

`SpringApplication.exit(ctx)` は、終了コードを集める相手がいないので 0 を返します。
すると、ファイルが読めなくても、見出しが壊れていても、JOB0001 は **いつも 0（正常）で終わります**。

スケジューラは後続のジョブを起動し、注文の集計は「0 件」として進みます。
誰も気づかないまま翌朝を迎え、利用者からの問い合わせで初めて発覚する、という最も避けたい形の障害になります。

## 理解度チェック

1. 見出しだけで、データ行が 1 行も無いファイルを渡すと、終了コードはいくつですか。

    ??? note "答え"
        0 です。見出しは正しいので例外にならず、`errors` も空なので、55 行目で `OK` になります。
        「取り込む行が 0 件なら警告にしたい」という場合は、仕様として決めて実装を足す必要があります。

2. `OrderImportJob` で終了コードを決めている行を 3 つ答えてください。

    ??? note "答え"
        46 行目（引数不足で 8）、55 行目（正常なら 0、形式エラーの行があれば 4）、58 行目（例外で 8）です。

3. API として起動したとき、`OrderImportJob.getExitCode()` は呼ばれますか。

    ??? note "答え"
        呼ばれません。`SampleApplication.java` 18 行目の条件（プロファイル `batch`）が偽なので、`SpringApplication.exit` を呼びません。
        そもそも `app.batch.job` を指定しなければ、`OrderImportJob` は Bean になりません（30-09）。

4. 起動シェルで `exit "$rc"` を書き忘れると、何が起きますか。

    ??? note "答え"
        シェルの終了コードは最後のコマンド（`echo` など）の結果になり、たいてい 0 です。
        ジョブが 8 で終わっても、スケジューラには正常終了として伝わります。

## コードを読むときの確認観点

- [ ] 終了コードの値と意味が、設計書・運用設計書と一致しているか確認したか
- [ ] 終了コードを決める場所が限られていて、すべての経路で値が決まるか確認したか
- [ ] 例外が外に漏れて、約束に無い終了コード（1 など）にならないか確認したか
- [ ] `System.exit` を呼ぶ場所が 1 か所で、後片付けを通しているか確認したか
- [ ] 起動シェルやスケジューラまで、終了コードがそのまま届くか確認したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **動きを予想する**: 次の入力のとき、終了コードはそれぞれいくつですか。(a) `--input` を 2 回指定した (b) データ行がすべて重複 (c) 見出しの綴りが違う (d) データ行 3 行のうち 1 行の列数が 3
2. **どのテストが落ちるか**: `OrderImportJob.java` 55 行目を `exitCode = OK;` に変えたとき、`OrderImportJobTest` のどのテストが失敗しますか。
3. **どのテストが落ちるか**: 56〜59 行目の `catch` を消し、`run` に `throws Exception` を付けた（例外を外に出す）とします。コンパイルは通るとして、どのテストが失敗しますか。実際にバッチを動かしたときの終了コードはどうなりますか。
4. **小さな変更**: 仕様変更で「取り込めた行も重複した行も 0 件（`imported == 0` かつ `duplicated == 0`）なら 4 にする」ことになりました。変更する行と、追加するテストを書いてください。
5. **考える**: 設計書 STEP3 の表と `OrderImportJob` を比べたとき、メッセージの出し方で一致していない点はありますか。ログに出るメッセージ ID に注目してください。

解答: [30-13 解答](answers/30-13.md)

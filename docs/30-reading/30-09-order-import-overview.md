# 30-09 注文取込バッチの全体

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - 注文取込バッチ（JOB0001）が、どのクラスをどの順に通るかを説明できる
    - `ApplicationRunner` と `ExitCodeGenerator` が何をするかを説明できる
    - `@ConditionalOnProperty` で、起動するジョブが選ばれる仕組みを読める
    - 設計書と実装を突き合わせて、食い違いを見つけられる

## 何か

**バッチ**とは、人の操作を待たずに、決まった時刻にまとめて処理するプログラムです。
API が「1 件の依頼に 1 回答える」のに対し、バッチは「ファイルや表をまとめて処理して終わる」のが特徴です。

sample-app には、注文ファイル取込バッチ（ジョブ ID: JOB0001）が入っています。
設計書 `ai-coding/samples/design-docs/batch/JOB0001_order-import.md` の概要は次のとおりです。

| 項目 | 内容 |
|---|---|
| ジョブ ID | JOB0001 |
| 起動 | 毎日 2:00（ジョブスケジューラから起動） |
| 入力 | S3 上の注文 CSV（UTF-8、BOM 可、1 行目は見出し） |
| 出力 | 注文テーブル（`orders`） |
| 起動引数 | `--app.batch.job=JOB0001 --input=<s3://バケット/キー>` |

この章では、細部に入る前に「全体の流れ」をつかみます。
CSV の検証（30-10）、登録（30-11）、ファイル取得（30-12）、終了コード（30-13）は次章以降で掘り下げます。

## なぜ必要か

バッチのソースは、API より「入口」が見えにくいです。
API なら URL からコントローラを探せますが、バッチには URL がありません。
入口を知らずに業務ロジックから読み始めると、次のような疑問に答えられません。

- このクラスは、誰が、いつ呼び出すのか
- 起動引数はどこで受け取っているのか
- 処理が失敗したとき、呼び出し元（スケジューラ）には何が返るのか

全体の流れを先に押さえておくと、障害調査や改修のときに「どこを見ればよいか」がすぐ決まります。

## どうやるか

バッチを読むときは、**起動される順** にたどります。

!!! failure "悪い例"
    いきなり `OrderImportService` を開き、`parse` の分岐を 1 行ずつ追う。
    検証の細部はわかっても、「誰が呼ぶのか」「失敗したら何が起きるか」がわからないままになる。

!!! success "良い例"
    1. 設計書で、ジョブ ID・入力・出力・終了コードを確認する
    2. `main` メソッド（起動クラス）を読み、バッチとして起動したときの分岐を見る
    3. ジョブ ID でソースを検索し、ジョブのクラスを見つける
    4. ジョブのクラスの `run` を読み、呼び出す部品（取得・業務ロジック）を書き出す
    5. 部品を 1 つずつ開き、最後に SQL（Mapper の XML）まで降りる

JOB0001 の流れを、起動から終了まで並べると次のようになります。

```text
[ジョブスケジューラ]
   │ java -jar ... --spring.profiles.active=batch --app.batch.job=JOB0001 --input=s3://...
   ▼
(1) SampleApplication.main          … Spring を起動する
(2) application-batch.yml           … Web サーバーを立てない（web-application-type: none）
(3) @ConditionalOnProperty          … app.batch.job=JOB0001 のときだけ OrderImportJob を作る
(4) OrderImportJob.run              … Spring が起動完了後に呼ぶ（ApplicationRunner）
      ├─ (5) FileFetcher.readLines        … S3 またはローカルから行の一覧を読む
      ├─ (6) OrderImportService.importLines
      │        ├─ 見出しの確認 → 各行を parse（形式エラーは飛ばして記録）
      │        └─ OrderMapper.insertIfAbsent（ON CONFLICT DO NOTHING）
      └─ (7) ログ出力と exitCode の決定（0 / 4 / 8）
(8) SpringApplication.exit(ctx)     … ExitCodeGenerator から終了コードを集める
(9) System.exit(終了コード)          … プロセスが終わり、スケジューラに終了コードが返る
```

用語を 2 つ補足します。

- **`ApplicationRunner`**: Spring Boot の起動が終わった直後に、`run` が 1 回呼ばれる仕組みです。バッチの「本体」を置く場所としてよく使います
- **`ExitCodeGenerator`**: `SpringApplication.exit` を呼んだときに、プロセスの終了コードを返す仕組みです

公式の説明は [Spring Boot リファレンス: SpringApplication](https://docs.spring.io/spring-boot/reference/features/spring-application.html) にあります。

## サンプルアプリでは

### (1) 起動クラス

<!-- src: sample-app/src/main/java/com/example/sample/SampleApplication.java#L13-L22 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/SampleApplication.java（13〜22 行目）"
@SpringBootApplication
public class SampleApplication {

    public static void main(String[] args) {
        ConfigurableApplicationContext ctx = SpringApplication.run(SampleApplication.class, args);
        if (ctx.getEnvironment().matchesProfiles("batch")) {
            System.exit(SpringApplication.exit(ctx));
        }
    }
}
```

- 17 行目: Spring を起動します。この中で `ApplicationRunner` の `run` が呼ばれます
- 18〜20 行目: プロファイル `batch` が有効なときだけ、終了コードを集めてプロセスを終えます
- API として起動したとき（`batch` なし）は 18 行目を素通りし、Web サーバーが動き続けます

### (2) バッチ用の設定

<!-- src: sample-app/src/main/resources/application-batch.yml @exercise-base -->
```yaml title="sample-app/src/main/resources/application-batch.yml（全体）"
# バッチとして起動する（Web サーバーを立てず、ジョブが終わったら終了する）
spring:
  main:
    web-application-type: none
```

API とバッチは 1 つのプロジェクトに同居しています（`build.gradle` 1 行目（`// サンプルアプリ`）のコメント）。
同じ jar を、プロファイルの違いで API にもバッチにも使い分けています。

### (3)(4)(7) ジョブのクラス

<!-- src: sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java#L22-L24,L41-L60 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java（22〜60 行目を抜粋）"
@Component
@ConditionalOnProperty(name = "app.batch.job", havingValue = "JOB0001")
public class OrderImportJob implements ApplicationRunner, ExitCodeGenerator {
    // ...
    @Override
    public void run(ApplicationArguments args) {
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
    }
```

- 23 行目: 設定 `app.batch.job` が `JOB0001` のときだけ、このクラスが Bean（Spring が管理する部品）になります
- 24 行目: 2 つのインタフェースを実装し、「本体」と「終了コード」を 1 クラスで受け持ちます
- 43〜48 行目: `--input` が無い・2 つ以上あるときは、何もせず終了コード 8 にします
- 51 行目: 「読む」と「取り込む」を 1 行でつないでいます。ここがジョブの心臓部です
- 52〜54 行目: 形式エラーの行を警告ログ、件数を情報ログに出します
- 56〜59 行目: どんな例外も受け止めて、終了コード 8 にします

### 関係するファイルの一覧

| 役割 | ファイル |
|---|---|
| 起動 | `sample-app/src/main/java/com/example/sample/SampleApplication.java` |
| ジョブ（入口） | `sample-app/src/main/java/com/example/sample/order/batch/OrderImportJob.java` |
| ファイル取得 | `.../order/batch/FileFetcher.java`、`DefaultFileFetcher.java`、`S3Config.java` |
| 業務ロジック | `sample-app/src/main/java/com/example/sample/order/OrderImportService.java` |
| データ | `.../order/Order.java`、`ImportResult.java` |
| SQL | `.../order/OrderMapper.java`、`sample-app/src/main/resources/mapper/OrderMapper.xml` |
| 設定 | `sample-app/src/main/resources/application-batch.yml`、`application-local.yml` |
| テスト | `sample-app/src/test/java/com/example/sample/order/OrderImportJobTest.java` ほか |
| ローカルの入力 | `local/data/orders.csv`、`local/scripts/upload-sample.sh` |

ローカルでの起動方法は `local/README.md` の「8. サンプルバッチを動かす」にあります。

```bash
cd ../local && ./scripts/upload-sample.sh
cd ../sample-app
./gradlew bootRun --args='--spring.profiles.active=local,batch --app.batch.job=JOB0001 --input=s3://sample-bucket/orders.csv'
```

### 設計書と実装の突き合わせ

設計書と実装は、いつも一致しているとは限りません。
JOB0001 でも、次の点は自分の目で確かめる価値があります。

| 設計書の記述 | 実装で確かめる場所 |
|---|---|
| 実装クラスのパッケージ名 | `OrderImportJob.java` 1 行目の `package` 文 |
| 入力の S3 キー | ローカルは `orders.csv`（`upload-sample.sh` 7 行目（`orders.csv`））。本番のキーは起動引数で渡す |
| 終了コード 0 / 4 / 8 | `OrderImportJob.java` 26〜28 行目（`OK = 0`） |
| メッセージ ID | `MessageIds.java` 13〜15 行目（`IMPORT_STARTED`）、`messages.properties` 4〜6 行目（`APPI0001`） |

!!! tip "ずれを見つけたら"
    どちらが正しいかを自分で決めず、設計書の担当者に確認してください。
    「設計書を直す」のか「実装を直す」のかは、チームで決めることです。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| ジョブ ID `JOB0001` | ジョブ一覧・運用設計書のジョブ ID。ソース全体をこの ID で検索する |
| `SampleApplication.main` | バッチの起動クラス、または起動シェル（`java -jar` を呼ぶスクリプト） |
| `application-batch.yml` | バッチ用のプロファイル・設定ファイル |
| `@ConditionalOnProperty(... "JOB0001")` | ジョブを選ぶ仕組み（起動引数、ジョブ定義ファイル、バッチ用フレームワークの設定など） |
| `OrderImportJob.run` | ジョブの本体（`ApplicationRunner`、`CommandLineRunner`、バッチ用フレームワークのステップなど） |
| `--input=s3://...` | ジョブスケジューラのジョブ定義に書かれた起動引数 |

## もし @ConditionalOnProperty がなかったら？

`OrderImportJob` は `@Component` なので、条件が無ければ **どのプロファイルでも Bean になります**。
すると API として起動しただけで `run` が呼ばれ、`--input` が無いため 45 行目のエラーログが毎回出ます。
ジョブが増えたときはもっと深刻です。JOB0002 を起動したつもりでも、JOB0001 まで一緒に動いてしまいます。

ジョブごとに「この設定のときだけ動く」と条件を付けることで、1 つの jar に複数のジョブを入れても、起動引数で 1 つだけを選べます。

## 理解度チェック

1. `OrderImportJob.run` を呼び出しているのは誰ですか。

    ??? note "答え"
        Spring Boot です。起動（`SpringApplication.run`）の最後に、`ApplicationRunner` を実装した Bean の `run` を呼びます。
        自分たちのコードに `job.run(...)` と書いている箇所は、テスト以外にありません。

2. 同じ jar を API として起動したとき、プロセスが終わらないのはなぜですか。

    ??? note "答え"
        `SampleApplication.java` 18 行目（`matchesProfiles("batch")`）の条件（プロファイル `batch`）が偽になり、`System.exit` を呼ばないからです。
        また `application-batch.yml` が読まれないので、Web サーバーが起動したまま待ち続けます。

3. `OrderImportJob` が受け持つ 2 つの役割を答えてください。

    ??? note "答え"
        ジョブの本体（`ApplicationRunner.run`）と、終了コードを返すこと（`ExitCodeGenerator.getExitCode`）です。

4. 取込の業務ロジック（検証と登録）は、どのクラスにありますか。

    ??? note "答え"
        `OrderImportService` です。`OrderImportJob` は、引数の確認・ログ・終了コードの決定といった「ジョブの枠」だけを持ちます。

## コードを読むときの確認観点

- [ ] 設計書のジョブ ID でソースを検索し、ジョブのクラスを特定したか
- [ ] 起動クラスで、バッチ起動時の分岐（プロファイル・`System.exit`）を確認したか
- [ ] ジョブが選ばれる条件（`@ConditionalOnProperty` など）を確認したか
- [ ] `run` から呼ばれる部品を、取得・業務ロジック・SQL に分けて書き出したか
- [ ] 例外がどこで受け止められ、終了コードがどこで決まるかを確認したか
- [ ] 設計書と実装（パッケージ名・引数・終了コード・メッセージ ID）を突き合わせたか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **場所を探す**: README に出てくるログ `APPI0002 JOB0001 終了 imported=3 duplicated=0 errors=1` は、どのファイルの何行目で出力されていますか。
2. **場所を探す**: バッチとして起動したとき Web サーバー（ポート 8080）が立ち上がらないのは、どのファイルのどの設定によるものですか。
3. **動きを予想する**: `--spring.profiles.active=local,batch --app.batch.job=JOB0002 --input=s3://sample-bucket/orders.csv` で起動すると、何が起き、終了コードはいくつになりますか。
4. **突き合わせ**: 設計書 `JOB0001_order-import.md` の「実装クラス」欄と、sample-app の実際のクラスの完全修飾名（パッケージ名 + クラス名）を比べ、違いを答えてください。
5. **小さな変更**: S3 ではなく、手元のファイル `local/data/orders.csv` を直接読ませて JOB0001 を動かしたいとします。`sample-app` ディレクトリで実行する起動コマンドを書き、それが動く根拠となるコードの場所を答えてください。

解答: [30-09 解答](answers/30-09.md)

!!! tip "案件担当として"
    この章の内容を「なぜそうするか」まで説明できるようになったら、[80-07 設計書とコードの対応と変更の影響範囲](../80-case-owner/80-07-design-code-impact.md) に進みます。
    STEP とコードの対応づけと、項目を足すときの影響範囲の洗い出しの練習です。

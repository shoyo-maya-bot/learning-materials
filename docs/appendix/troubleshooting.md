# つまずき集

環境構築やビルドでよく出るエラーを、**症状 → 原因 → 対処** の形でまとめています。
まず下の一覧で症状を探し、詳しい説明に進んでください。

!!! tip "調べる前に"
    - エラーは出力の **最初** に出たものから見ます。最後の `BUILD FAILED` だけでは原因が分かりません
    - 状況を確かめるコマンド: `java -version`、`echo $JAVA_HOME`、`docker compose ps`、`docker compose logs db`
    - Copilot Chat の `/env-troubleshoot` でも、手順に沿って調べられます（[10-06](../10-setup/10-06-copilot.md)）

## 一覧

| 症状 | 原因 | 対処 |
|---|---|---|
| `gradlew` や `docker compose up` で証明書エラー（`PKIX path building failed` など） | 社内プロキシの SSL 検査 | [プロキシと証明書](#proxy) |
| `JAVA_HOME is not set` / `JAVA_HOME is set to an invalid directory` | `JAVA_HOME` が無い・誤り | [JAVA_HOME](#java-home) |
| `java -version` は 17 なのにビルドが別の版で動く | 複数の JDK が入っている | [JAVA_HOME](#java-home) |
| `./gradlew: Permission denied` | 実行権限が落ちた | [gradlew の権限](#gradlew-permission) |
| `bad interpreter` / `$'\r': command not found` | スクリプトが CRLF になっている | [改行コード](#crlf) |
| `port is already allocated` / `address already in use` | 5432・9090・8080 番を別のソフトが使用中 | [ポートの競合](#port) |
| `docker: command not found` | Rancher Desktop が起動していない、containerd を選んでいる | [コンテナが起動しない](#container) |
| `docker compose ps` で `unhealthy`、または `--wait` が終わらない | コンテナの起動失敗 | [コンテナが起動しない](#container) |
| ログやコンソールの日本語が文字化けする | コンソールの文字コード | [文字化け](#mojibake) |
| `Connection refused`（DB）で起動やテストが失敗する | DB コンテナが起動していない | [DB が起動していない](#db-not-up) |
| `karateTest` がすべて失敗する | API を起動していない | [DB が起動していない](#db-not-up) |
| 初期データが入っていない・テーブルが無い | 初期化 SQL は初回だけ実行される | [初期データ](#init-data) |

## プロキシと証明書 { #proxy }

**症状**: `./gradlew build` の初回に、依存ライブラリのダウンロードで次のようなエラーが出る。

```text
PKIX path building failed: unable to find valid certification path to requested target
```

**原因**: 社内プロキシが通信の中身を検査するため、独自の証明書（社内 CA）で通信を作り直しています。
Java は社内 CA を知らないため、相手を信用できずに接続を止めます。

**対処**:

1. 社内 CA 証明書と、プロキシの設定値を情報システム部門の手順で入手する
2. 社内 CA 証明書を、使っている JDK の `cacerts`（信頼する証明書の一覧）に取り込む
3. Gradle にプロキシを設定する場合は、ユーザーのホーム直下の `.gradle/gradle.properties` に書く（例: `systemProp.https.proxyHost=...`）
4. Rancher Desktop のイメージ取得が失敗する場合は、Preferences の WSL → Network、または環境変数 `HTTPS_PROXY` を設定する

!!! warning "証明書の検証を無効にしない"
    「検証を無効にすれば動く」という情報がありますが、通信の安全性を損ないます。必ず証明書を取り込む方法で解決してください。
    プロキシの認証情報をリポジトリのファイルに書かないでください。

## JAVA_HOME { #java-home }

**症状**:

```text
ERROR: JAVA_HOME is set to an invalid directory: C:\Program Files\Amazon Corretto\jdk17.x.x_x\bin
```

または、`java -version` は 17 なのに、Gradle が別の版で動く。

**原因**: `JAVA_HOME` が設定されていない、`bin` まで含めている、古い JDK を指している、のいずれかです。

**対処**:

1. `echo $env:JAVA_HOME`（PowerShell）または `echo "$JAVA_HOME"`（Git Bash）で値を確認する
2. `JAVA_HOME` を JDK のフォルダ（`bin` の 1 つ上）に直す
3. `Path` で `%JAVA_HOME%\bin` がほかの JDK より上にあることを確認する
4. ターミナルと VS Code を **すべて閉じて** 開き直す

詳しくは [10-03 JDK と VS Code](../10-setup/10-03-jdk-vscode.md) を見てください。

## gradlew の権限 { #gradlew-permission }

**症状**: Git Bash で `./gradlew build` を実行すると `Permission denied` になる。

**原因**: `gradlew` の実行権限が、コピーや ZIP の展開などで失われています。

**対処**: どちらかを実行します。

```bash
bash gradlew build                      # その場しのぎ: bash に読ませる
git update-index --chmod=+x gradlew     # リポジトリ上の権限を直す（変更として commit が必要）
```

PowerShell では `.\gradlew.bat` を使えば権限の問題は起きません。

## 改行コード（CRLF） { #crlf }

**症状**: シェルスクリプトを実行すると次のようなエラーになる。

```text
/usr/bin/env: 'bash\r': No such file or directory
$'\r': command not found
```

**原因**: スクリプトの改行コードが Windows 形式（CRLF）になっています。
`.gitattributes` の無いリポジトリで `core.autocrlf=true` だったり、エディタで CRLF にして保存したりすると起きます。

**対処**:

1. VS Code でファイルを開き、右下の「CRLF」をクリックして「LF」に変えて保存する
2. リポジトリに `.gitattributes` があるなら、取り出し直す: `git rm --cached -r . && git reset --hard`（未コミットの変更が消えるので先に退避する）
3. 再発を防ぐには、`.gitattributes` で `*.sh text eol=lf` のように固定する

詳しくは [10-02 Git と GitHub の準備](../10-setup/10-02-git.md) を見てください。

## ポートの競合 { #port }

**症状**:

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

または、アプリの起動時に `Port 8080 was already in use`。

**原因**: 同じポートを別のソフト（PC に直接入れた PostgreSQL、前に起動したままのアプリなど）が使っています。

**対処**:

1. 使っているプロセスを調べる（PowerShell）: `netstat -ano | findstr :5432` で PID を確認し、タスクマネージャーで該当のプロセスを探す
2. 不要なら止める（PC に入れた PostgreSQL のサービス、起動したままの `bootRun` など）
3. 止められない場合は、`local/.env` の `DB_PORT` や `S3_PORT` を変える。アプリを起動するターミナルで、環境変数 `DB_URL`（例: `jdbc:postgresql://localhost:15432/sampledb`）や `S3_ENDPOINT` も合わせる
4. アプリの 8080 番が使えない場合は、環境変数 `SERVER_PORT` で変えられる（Karate の接続先も合わせる必要がある）

## コンテナが起動しない { #container }

**症状 1**: `docker: command not found`

**原因と対処**: Rancher Desktop が起動していないか、Container Engine が containerd になっています。
Rancher Desktop を起動し、Container Engine を「dockerd (moby)」にして、ターミナルを開き直します。

**症状 2**: `docker compose up -d --wait` が終わらない、または `unhealthy` になる。

**対処**:

1. `docker compose ps` で、どのサービスが問題かを確認する
2. `docker compose logs db`（または `s3`）でログを見る
3. よくある原因:
    - Rancher Desktop のメモリ不足 → Preferences → Virtual Machine で 4GB 以上にする
    - `.env` が無い・値が誤っている → `.env.example` からコピーし直す
    - イメージを取得できない → [プロキシと証明書](#proxy) を確認する
4. それでも直らないときは、Rancher Desktop の Troubleshooting 画面の「Factory Reset」を検討する（コンテナとデータが消えるので、相談してから行う）

## 文字化け { #mojibake }

**症状**: `bootRun` のログやテストの出力で、日本語が `ã` や `?` のように崩れる。

**原因**: Windows のコンソールの文字コードが UTF-8 ではありません（既定は Shift_JIS 系の CP932）。

**対処**:

1. PowerShell で `chcp 65001` を実行してから起動する
2. 毎回の設定が面倒な場合は、Windows の設定で「ベータ: ワールドワイド言語サポートで Unicode UTF-8 を使用」を有効にする（ほかのソフトへの影響があるので、チームの方針を確認する）
3. ソースの文字化け（コンパイルエラー）は、`build.gradle` の `options.encoding = 'UTF-8'` で防がれています。エディタの保存形式も UTF-8 にしてください

## DB が起動していない { #db-not-up }

**症状**: `bootRun` やテストで次のようなエラーが出る。

```text
org.postgresql.util.PSQLException: Connection to localhost:5432 refused.
```

**原因**: DB コンテナが起動していない、または起動の途中（healthy になる前）に接続しました。

**対処**:

1. Rancher Desktop が起動していることを確認する
2. `local` フォルダで `docker compose up -d --wait` を実行する
3. `docker compose ps` で `db` が `healthy` になってから、アプリを起動する

!!! note "どのテストが DB を使うか"
    `./gradlew test`（単体テスト）は DB を使わないので、DB が止まっていても通ります。
    DB と API が必要なのは `./gradlew karateTest` です。
    `karateTest` がすべて失敗するときは、API を `bootRun` で起動しているかを確認してください。

## 初期データ { #init-data }

**症状**: `member` テーブルが無い、または会員のデータが入っていない。

**原因**: `local/db/init/` の SQL は、DB のデータが空のとき（初回起動時）だけ実行されます。
途中で SQL を変えても、既存のデータには反映されません。

**対処**: データを消して作り直します（ローカルのデータがすべて消えます）。

```bash
docker compose down -v && docker compose up -d --wait
```

その後、バッチの入力ファイルも置き直します（`./scripts/upload-sample.sh`）。

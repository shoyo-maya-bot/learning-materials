# 80-13 環境の差と共通部品

!!! abstract "到達目標"
    - ローカル開発環境の各ツール（コンテナの実行環境・DB・クラウドのエミュレータ・エディタ・Git）の役割を説明できる
    - 開発環境と本番環境の差を挙げ、その差で起きうる不具合を説明できる
    - Dockerfile の主な命令（FROM・WORKDIR・COPY・RUN・USER・EXPOSE・ENTRYPOINT）の意味を説明できる
    - 共通部品を取得する 3 つの仕組み（ローカルビルド・パッケージレジストリ・git submodule）と、更新の手順を説明できる

## 何か

### 開発環境の道具と役割

ローカル環境の作り方は [10 環境構築](../10-setup/index.md) で学びました。
ここでは、それぞれの道具が **本番の何の代わりをしているか** を整理します。

| 道具 | 役割 | 本番での相手 |
|---|---|---|
| コンテナの実行環境（Rancher Desktop など） | DB やエミュレータをコンテナで動かす | コンテナの実行基盤（クラウドのサービス） |
| DB のコンテナ（PostgreSQL） | アプリのデータを置く | クラウドの管理された DB |
| S3 のエミュレータ | ファイルの置き場所の代わり | S3 |
| JDK と Gradle | ビルドと実行 | ビルドは CI、実行はコンテナの中の JRE |
| エディタ（VS Code） | 書く・読む・デバッグする | （なし） |
| Git | 変更の履歴と共有 | CI と出荷の起点 |

### Dockerfile

**Dockerfile** は、コンテナのイメージを作る手順を書いたファイルです
（[Dockerfile reference（Docker）](https://docs.docker.com/reference/dockerfile/)）。

| 命令 | 意味 |
|---|---|
| `FROM` | 元にするイメージ。複数書くと、ビルド用と実行用を分けられる（マルチステージ） |
| `WORKDIR` | 以降の命令の作業フォルダ |
| `COPY` | ファイルをイメージに入れる。`--from=` で前の段階から持ってくる |
| `RUN` | イメージを作るときに実行するコマンド |
| `USER` | 以降の命令とコンテナの実行に使う利用者 |
| `EXPOSE` | コンテナが待ち受けるポートの宣言（説明のためのもの。公開は起動の設定で決まる） |
| `ENTRYPOINT` | コンテナを起動したときに実行するコマンド |

### 共通部品の取得

複数のアプリで使う共通部品（ライブラリ）は、次のどれかの仕組みで取り込みます。

| 仕組み | やり方 | 向く場面 |
|---|---|---|
| ローカルビルド | 部品を手元でビルドし、PC の中の Maven ローカルリポジトリ（`~/.m2/repository`）に置く。使う側は `mavenLocal()` から取る | 部品を直しながら、使う側で試す |
| パッケージレジストリ | 部品をビルドしてレジストリ（社内の Maven リポジトリや GitHub Packages など）に公開する。使う側は版を指定して取る | チームで同じ版を使う。CI でも同じものを取る |
| git submodule | 部品のリポジトリを、使う側のリポジトリの中に、特定のコミットを指して取り込む | ソースのまま取り込みたい。ビルドの仕組みが無い |

仕組みの詳細は公式にあります。
[Declaring Repositories（Gradle）](https://docs.gradle.org/current/userguide/declaring_repositories.html)、
[Gradle レジストリの利用（GitHub Docs）](https://docs.github.com/ja/packages/working-with-a-github-packages-registry/working-with-the-gradle-registry)、
[git-submodule](https://git-scm.com/docs/git-submodule)。

## なぜ必要か

作業担当は、手順書どおりに環境を作り、`docker compose up -d` や `down` を使えれば十分です。
案件担当は、各道具の役割と本番との差を説明でき、環境のトラブルを自分で切り分けられる必要があります。

「手元では動くが、検証環境では動かない」の多くは、環境の差から起きます。
差を知っていれば、どこを疑えばよいかがすぐ分かります。

共通部品の仕組みを知らないと、「自分の PC では新しい部品が使われていたが、CI では古い部品だった」といった食い違いに気づけません。

## どうやるか

### 1. 開発と本番の差を表にする

| 差 | ローカル | 本番 | 起きうる不具合 |
|---|---|---|---|
| 接続先と認証 | エミュレータ・固定のパスワード | 本物のサービス・ロールと秘密情報の管理の仕組み | 権限が足りずに読めない |
| 設定の切り替え | プロファイル `local` | 環境変数で渡す | 設定の渡し忘れ |
| JDK の版 | 手元の JDK（新しいことがある） | イメージの中の JRE | 新しい版の機能を使ってしまう |
| データの量 | 数件 | 数十万件 | メモリ不足・遅さ（[80-11](80-11-data-io.md)） |
| 時刻・文字コード | PC の設定 | コンテナの設定 | 日付の境目のずれ、文字化け |

### 2. Dockerfile を読む

sample-app には Dockerfile がありません（本番のイメージの作り方は範囲外）。
Spring Boot のアプリなら、例えば次のように書きます。

```dockerfile
# 例: ビルド用と実行用を分ける（マルチステージ）
FROM eclipse-temurin:17-jdk AS build
WORKDIR /src
COPY . .
RUN ./gradlew bootJar --no-daemon

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /src/build/libs/sample-app-0.1.0.jar app.jar
RUN useradd --system app
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

| 箇所 | 意図 |
|---|---|
| `FROM ... AS build` と 2 つ目の `FROM` | 実行用のイメージに JDK やソースを入れず、小さく安全にする |
| `COPY --from=build` | ビルド用の段階で作った jar だけを持ってくる |
| `USER app` | 管理者（root）で動かさない。乗っ取られたときの被害を小さくする |
| `ENTRYPOINT` の配列の形 | シェルを通さずに起動し、停止の合図が Java に直接届く |

書き方の勧めは [Building best practices（Docker）](https://docs.docker.com/build/building/best-practices/) にあります。

### 3. 共通部品を更新する

| 仕組み | 更新の手順 | 確かめること |
|---|---|---|
| ローカルビルド | 部品のリポジトリで `./gradlew publishToMavenLocal`（`maven-publish` プラグインが要る）。使う側をビルドし直す | 自分の PC にしか無い版を使っていないか（CI では取れない） |
| パッケージレジストリ | 使う側の `build.gradle` の版を上げる | 変更点（リリースノート）と、使う側のテスト |
| git submodule | `git submodule update --init` で取り出す。新しいコミットにするときは、部品のフォルダでそのコミットを取り出し、使う側でその変更をコミットする | 使う側のリポジトリが指しているコミット（`git submodule status`） |

!!! warning "submodule は「コミットを指している」"
    submodule は、部品のブランチではなく、特定のコミットを指して記録されます。
    部品のリポジトリが新しくなっても、使う側でコミットを進めて記録しない限り、古いままです。
    clone した直後は中身が空なので、`git submodule update --init` を実行します。

## サンプルアプリでは

`sample-app/build.gradle` は、部品を公開のリポジトリ（Maven Central）からだけ取ります。

<!-- src: sample-app/build.gradle @main -->
```groovy
repositories {
    mavenCentral()
}
```

社内の共通部品を使う案件では、ここに `mavenLocal()` やレジストリの URL が足されます。
どこから取っているかを見れば、CI で同じ部品が取れるかを判断できます。

ローカルと本番の差は、dev-environment の `cloud/README.md` に表でまとめられています。

<!-- src: cloud/README.md @main -->
```markdown
| 実行 | `./gradlew bootRun` | ECS Fargate（コンテナ） |
| DB | PostgreSQL 16（コンテナ） | Aurora PostgreSQL |
| ファイル | S3 エミュレータ（コンテナ） | S3 |
| 非同期 | （必要ならエミュレータを追加） | SQS |
| ジョブ起動 | 起動引数で直接 | EventBridge Scheduler → Step Functions |
| 秘密情報 | `.env`（コミットしない） | Secrets Manager |
| 構築 | `docker compose up` | Terraform |
| 設定の切替 | プロファイル `local` | プロファイル `cloud`（環境変数で値を渡す） |
```

`local/docker-compose.yml` は、イメージを digest（中身から計算した値）まで固定しています（[10-04](../10-setup/10-04-docker-local.md)）。
これは submodule が「コミットを指す」のと同じ考え方で、全員が同じものを使うための仕組みです。
この教材のリポジトリも、引用する dev-environment のコミットを `dev-environment-pin.json` に固定しています。

## もし環境の差の表がなかったら？

ローカルではエミュレータに固定のキーでつないでいたので、S3 の読み取りが問題なく動いていました。
検証環境に出したら、ファイルを読めずに異常終了しました。
原因は、本番側のロールに読み取りの権限が無かったことです。

差の表があれば、「接続先と認証」の行を見て、最初に権限を疑えます。
差を知らないと、コードの不具合を探して時間を使います。

## 理解度チェック

1. Dockerfile をマルチステージにする理由は何ですか。
2. `EXPOSE 8080` と書くだけで、PC から 8080 番につながりますか。
3. `mavenLocal()` から取った部品で手元のビルドが通っても、CI で失敗することがあるのはなぜですか。
4. 部品のリポジトリを更新したのに、submodule を使う側で古いままなのはなぜですか。

??? note "答え"
    1. 実行用のイメージに JDK やソースを入れず、小さく、攻撃の足場になるものを減らすためです。
    2. つながりません。`EXPOSE` は宣言で、公開は起動の設定（`docker run -p` や compose の `ports`）で決まります。
    3. ローカルリポジトリは自分の PC の中にしか無く、CI の環境には無いからです。チームで使う版は、レジストリに公開します。
    4. submodule は部品の特定のコミットを指して記録されるからです。使う側で新しいコミットを取り出し、その変更をコミットする必要があります。

## コードを読むときの確認観点

- [ ] `build.gradle` の `repositories` に、CI から取れないもの（`mavenLocal()` など）が入っていないか
- [ ] 依存の版が固定されているか（イメージは digest、部品は版、submodule はコミット）
- [ ] Dockerfile が、root で動かしていないか・実行用に不要なものを入れていないか
- [ ] ローカルと本番で、設定の渡し方（プロファイル・環境変数）の対応が分かるか

## 演習

1. dev-environment の `local/docker-compose.yml` を読み、`db` と `s3` の各サービスについて、
   本番で何の代わりをしているかと、本番との差で起きうる不具合を 1 つずつ答えてください。
2. 上の Dockerfile の例について、次の変更をすると何が起きるかを答えてください。
   (a) `USER app` を消す (b) 2 つ目の `FROM` を消し、1 つ目のイメージのまま実行する
   (c) `ENTRYPOINT java -jar app.jar`（配列でない形）にする
3. 共通部品 `common-util` を、別のチームが 1.4.0 から 1.5.0 に上げました。
   あなたの案件は、(a) パッケージレジストリから取る (b) git submodule で取り込む のそれぞれの場合で、
   新しい版を使うための手順と、上げる前に確かめることを答えてください。

解答: [80-13 解答](answers/80-13.md)

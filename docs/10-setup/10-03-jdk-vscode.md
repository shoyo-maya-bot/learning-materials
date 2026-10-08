---
render_macros: true
---

# 10-03 JDK と VS Code

!!! abstract "到達目標"
    - JDK（Java の開発キット）を入れ、`java -version` で 17 以上であることを確認できる
    - 環境変数 `JAVA_HOME` の役割を説明し、正しく設定できる
    - VS Code にチーム推奨の拡張機能を入れられる

## 何か

**JDK**（Java Development Kit）は、Java のソースをコンパイルし、実行するための道具一式です。
JDK にはいくつかの配布元（ディストリビューション）があります。
この教材では、無償で使える次のどちらかを使います。

| ディストリビューション | 配布元 | 備考 |
|---|---|---|
| Amazon Corretto 17 | AWS | dev-environment の手順と CI はこちら。クラウドの実行環境とそろう |
| Eclipse Temurin 17 | Eclipse Adoptium | 代わりに使ってもよい（どちらも OpenJDK ベース） |

**`JAVA_HOME`** は、「JDK がどこに入っているか」を示す環境変数です。
Gradle や VS Code は、この変数を見て使う JDK を決めます。

**VS Code**（Visual Studio Code）は無償のエディタです。
拡張機能を入れると、Java の補完・デバッグ・テスト実行、Spring Boot アプリの起動などができます。

## なぜ必要か

- 本番と CI は Java {{ versions.java }} です。手元でも 17 以上の JDK が無いとビルドできません
- PC に複数の JDK が入っていると、`PATH` と `JAVA_HOME` が別の JDK を指して、思わぬ版で動くことがあります
- 拡張機能をチームでそろえると、画面の見え方や操作の説明が全員で共通になります

## どうやるか

### 1. JDK をインストールする

1. [Amazon Corretto 17 のダウンロードページ](https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/downloads-list.html) から、Windows x64 用の `.msi` を取得する
2. インストーラーを実行する。既定で `JAVA_HOME` と `PATH` が設定される
3. PowerShell を **開き直して** 確認する

```powershell
java -version
```

`openjdk version "17.0.x"` のように `17.` で始まれば OK です。

!!! note "21 が入っている場合"
    JDK 21 を使っていても、sample-app は `build.gradle` の設定で Java {{ versions.java }} 向けにコンパイルされます。
    ただし、迷いを減らすために 17 を入れておくことをおすすめします。

### 2. JAVA_HOME を確認する

```powershell
echo $env:JAVA_HOME
```

`C:\Program Files\Amazon Corretto\jdk17.x.x_x` のようなパスが表示されれば OK です。
空の場合や、別の JDK を指している場合は設定します。

1. スタートメニューで「環境変数」と検索し、「システム環境変数の編集」を開く
2. 「環境変数」→ ユーザー環境変数の「新規」で、変数名 `JAVA_HOME`、値に JDK のフォルダを入れる
3. `Path` に `%JAVA_HOME%\bin` があり、ほかの JDK の `bin` より上にあることを確認する
4. PowerShell を開き直し、`java -version` と `echo $env:JAVA_HOME` を再確認する

!!! failure "悪い例"
    `JAVA_HOME` に `C:\Program Files\Amazon Corretto\jdk17.x.x_x\bin` と `bin` まで書いてしまう。
    Gradle は `JAVA_HOME\bin\java` を探すため、`bin\bin\java` となって見つかりません。

!!! success "良い例"
    `JAVA_HOME` は JDK のフォルダ（`bin` の 1 つ上）にし、`Path` には `%JAVA_HOME%\bin` を書く。

Git Bash からも確認しておきます。

```bash
echo "$JAVA_HOME"
java -version
```

### 3. VS Code をインストールする

1. [VS Code](https://code.visualstudio.com/) のインストーラー（User Installer）を実行する
2. 「PATH への追加」にチェックを入れる（`code` コマンドが使えるようになる）

**確認**:

```powershell
code --version
```

### 4. 推奨の拡張機能を入れる

`dev-environment` リポジトリには、推奨する拡張機能の一覧 `.vscode/extensions.json` があります。

```json
{
  "recommendations": [
    "vscjava.vscode-java-pack",
    "vmware.vscode-boot-dev-pack",
    "github.copilot-chat",
    "hashicorp.terraform",
    "ms-azuretools.vscode-containers"
  ]
}
```

| 拡張機能 ID | 表示名 | 何に使うか |
|---|---|---|
| `vscjava.vscode-java-pack` | Extension Pack for Java | Java の補完・デバッグ・テスト実行・Gradle 連携 |
| `vmware.vscode-boot-dev-pack` | Spring Boot Extension Pack | Spring Boot アプリの起動、`application.yml` の補完 |
| `github.copilot-chat` | GitHub Copilot Chat | AI による補完とチャット（[10-06](10-06-copilot.md)） |
| `hashicorp.terraform` | HashiCorp Terraform | クラウド構成（`cloud/`）の編集 |
| `ms-azuretools.vscode-containers` | Container Tools | コンテナの状態やログを VS Code で見る |

入れ方は次のとおりです。

1. VS Code で `dev-environment` フォルダを開く（Git Bash で `code .`）
2. 右下に「推奨の拡張機能をインストールしますか」と出たら「インストール」を押す
3. 出ない場合は、拡張機能ビューで `@recommended` と検索し、表示された拡張機能を入れる

!!! tip "Java の拡張機能が使う JDK"
    Extension Pack for Java は `JAVA_HOME` の JDK を使います。
    `JAVA_HOME` を変えたら、VS Code を完全に終了してから開き直してください。

### 5. 動作を確かめる

1. VS Code で `sample-app/src/main/java/com/example/sample/SampleApplication.java` を開く
2. 右下のステータスバーに Java のプロジェクトの読み込み状況が表示される。初回は数分かかる
3. 読み込みが終わると、`main` メソッドの上に「Run | Debug」が表示される

ここではまだ起動しません。起動は DB を用意してから [10-05](10-05-run-sample-app.md) で行います。

## サンプルアプリでは

`sample-app/build.gradle` で、Java の版と文字コードを指定しています。

<!-- src: sample-app/build.gradle @main -->
```groovy
tasks.withType(JavaCompile).configureEach {
    options.release = 17
    options.encoding = 'UTF-8'
    options.compilerArgs += ['-parameters']
}
```

- `options.release = {{ versions.java }}`: どの JDK でビルドしても、Java {{ versions.java }} の API だけを使えるようにします
- `options.encoding = 'UTF-8'`: ソースの文字コードを UTF-8 に固定します。Windows の既定の文字コードに左右されません
- `-parameters`: メソッドの引数名をクラスファイルに残します。Spring がリクエストの値を引数に渡すときに使います

CI（`.github/workflows/ci.yml`）では、`actions/setup-java` で Corretto 17 を指定しています。
手元も Corretto 17 にしておけば、CI と同じ条件で確認できます。

## もし JAVA_HOME がなかったら？

`gradlew` は `JAVA_HOME` を見て Java を探します。
設定が無い、または古い JDK を指していると、ビルドが「Java が見つからない」「版が合わない」で失敗します。

さらに困るのは、`java -version` では 17 と出るのに、Gradle は別の JDK で動いている場合です。
エラーの原因が見えにくく、調査に時間がかかります。
`java -version` と `JAVA_HOME` の両方を確認する習慣をつけてください。

## 理解度チェック

1. `JAVA_HOME` には、JDK のどのフォルダを設定しますか。
2. JDK 21 を入れた PC でも、sample-app が Java {{ versions.java }} 向けにビルドされるのはなぜですか。
3. `options.encoding = 'UTF-8'` が無いと、Windows でどんな問題が起きる可能性がありますか。
4. 推奨の拡張機能の一覧は、どのファイルに書かれていますか。

??? note "答え"
    1. `bin` の 1 つ上の、JDK そのもののフォルダです（例: `C:\Program Files\Amazon Corretto\jdk17.x.x_x`）。
    2. `build.gradle` で `options.release = {{ versions.java }}` を指定しているからです。
    3. ソースの日本語（コメントや文字列）が、Windows の既定の文字コードで読まれて文字化けし、コンパイルエラーや表示の崩れが起きる可能性があります。
    4. `dev-environment/.vscode/extensions.json` です。

## コードを読むときの確認観点

- [ ] `build.gradle` の `options.release` と本番の Java の版が一致しているか
- [ ] ソースの文字コード（`options.encoding`）が指定されているか
- [ ] `.vscode/extensions.json` の拡張機能がすべて入っているか
- [ ] `java -version` と `JAVA_HOME` が同じ JDK を指しているか

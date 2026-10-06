# 10-04 コンテナとローカル環境

!!! abstract "到達目標"
    - コンテナとは何か、なぜ DB や S3 をコンテナで動かすのかを説明できる
    - Rancher Desktop を入れ、`docker compose` で DB と S3 エミュレータを起動できる
    - `.env` の役割と、秘密情報をコミットしない理由を説明できる
    - `docker-compose.yml` を読み、ポート・初期化 SQL・ヘルスチェックの意味を説明できる

## 何か

**コンテナ** は、アプリとその動作に必要なもの（OS の一部・ライブラリ・設定）をひとまとめにして、
どの PC でも同じように動かす仕組みです。
**イメージ** はコンテナの元になる「型」で、`postgres:16` のように名前と版（タグ）で指定します。

**Docker Compose** は、複数のコンテナの構成を `docker-compose.yml` に書き、
`docker compose up` の 1 コマンドでまとめて起動する道具です。

**Rancher Desktop** は、Windows でコンテナを動かすための無償のソフトです。
内部で WSL2（Windows 上の Linux 環境）を使い、`docker` コマンドを提供します。

ローカル環境では、次の 2 つのコンテナを動かします。

| サービス名 | イメージ | 代わりをするもの | ポート |
|---|---|---|---|
| `db` | `postgres:16` | クラウドの Aurora PostgreSQL | 5432 |
| `s3` | S3 互換エミュレータ（`.env` で差し替え可） | クラウドの S3 | 9090 |

## なぜ必要か

- DB を PC に直接インストールすると、版がそろわず、アンインストールも面倒です。コンテナなら全員が同じ版を使えます
- クラウドの S3 に PC から接続すると、費用・権限・誤操作のリスクがあります。エミュレータなら安全に試せます
- データを壊しても、コマンド 1 つで初期状態から作り直せます
- CI でも同じ `docker-compose.yml` で起動を確認しているため、手元と CI の差が小さくなります

## どうやるか

### 1. WSL2 を有効にする

管理者権限の PowerShell で次を実行し、PC を再起動します。

```powershell
wsl --install --no-distribution
```

**確認**: `wsl --status` で「既定のバージョン: 2」と表示される。

!!! warning "仮想化が無効な場合"
    BIOS で仮想化（Intel VT-x / AMD-V）が無効だと失敗します。
    社用 PC で変更できない場合は、情報システム部門に相談してください。

### 2. Rancher Desktop を入れる

1. [Rancher Desktop](https://rancherdesktop.io/) のインストーラーを実行する
2. 初回起動の設定で **Container Engine を「dockerd (moby)」** にする（`docker` コマンドを使うため）
3. Kubernetes は使わないので無効にしてよい（メモリの節約）
4. Preferences → Virtual Machine でメモリを 4GB 以上にする

**確認**（新しく開いた PowerShell で）:

```powershell
docker version
docker compose version
```

!!! failure "悪い例"
    Container Engine を「containerd」のままにする。
    `docker` コマンドが無く、`docker: command not found` になります。

!!! success "良い例"
    Container Engine を「dockerd (moby)」にし、ターミナルを開き直してから `docker version` を確認する。

### 3. .env を作る

`local` フォルダで、見本の `.env.example` をコピーして `.env` を作ります。

```bash
cd /c/work/dev-environment/local
cp .env.example .env            # PowerShell なら: Copy-Item .env.example .env
```

`.env.example` の中身は次のとおりです。

<!-- src: local/.env.example @main -->
```text
# コピーして .env を作る（.env はコミットしない）
DB_NAME=sampledb
DB_USER=app
DB_PASSWORD=localpass
DB_PORT=5432
S3_PORT=9090
S3_BUCKET=sample-bucket
# S3_EMULATOR_IMAGE=<your-registry>/<s3-emulator>:<tag>
```

`docker compose` は、同じフォルダの `.env` を自動で読み込み、`docker-compose.yml` の `${DB_PASSWORD}` などに当てはめます。

!!! danger "秘密情報は .env だけに書く"
    パスワードやアクセスキーは `.env` にだけ書きます。`.env` は `.gitignore` でコミット対象外です。
    `docker-compose.yml` やソース、`.env.example` に本物の値を書かないでください。
    `.env.example` には、ローカル専用のダミー値だけを置きます。

### 4. DB と S3 エミュレータを起動する

```bash
docker compose up -d --wait
```

- `-d`: バックグラウンドで起動する（ターミナルを占有しない）
- `--wait`: すべてのコンテナが healthy（正常に応答する状態）になるまで待つ

初回はイメージのダウンロードがあるため、数分かかります。

**確認**:

```bash
docker compose ps
```

`db` と `s3` の STATUS が `healthy` なら OK です。

### 5. 初期データを確認する

DB には、初回起動時に `local/db/init/` の SQL が実行され、テーブルと会員 2 件が入ります。

```bash
docker compose exec db psql -U app -d sampledb -c "SELECT id, name, email FROM member;"
```

会員 2 件（架空の名前）が表示されれば OK です。`psql` を抜けるコマンドは不要です（`-c` で 1 回だけ実行しています）。

### 6. サンプルの CSV を S3 エミュレータに置く

注文ファイル取込バッチ（JOB0001）の入力ファイルを、S3 エミュレータに置いておきます。
AWS CLI は不要で、HTTP の PUT でアップロードします。

```bash
./scripts/upload-sample.sh          # Git Bash
```

```powershell
.\scripts\upload-sample.ps1         # PowerShell
```

`uploaded: s3://sample-bucket/orders.csv` と表示されれば OK です。
このファイルは [10-05](10-05-run-sample-app.md) でバッチの入力に使います。

### 7. 日々の起動と停止

| やりたいこと | コマンド（`local` フォルダで） |
|---|---|
| 起動 | `docker compose up -d --wait` |
| 停止（データは残る） | `docker compose stop` |
| 状態を見る | `docker compose ps` |
| ログを見る | `docker compose logs -f db` |
| DB に入る | `docker compose exec db psql -U app -d sampledb` |
| データを消して作り直す | `docker compose down -v && docker compose up -d --wait` |

!!! warning "`down -v` はデータを消します"
    `-v` を付けると、DB のデータを保存しているボリュームも削除されます。
    初期データからやり直したいときだけ使ってください。

## サンプルアプリでは

`local/docker-compose.yml` の `db` サービスを読んでみます。

<!-- src: local/docker-compose.yml @main -->
```yaml
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${DB_NAME:-sampledb}
      POSTGRES_USER: ${DB_USER:-app}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-localpass}
      TZ: Asia/Tokyo
    ports:
      - "${DB_PORT:-5432}:5432"
    volumes:
      - db-data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro   # 初回起動時だけ実行される
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 20
```

- `${DB_NAME:-sampledb}`: `.env` に `DB_NAME` があればその値、無ければ `sampledb` を使います
- `ports`: 左が PC 側、右がコンテナ側のポートです。PC の 5432 番でコンテナの DB に接続できます
- `volumes` の 1 行目: DB のデータを名前付きボリューム `db-data` に保存します。コンテナを作り直してもデータが残ります
- `volumes` の 2 行目: `db/init` フォルダを、PostgreSQL のイメージが初回だけ実行する場所に読み取り専用でつなぎます
- `healthcheck`: `pg_isready` で DB が接続を受け付けるかを 5 秒ごとに確かめます。`--wait` はこの結果を待ちます

初期化の SQL は 2 つです。

- `local/db/init/01_schema.sql`: `member` と `orders` テーブルを作る
- `local/db/init/02_data.sql`: 動作確認用の会員 2 件を入れる

アプリ側は、`sample-app/src/main/resources/application.yml` で接続先を決めています。

<!-- src: sample-app/src/main/resources/application.yml @main -->
```yaml
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/sampledb}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:}
```

`application-local.yml` では、パスワードの既定値を `localpass` にし、S3 の接続先をエミュレータ（`http://localhost:9090`）にしています。

!!! note "`.env` の値を変えたとき"
    `.env` を読むのは `docker compose` だけで、sample-app は読みません。
    `DB_PORT` や `DB_PASSWORD` を変えた場合は、アプリを起動するターミナルで
    環境変数 `DB_URL`・`DB_PASSWORD`・`S3_ENDPOINT` も合わせて設定してください。

## もしコンテナがなかったら？

各自が PostgreSQL を PC に直接インストールすることになり、版や設定が人によって違ってきます。
「初期データを入れ直したい」ときも、手作業で SQL を流し直す必要があります。

S3 については、クラウドの本物のバケットに PC から接続することになります。
アクセスキーを PC に置くことになり、漏えいや誤削除のリスクが生まれます。
コンテナとエミュレータを使えば、安全に、何度でも同じ状態から始められます。

## 理解度チェック

1. `docker compose up -d --wait` の `--wait` は何を待ちますか。
2. `local/db/init/` の SQL が「初回起動時だけ」実行されるのはなぜですか。もう一度実行させるにはどうしますか。
3. `"${DB_PORT:-5432}:5432"` の左右の 5432 は、それぞれ何のポートですか。
4. `.env` に書いたパスワードがコミットされないのはなぜですか。
5. `docker compose stop` と `docker compose down -v` の違いは何ですか。

??? note "答え"
    1. 各サービスの `healthcheck` が成功し、`healthy` になるのを待ちます。
    2. PostgreSQL のイメージは、データの保存先が空のときだけ `/docker-entrypoint-initdb.d` の SQL を実行するからです。`docker compose down -v` でボリュームを消してから `up` し直すと、再び実行されます。
    3. 左が PC 側のポート、右がコンテナの中の PostgreSQL のポートです。
    4. `dev-environment` の `.gitignore` に `.env` が書かれているからです。
    5. `stop` はコンテナを止めるだけでデータは残ります。`down -v` はコンテナとボリュームを削除するため、DB のデータも消えます。

## コードを読むときの確認観点

- [ ] `docker-compose.yml` にパスワードなどの本物の値が直接書かれていないか（`${...}` で `.env` から渡しているか）
- [ ] `ports` の PC 側の番号が、ほかのソフトと重なっていないか
- [ ] `healthcheck` があり、`--wait` で起動完了を待てるか
- [ ] 初期化 SQL のテーブル定義と、アプリの Mapper の SQL が対応しているか
- [ ] アプリの接続先（`application.yml` の `DB_URL` など）と `.env` の値がそろっているか

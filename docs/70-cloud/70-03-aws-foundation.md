# 70-03 AWS の基礎（リージョン・IAM・VPC）

!!! abstract "到達目標"
    - リージョン・AZ・責任共有モデルを説明し、マルチ AZ が可用性の基本である理由を説明できる
    - IAM のユーザー・ロール・ポリシーの違いと、アプリにロールを使う理由を説明できる
    - VPC・public / private サブネット・NAT ゲートウェイ・VPC エンドポイントの役割を説明できる
    - セキュリティグループとネットワーク ACL の違いを説明し、通信の許可を読める

## 何か

AWS の設計は、まず次の 3 つを決めることから始まります。

| 決めること | AWS での仕組み |
| --- | --- |
| どこに置くか | リージョン・アベイラビリティゾーン（AZ） |
| 誰が何を触れるか | IAM（Identity and Access Management） |
| どう通信するか | VPC（Virtual Private Cloud） |

### リージョンと AZ

| 単位 | 中身 | 設計での意味 |
| --- | --- | --- |
| リージョン | 地理的に離れたデータセンター群（東京は `ap-northeast-1`、大阪は `ap-northeast-3`） | データの置き場所（法令）、応答の速さ、DR 先 |
| AZ | リージョンの中の、独立したデータセンター群。1 リージョンに通常 3 つ以上 | 1 つの AZ が止まっても動くように、2 つ以上の AZ に置く |
| エッジロケーション | CloudFront などが使う配信の拠点 | 静的なファイルを、利用者の近くから配る |

### 責任共有モデル

AWS は「クラウド **の** セキュリティ」（建物・機器・仮想化の基盤）に責任を持ちます。
利用者は「クラウド **の中の** セキュリティ」（OS・データ・権限の設定・暗号化）に責任を持ちます。
マネージドサービス（DB や Fargate など）ほど、利用者の責任の範囲は小さくなります。

### IAM

| 要素 | 役割 | ポイント |
| --- | --- | --- |
| ルートユーザー | アカウントを作ったときの、すべての権限を持つユーザー | 多要素認証を設定し、普段は使わない |
| IAM ユーザー | 人やプログラムの、長く使う ID | 人の利用は IAM Identity Center（シングルサインオン）に寄せるのが今の主流 |
| IAM グループ | ユーザーの束 | 権限はグループに付ける |
| IAM ロール | 一時的に「なりかわって」使う権限 | EC2・ECS・Lambda には、アクセスキーではなくロールを付ける |
| ポリシー | 許可・拒否を JSON で書いたもの | 明示的な拒否 ＞ 明示的な許可 ＞ 何も書かなければ拒否 |

複数のアカウントは **AWS Organizations** でまとめます。
**SCP**（サービスコントロールポリシー）で「このアカウントでは東京リージョン以外を使わせない」のような上限をかけます。

### VPC

VPC は、AWS の中に作る自分専用のネットワークです。

| 部品 | 役割 |
| --- | --- |
| VPC | 自分専用のネットワーク空間（例: `10.0.0.0/16`） |
| サブネット | VPC を区切ったもの。**AZ ごとに作る**。外への経路があるものを public、無いものを private と呼ぶ |
| インターネットゲートウェイ | VPC とインターネットの出入口 |
| NAT ゲートウェイ | private サブネットから、外へ出る通信だけを通す。費用が高めなので注意 |
| ルートテーブル | サブネットごとの経路の表 |
| セキュリティグループ | 部品（インスタンス・タスク）ごとのファイアウォール |
| ネットワーク ACL | サブネットごとのファイアウォール |
| VPC エンドポイント | インターネットを通らずに S3 などへつなぐ |

## なぜ必要か

この 3 つの設計を誤ると、後からは直しにくい問題になります。

- 1 つの AZ にしか置かないと、その AZ の障害で全体が止まる
- アクセスキーをコードや設定ファイルに書くと、漏れたときに誰でも AWS を操作できる
- DB を public サブネットに置くと、インターネットから直接に攻撃を受ける

AWS の設計の試験問題の多くも、「どこに置くか・誰が触れるか・どう通信するか」の理解で解けます。
サービスの名前を覚える前に、この土台を押さえてください。

## どうやるか

### アプリにはロールを使う

!!! failure "悪い例"
    例: アプリの設定ファイルに、IAM ユーザーのアクセスキーを書く。

    ```properties
    # 例: sample-app には無い設定
    app.aws.access-key=AKIA................
    app.aws.secret-key=................
    ```

    設定ファイルが漏れると、そのキーで誰でも AWS を操作できます。
    キーは期限が無いので、気付くまで使われ続けます。

!!! success "良い例"
    EC2・ECS のタスクに IAM ロールを付け、SDK の標準の認証情報の仕組みに任せる。
    ロールの認証情報は一時的なもので、AWS が自動で入れ替えます。
    コードにも設定にも、キーは書きません。

ロールに付ける権限は、**必要な操作と、必要な対象だけ** にします（最小権限）。

### サブネットを AZ ごとに分ける

典型的な形は、VPC を 2 つ以上の AZ にまたがって作り、AZ ごとに public と private のサブネットを置く形です。

| 置き場所 | 置くもの |
| --- | --- |
| public サブネット | ロードバランサー、NAT ゲートウェイ |
| private サブネット | アプリのサーバー・コンテナ、DB、キャッシュ |

外部から直接に届く必要があるもの以外は、private に置きます。
private から外に出る必要があるとき（OS の更新、イメージの取得）は、NAT ゲートウェイか VPC エンドポイントを使います。

### セキュリティグループとネットワーク ACL を使い分ける

| 項目 | セキュリティグループ | ネットワーク ACL |
| --- | --- | --- |
| 単位 | 部品（インスタンス・タスク）ごと | サブネットごと |
| 書けるルール | 許可だけ | 許可と拒否 |
| 状態 | ステートフル（行きを許可すれば、戻りは自動で通る） | ステートレス（戻りの通信も許可が必要） |
| 評価 | すべてのルールを見る | 番号の小さい順に見て、最初に合ったもの |

普段はセキュリティグループで制御し、ネットワーク ACL は大まかな遮断に使います。
セキュリティグループは、IP アドレスではなく **相手のセキュリティグループ** を指定できます。
「アプリのグループからだけ DB に入れる」と書けるので、台数が増減しても設定を変えずに済みます。

### VPC どうし・社内とつなぐ

| 方法 | 内容 |
| --- | --- |
| VPC ピアリング | VPC を 1 対 1 でつなぐ。推移しない（A-B、B-C がつながっていても A-C は通らない） |
| Transit Gateway | 多数の VPC と社内のネットワークを、中心の 1 か所で束ねる |
| Site-to-Site VPN | インターネットの上に暗号化した通り道を作る。すぐに作れて安い |
| Direct Connect | 専用線。帯域と安定性を重視するとき |

名前の解決（DNS）は **Route 53** が担います。
ヘルスチェックと組み合わせた「フェイルオーバー」の設定は、DR の構成でよく使います。

## サンプルアプリでは

### 2 つの AZ に、public と private のサブネット

`cloud/modules/network/main.tf` は、2 つの AZ に public と private のサブネットを 1 つずつ作ります。

```hcl title="cloud/modules/network/main.tf（6〜32 行目）"
locals {
  azs = slice(data.aws_availability_zones.this.names, 0, 2)
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name}-vpc" }
}

resource "aws_subnet" "public" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr_block, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.name}-public-${count.index}" }
}

resource "aws_subnet" "private" {
  count             = length(local.azs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index + 10)
  availability_zone = local.azs[count.index]
  tags              = { Name = "${var.name}-private-${count.index}" }
}
```

| 行 | 意味 |
| --- | --- |
| `slice(..., 0, 2)` | 使える AZ のうち、最初の 2 つを使う |
| `cidrsubnet(var.cidr_block, 8, count.index)` | `10.0.0.0/16` を `/24` に区切る。public は `10.0.0.0/24` と `10.0.1.0/24` |
| `count.index + 10` | private は `10.0.10.0/24` と `10.0.11.0/24` |
| `map_public_ip_on_launch = false` | public サブネットでも、自動で公開の IP を付けない |

API とバッチは private サブネットに置かれます（`environments/prod/main.tf` の `subnet_ids = module.network.private_subnet_ids`）。
ECS のサービスも `assign_public_ip = false` で、外から直接は届きません。

### 2 つのロール（実行ロールとタスクロール）

`cloud/modules/ecs-service/main.tf` は、ECS のタスクに 2 種類のロールを作ります。

```hcl title="cloud/modules/ecs-service/main.tf（29〜33 行目、55〜59 行目）"
# イメージ取得・ログ出力・シークレット読み出し用（ECS が使う）
resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# アプリが AWS を使う権限（S3・SQS など）。必要な権限だけを task_policy_json で渡す
resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}
```

| ロール | 使う人 | 権限の例 |
| --- | --- | --- |
| 実行ロール（execution） | ECS 自身 | イメージの取得、ログの出力、DB パスワードの読み出し |
| タスクロール（task） | アプリのコード | S3 の読み書き、SQS の送受信 |

アプリ側の受け取り方は、`sample-app/src/main/java/com/example/sample/order/batch/S3Config.java` です。

```java title="sample-app/src/main/java/com/example/sample/order/batch/S3Config.java（29〜36 行目）"
        S3ClientBuilder b = S3Client.builder().region(Region.of(region));
        if (endpoint.isBlank()) {
            b.credentialsProvider(DefaultCredentialsProvider.builder().build());
        } else {
            b.endpointOverride(URI.create(endpoint))
                    .forcePathStyle(true)
                    .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(accessKey, secretKey)));
        }
```

クラウドでは `app.s3.endpoint` を指定しないので、`DefaultCredentialsProvider` が使われます。
これがタスクロールの一時的な認証情報を自動で取り出します。
コードにも設定にも、本物のアクセスキーはありません（`test` はローカルのエミュレータ用です）。

### セキュリティグループで「アプリからだけ」DB に入れる

```hcl title="cloud/modules/aurora-postgres/main.tf（13〜20 行目）"
resource "aws_vpc_security_group_ingress_rule" "from_app" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
```

IP アドレスではなく、API とバッチのセキュリティグループ（`referenced_security_group_id`）を指定しています。
コンテナの数や IP が変わっても、このルールは変えずに済みます。

## もし VPC とロールの設計がなかったら？

DB を public サブネットに置き、パスワードをアプリの設定ファイルに書いたとします。
設定ファイルがリポジトリに混ざって公開されると、インターネットのどこからでも DB に接続を試せます。
実際に、公開されたキーを数分のうちに見つけて悪用する仕組みが、外部には常に動いています。

private サブネット、セキュリティグループ、ロールの 3 つがあれば、
仮に設定ファイルが漏れても、外からは DB に届かず、使えるキーもありません。
これが「多層防御」です。

## 理解度チェック

1. 東京リージョンの 1 つの AZ だけで構成したシステムの弱点を答えてください。

    ??? note "答え"
        その AZ が止まると、システム全体が止まる点です。
        2 つ以上の AZ に、アプリと DB を分けて置くのが基本です。

2. EC2 のアプリが S3 を使うとき、アクセスキーではなくロールを使う理由を 2 つ答えてください。

    ??? note "答え"
        ロールの認証情報は一時的で、AWS が自動で入れ替える点です。
        また、コードや設定にキーを書かないので、漏れる場所が無い点です。

3. セキュリティグループで戻りの通信を許可しなくてよいのはなぜですか。

    ??? note "答え"
        セキュリティグループはステートフルで、許可した通信の戻りは自動で通すからです。
        ネットワーク ACL はステートレスなので、戻りの通信も許可が必要です。

4. sample-app の dev1 環境は NAT ゲートウェイがありません。private サブネットのコンテナが S3 を使うには、何が必要ですか。

    ??? note "答え"
        S3 用の VPC エンドポイント（ゲートウェイ型）です。
        インターネットを通らずに S3 へ届き、NAT ゲートウェイも不要になります。

5. VPC A・B・C を、A-B、B-C の VPC ピアリングでつなぎました。A から C に届きますか。

    ??? note "答え"
        届きません。VPC ピアリングは推移しないからです。
        A-C も直接つなぐか、多数の VPC をつなぐなら Transit Gateway を使います。

## コードを読むときの確認観点

- [ ] アプリ・DB が private サブネットに置かれ、公開の IP が付いていないか
- [ ] サブネットが 2 つ以上の AZ に作られているか
- [ ] コード・設定ファイル・環境変数に、アクセスキーやパスワードが書かれていないか
- [ ] IAM ポリシーの `Action` と `Resource` が、必要な範囲だけになっているか（`*` が無いか）
- [ ] セキュリティグループが、IP ではなく相手のグループで許可しているか（`0.0.0.0/0` からの受信が無いか）

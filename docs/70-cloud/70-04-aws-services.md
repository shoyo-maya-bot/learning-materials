# 70-04 AWS の主要サービス

!!! abstract "到達目標"
    - コンピュート（EC2・ECS / Fargate・Lambda）を、要件に合わせて選べる
    - ストレージ（S3・EBS・EFS）と S3 のストレージクラスの違いを説明できる
    - RDS のマルチ AZ とリードレプリカの目的の違いを説明できる
    - SQS・SNS・EventBridge・Step Functions を使い分けられる
    - CloudWatch・CloudTrail・Config が、それぞれ何を記録するかを説明できる

## 何か

AWS には 200 を超えるサービスがあります。
すべてを覚える必要はありません。
業務システムでよく使うサービスを、次の 3 点で覚えます。

1. 何をするか
2. いつ選ぶか
3. 似たサービスとの違い

資格試験の問題も、ほとんどが 3 つ目の「似たものとの違い」を問います。

## なぜ必要か

サービスの選び方で、運用の手間と費用が大きく変わります。
たとえば、同じ Web アプリを動かすにも、EC2 なら OS の更新や修正の適用を自分たちで行います。
Fargate なら、サーバーの管理は AWS に任せられます。

選び方を知らないと、「慣れているから」という理由だけで手間のかかる構成を選びがちです。
各サービスの得意・不得意を知り、要件に合わせて選べるようにします。

## どうやるか

### コンピュート

| サービス | 何をするか | いつ選ぶか |
| --- | --- | --- |
| EC2 | 仮想サーバー | OS から自由に管理したい、既存のアプリをそのまま載せたい |
| EC2 Auto Scaling | 負荷や時刻で、台数を自動で増減する | Web サーバーの可用性と費用の最適化（最低 2 台・マルチ AZ） |
| ELB（ALB / NLB） | ロードバランサー | ALB: HTTP / HTTPS、パスやホスト名で振り分け。NLB: TCP / UDP、高性能、固定 IP |
| ECS / EKS | コンテナを動かす（EKS は Kubernetes） | コンテナ化したアプリ。Kubernetes が必要なら EKS |
| Fargate | コンテナを動かすサーバーを、AWS が管理する | ECS / EKS で、サーバーの管理をしたくない |
| Lambda | 出来事をきっかけに関数を動かす（サーバーレス） | 短い処理（最大 15 分）、負荷の波が大きい |

EC2 の買い方は、費用の問題でよく問われます。

| 買い方 | 内容 | 向いている使い方 |
| --- | --- | --- |
| オンデマンド | 使った分だけ払う | 短期、予測できない負荷 |
| Savings Plans / リザーブドインスタンス | 1 年か 3 年の利用を約束して割り引く | 常に動いている本番 |
| スポットインスタンス | AWS の余った容量を大きく割り引いて使う。中断されることがある | 中断されてもよいバッチ、CI |
| ハードウェア専有 | 物理サーバーを占有する | ライセンスや規制で必要なとき |

### ストレージ

| サービス | 種類 | ポイント |
| --- | --- | --- |
| S3 | オブジェクトストレージ | 耐久性 99.999999999%。バックアップ、静的なサイト、データの置き場 |
| EBS | ブロックストレージ（EC2 のディスク） | 1 つの AZ に属する。スナップショットは別の AZ・リージョンに戻せる |
| EFS | 共有のファイルシステム（Linux） | 複数の EC2 から同時に使える。マルチ AZ |
| FSx | Windows のファイルサーバーなど | Windows の共有フォルダが必要なとき |

S3 は、使う頻度に合わせて **ストレージクラス** を選びます。

| クラス | 向いているデータ |
| --- | --- |
| Standard | よく使う |
| Standard-IA | たまにしか使わないが、すぐ取り出したい |
| Glacier 系 | ほとんど使わない保管用。取り出しに時間がかかるものもある |
| Intelligent-Tiering | 使う頻度が読めない（自動で移す） |

**ライフサイクルルール** を設定すると、「30 日後に IA、1 年後に Glacier」のように自動で移せます。

### データベース

| サービス | 種類 | いつ選ぶか |
| --- | --- | --- |
| RDS | マネージドの RDB（PostgreSQL・MySQL・Oracle・SQL Server など） | 一般的な業務システム |
| Aurora | AWS 独自の高性能な RDB（PostgreSQL / MySQL 互換） | 高い性能と可用性。データを 3 つの AZ に 6 重に保存 |
| DynamoDB | NoSQL（キーと値） | 大量のアクセスに一定の速さで応答したい |
| ElastiCache | メモリ上のキャッシュ（Redis など） | DB の負荷を減らす、セッションを置く |
| Redshift | データウェアハウス | 大量のデータの集計・分析 |

RDS では、次の 2 つの違いが最もよく問われます。

| 項目 | マルチ AZ | リードレプリカ |
| --- | --- | --- |
| 目的 | **可用性**（止まらない） | **読み取りの性能** |
| 複製の方法 | 別の AZ に同期で複製 | 非同期で複製 |
| 障害のとき | 自動で切り替わる | 自動では切り替わらない（手動で昇格） |
| 読み取りに使えるか | 従来の構成では使えない | 使える。別のリージョンにも置ける |

!!! failure "悪い例"
    会員の検索が多く、DB の CPU 使用率が高い。
    「DB を強くしたい」と考え、マルチ AZ を有効にする。
    待機側は読み取りに使えないので、費用だけが増え、検索は速くなりません。

!!! success "良い例"
    検索（読み取り）はリードレプリカに向け、更新だけをプライマリに送る。
    同じ検索が繰り返されるなら、結果を ElastiCache にキャッシュする。
    止まらないことが要件なら、それとは別にマルチ AZ も有効にする。

### メッセージングと連携

| サービス | 何をするか | 使い分け |
| --- | --- | --- |
| SQS | キュー | 送り手と受け手を切り離す。受け手のペースで処理（[40-02](../40-async/40-02-queue-retry-idempotency.md)） |
| SNS | 通知（Pub/Sub） | 1 つのメッセージを、複数の宛先に一斉に配る |
| EventBridge | イベントの振り分け | AWS の出来事やスケジュールを、ルールで宛先に流す |
| Step Functions | ワークフロー | 複数の処理を、順番・分岐・再試行つきでつなぐ |
| Kinesis | ストリーミング | ログやクリックなど大量のデータを、流れのまま処理する |
| API Gateway | API の入口 | Lambda などの前に置き、認証や流量の制限をかける |

定番の組み合わせは、**SNS から複数の SQS へ配る（ファンアウト）** 形です。
1 つの「注文が入った」という通知を、在庫・配送・メールの各処理が、それぞれのキューで受け取れます。

### 監視・セキュリティ・運用

| サービス | 役割 |
| --- | --- |
| CloudWatch | メトリクス・ログ・アラーム。**性能と状態** を見る |
| CloudTrail | 誰がいつどの API を呼んだか。**操作** の記録 |
| AWS Config | リソースの設定の変更履歴と、ルール違反の検出。**設定** の記録 |
| GuardDuty | 怪しいアクセスなどの脅威を検出する |
| KMS | 暗号化の鍵を管理する |
| Secrets Manager | パスワードなどの秘密情報を保管し、自動で入れ替える |
| WAF / Shield | Web アプリへの攻撃を防ぐ / DDoS 攻撃を防ぐ |
| Systems Manager | パッチの適用や、SSH を使わないログイン（Session Manager） |

## サンプルアプリでは

dev-environment の `cloud/` には、同じ sample-app を動かす 2 つの構成があります。

| 構成 | 場所 | コンピュート | DB | 用途 |
| --- | --- | --- | --- | --- |
| 簡易環境 | `cloud/simple/` | EC2 1 台 | RDS PostgreSQL 1 台 | 試作・短期の検証 |
| 本格環境 | `cloud/environments/` | ECS Fargate | Aurora PostgreSQL | 開発・検証・本番 |

### 簡易環境: EC2 と RDS

<!-- src: cloud/simple/main.tf#L110-L124 @main -->
```hcl title="cloud/simple/main.tf（110〜124 行目）"
resource "aws_db_instance" "db" {
  identifier                  = "${var.system_name}-postgres"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  db_name                     = "sampledb"
  username                    = "app_admin"
  manage_master_user_password = true
  vpc_security_group_ids      = [aws_security_group.db.id]
  storage_encrypted           = true
  publicly_accessible         = false
  skip_final_snapshot         = true
  backup_retention_period     = 1
}
```

`multi_az` の指定が無いので、DB は 1 つの AZ だけにあります。
バックアップも 1 日分で、削除時の最終スナップショットも取りません。
試作用なので、可用性より費用と手軽さを優先した構成です。

`manage_master_user_password = true` は、パスワードを Secrets Manager に作らせる設定です。
パスワードは Terraform のコードにも、状態ファイルにも書かれません。
EC2 のロールには、このシークレットだけを読む権限（`secretsmanager:GetSecretValue` など）を付けています。
アプリの接続設定を作るときに、EC2 の中からパスワードを読むためです。

EC2 には SSH の鍵を使わず、Session Manager で入ります。

<!-- src: cloud/simple/main.tf#L69-L72,L94-L94,L101-L103 @main -->
```hcl title="cloud/simple/main.tf（69〜72 行目と、94〜103 行目の抜粋）"
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.web.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_instance" "web" {
  # （中略）
  metadata_options {
    http_tokens = "required"
  }
```

`http_tokens = "required"` は、EC2 のメタデータ（ロールの認証情報など）の取得に、
トークンを必須にする設定（IMDSv2）です。
アプリの脆弱性を使って認証情報を盗まれる攻撃を防ぎます。

### 本格環境: S3 と SQS

S3 のバケットは、公開の遮断・暗号化・バージョニングを有効にしています。

<!-- src: cloud/modules/s3-bucket/main.tf#L7-L13,L24-L29 @main -->
```hcl title="cloud/modules/s3-bucket/main.tf（7〜13 行目、24〜29 行目）"
resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

バージョニングがあると、ファイルを上書き・削除しても前の版に戻せます。
一方で、ライフサイクルルールはありません。
古い版や取込済みのファイルが、ずっと Standard クラスで残り続けます（理解度チェックの 5 問目）。

SQS は、デッドレターキュー付きです。

<!-- src: cloud/modules/sqs-queue/main.tf#L8-L16 @main -->
```hcl title="cloud/modules/sqs-queue/main.tf（8〜16 行目）"
resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}
```

既定値は、可視性タイムアウト 300 秒、最大受信回数 5（5 回受信しても成功しなければ、次の受信の代わりにデッドレターキューへ移す）、です。
ログは CloudWatch Logs に送られ、30 日で消えます（`cloud/modules/ecs-service/variables.tf` の `log_retention_days`）。

## もしサービスの違いを知らなかったら？

読み取りが多くて DB が遅いので、RDS のマルチ AZ を有効にしたとします。
費用は約 2 倍になりましたが、速さは変わりませんでした。
マルチ AZ の待機側は、従来の構成では読み取りに使えないからです。
必要だったのは、リードレプリカかキャッシュでした。

名前が似ているサービスほど、目的が違います。
目的を知らずに選ぶと、費用だけが増えて問題は解決しません。

## 理解度チェック

1. 夜間に 2 時間かかる集計バッチがあり、途中で止まってもやり直せます。最も費用の安いコンピュートの買い方は何ですか。

    ??? note "答え"
        スポットインスタンス（または Fargate Spot）です。
        中断されることがありますが、やり直せる処理なら大きく費用を下げられます。

2. 複数の Linux サーバーから、同じファイルを同時に読み書きしたいときに使うサービスは何ですか。

    ??? note "答え"
        EFS です。
        EBS は 1 つの AZ の 1 台の EC2 に付けるディスクなので、共有には向きません。

3. RDS のマルチ AZ とリードレプリカの目的を、それぞれ一言で答えてください。

    ??? note "答え"
        マルチ AZ は可用性、リードレプリカは読み取りの性能です。

4. 「誰が本番の DB のセキュリティグループを変更したか」を調べるには、どのサービスを見ますか。

    ??? note "答え"
        CloudTrail です。API の操作の記録が残ります。
        変更前後の設定の内容は、AWS Config で確かめられます。

5. sample-app の S3 バケットにライフサイクルルールを足すとしたら、どのようなルールが考えられますか。

    ??? note "答え"
        例: 取込済みのファイルを 30 日後に Standard-IA、1 年後に Glacier へ移す。
        古い版（バージョニングで残った版）は 90 日で消す。
        保持の期間は、運用・監査の要件に合わせて決めます。

## コードを読むときの確認観点

- [ ] DB に `multi_az`（Aurora なら 2 台以上のインスタンス）が、要件どおり設定されているか
- [ ] S3 バケットに、公開の遮断・暗号化・ライフサイクルルールがあるか
- [ ] SQS にデッドレターキューがあり、可視性タイムアウトが処理時間より長いか
- [ ] パスワードが Secrets Manager などで管理され、コードや変数に直接書かれていないか
- [ ] ログの保持期間が、運用・監査の要件と合っているか
- [ ] EC2 を使う場合、IMDSv2 が必須になっているか、SSH の代わりに Session Manager を使っているか

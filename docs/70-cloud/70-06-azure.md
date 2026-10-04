# 70-06 Azure（AWS との対応）

!!! abstract "到達目標"
    - AWS の主要サービスに対応する Azure のサービスを答えられる
    - 管理グループ・サブスクリプション・リソースグループの階層と、権限の継承を説明できる
    - Microsoft Entra ID と Azure RBAC の違い、マネージド ID の役割を説明できる
    - ストレージアカウントの冗長性（LRS・ZRS・GRS・GZRS）を、要件に合わせて選べる

## 何か

**Azure** は、Microsoft のクラウドです。
[70-02](70-02-architecture-basics.md) の設計の考え方（単一障害点・ステートレス・疎結合）は、Azure でもそのまま使えます。
違うのは、サービスの名前と、**Microsoft 365 や Active Directory との統合が前提** になっている点です。
社内で Microsoft 365 を使っている組織では、ID の管理をそろえやすいので、Azure が選ばれることがよくあります。

AWS で学んだことを土台に、対応表で覚えるのが近道です。

| 分類 | AWS | Azure |
| --- | --- | --- |
| 拠点 | リージョン / AZ | リージョン / 可用性ゾーン（＋リージョンのペア） |
| ID・権限 | IAM / IAM Identity Center | Microsoft Entra ID ＋ Azure RBAC |
| アカウントの管理 | Organizations / SCP | 管理グループ / サブスクリプション / Azure Policy |
| リソースのまとまり | （タグ、CloudFormation のスタック） | **リソースグループ**（すべてのリソースが必ずどれかに属する） |
| 仮想サーバー | EC2 | Virtual Machines |
| 自動の増減 | EC2 Auto Scaling | Virtual Machine Scale Sets |
| L7 のロードバランサー | ALB | Application Gateway（WAF を付けられる） |
| L4 のロードバランサー | NLB | Azure Load Balancer |
| 世界への配信と CDN | CloudFront | Azure Front Door |
| DNS | Route 53 | Azure DNS / Traffic Manager |
| Web アプリの実行（PaaS） | Elastic Beanstalk | **App Service** |
| 関数 | Lambda | Azure Functions |
| コンテナ | ECS / Fargate / EKS | Container Apps / Container Instances / AKS |
| ネットワーク | VPC / サブネット | Virtual Network（VNet）/ サブネット |
| ファイアウォール | セキュリティグループ / ネットワーク ACL | NSG（ネットワークセキュリティグループ）/ Azure Firewall |
| 社内との接続 | VPN / Direct Connect | VPN Gateway / ExpressRoute |
| ネットワークどうしの接続 | VPC ピアリング / Transit Gateway | VNet ピアリング / Virtual WAN |
| サービスへの閉じた接続 | VPC エンドポイント | プライベートエンドポイント / サービスエンドポイント |
| オブジェクトストレージ | S3 | Blob Storage（ストレージアカウントの中） |
| ディスク | EBS | マネージドディスク |
| ファイル共有 | EFS / FSx | Azure Files |
| RDB | RDS / Aurora | Azure SQL Database / Azure Database for PostgreSQL・MySQL |
| NoSQL | DynamoDB | Cosmos DB |
| キャッシュ | ElastiCache | Azure Cache for Redis |
| キュー・通知 | SQS / SNS / EventBridge | Service Bus・Queue Storage / Event Grid |
| ワークフロー | Step Functions | Logic Apps / Durable Functions |
| 監視 | CloudWatch | Azure Monitor / Log Analytics / Application Insights |
| 操作の記録 | CloudTrail | アクティビティログ |
| 鍵・秘密情報 | KMS / Secrets Manager | Key Vault |
| IaC | CloudFormation | ARM テンプレート / **Bicep** |
| 設計の指針 | Well-Architected（6 つの柱） | Azure Well-Architected Framework（5 つの柱）/ Cloud Adoption Framework |

## なぜ必要か

案件によって、使うクラウドはお客さんの方針で決まります。
AWS しか知らないと、Azure の案件で「同じことをどう実現するか」が分かりません。

ただし、すべてを一から学び直す必要はありません。
設計の考え方は共通で、違いは名前と、いくつかの Azure 独自の仕組みです。
対応表で全体をつかみ、**対応表で置き換えられない部分** を重点的に学ぶと、短い時間で使えるようになります。
置き換えられない部分の代表が、次の「どうやるか」で扱う ID と管理の仕組みです。

## どうやるか

### 管理の階層を理解する

Azure のリソースは、次の階層で管理します。

```text
管理グループ（組織・部門の単位）
└─ サブスクリプション（請求と上限の単位。環境ごとに分けることが多い）
   └─ リソースグループ（一緒に作って一緒に消すものの束）
      └─ リソース（VM・DB・ストレージなど）
```

上の階層で設定した権限（RBAC）やルール（Azure Policy）は、下の階層に **継承** されます。
「本番のサブスクリプションでは、東日本・西日本リージョン以外を禁止する」なら、
サブスクリプションに Azure Policy を割り当てます。

### Entra ID と Azure RBAC を区別する

| 仕組み | 何を決めるか | 範囲 |
| --- | --- | --- |
| Microsoft Entra ID（旧 Azure AD） | **誰か**（認証）。ユーザー・グループ・アプリの ID | テナント全体。Microsoft 365 と共通 |
| Azure RBAC | Azure のリソースに **何ができるか**（認可） | 管理グループ〜リソースのどこかに割り当てる |

RBAC の組み込みロールは、次の 3 つの違いがよく問われます。

| ロール | できること |
| --- | --- |
| 所有者（Owner） | すべての操作と、**他の人への権限の付与** |
| 共同作成者（Contributor） | リソースの作成・変更・削除（権限の付与はできない） |
| 閲覧者（Reader） | 見るだけ |

!!! failure "悪い例"
    開発チームに、サブスクリプション全体の「所有者」を割り当てる。
    本番のリソースまで変更でき、他の人に権限を配ることもできてしまいます。

!!! success "良い例"
    開発チームの Entra ID グループに、開発用のリソースグループだけの「共同作成者」を割り当てる。
    範囲（スコープ）を狭く、ロールを必要最小限にします。

認証には、Entra ID の **条件付きアクセス** と **多要素認証** を使います。
社内の Active Directory とのユーザーの同期は、Entra Connect で行います。

### マネージド ID を使う

**マネージド ID** は、AWS の「EC2・ECS にロールを付ける」に当たる仕組みです。
App Service や Container Apps にマネージド ID を付け、Key Vault や DB へのアクセス権を RBAC で与えます。
アプリの設定に、パスワードや接続キーを書かずに済みます。

### ストレージの冗長性を選ぶ

ストレージアカウントは、作るときに複製の範囲を選びます。

| 種類 | 複製の範囲 | 守れる障害 |
| --- | --- | --- |
| LRS | 1 つのデータセンターの中で 3 重 | 機器の故障 |
| ZRS | 1 つのリージョンの、3 つの可用性ゾーン | データセンター（ゾーン）の障害 |
| GRS | LRS ＋ ペアのリージョンへ非同期で複製 | リージョンの障害 |
| GZRS | ZRS ＋ ペアのリージョンへ非同期で複製 | ゾーンとリージョンの障害 |

名前に RA が付くもの（RA-GRS など）は、ペアのリージョン側の複製を、普段から読み取りに使えます。

### SLA を計算する

Azure のサービスは、構成ごとに SLA（稼働率の約束）が決まっています。
VM なら、1 台・可用性セット・可用性ゾーンで、約束される稼働率が変わります。
複数のサービスを直列につなぐときは、[70-01](70-01-requirements.md) と同じく掛け算で全体の SLA を求めます。

## サンプルアプリでは

dev-environment の `cloud/` は AWS 用ですが、対応表を使うと Azure の構成に置き換えられます。

| `cloud/` の部品（AWS） | Azure で置き換えるなら | 補足 |
| --- | --- | --- |
| ECS Fargate（API） | Container Apps | サーバーを管理しない。台数の自動の増減も設定できる |
| ECS Fargate（バッチ）＋ Step Functions ＋ EventBridge Scheduler | Container Apps のジョブ（スケジュール起動） | 複雑なジョブフローなら Logic Apps と組み合わせる |
| Aurora PostgreSQL | Azure Database for PostgreSQL（フレキシブルサーバー） | ゾーン冗長の高可用性を選べる |
| S3（入出力ファイル） | Blob Storage | 冗長性（LRS / ZRS / GRS）を要件で選ぶ |
| SQS ＋ デッドレターキュー | Service Bus のキュー | デッドレターキューが標準で付いている |
| Secrets Manager | Key Vault | アプリはマネージド ID で読み出す |
| VPC・private サブネット | VNet・サブネット | Container Apps は VNet に統合し、DB にはプライベートエンドポイント |
| タスクロール | マネージド ID ＋ RBAC | |
| CloudWatch Logs | Log Analytics | |
| Terraform（AWS プロバイダー） | Terraform（azurerm プロバイダー）か Bicep | |

アプリのコードで変わるのは、主に外部サービスとの接続の部分です。
sample-app では、S3 への接続が `FileFetcher` インタフェースの向こうに隠れています（[30-12](../30-reading/30-12-file-fetcher-s3.md)）。

```java title="sample-app/src/main/java/com/example/sample/order/batch/FileFetcher.java（6〜10 行目）"
/** 入力ファイルを行の並びとして読む（s3:// とローカルパスを同じ形で扱う）. */
public interface FileFetcher {

    List<String> readLines(String location) throws IOException;
}
```

Blob Storage に移すなら、この約束を実装したクラスを足し、設定で切り替えます。
業務ロジック（`OrderImportService`）は変えずに済みます。
外部とのやり取りをインタフェースで包むことは、クラウドを移るときの備えにもなります。

## もし対応表の考え方がなかったら？

AWS の経験だけで、初めての Azure の案件に入ったとします。
サービスの名前が分からず、画面のどこで何を設定するかに時間を取られます。
とくに、権限を Entra ID と RBAC のどちらで設定するのか分からず、
とりあえず広い権限を付けてしまう、という失敗がよく起きます。

対応表で「EC2 のロール ＝ マネージド ID」「リソースのまとまり ＝ リソースグループ」とつなげておけば、
新しい仕組みは対応表に無い部分だけです。
学ぶ量を減らし、危ない設定（広すぎる権限）を避けられます。

## 理解度チェック

1. AWS の S3・SQS・Secrets Manager に対応する Azure のサービスを答えてください。

    ??? note "答え"
        S3 は Blob Storage、SQS は Service Bus のキュー（または Queue Storage）、
        Secrets Manager は Key Vault です。

2. 開発チームが、特定のリソースグループの中だけでリソースを作成・変更でき、他人に権限は付与できないようにしたいです。どうしますか。

    ??? note "答え"
        そのリソースグループのスコープで、チームの Entra ID グループに「共同作成者」を割り当てます。
        「所有者」は権限の付与までできるので、使いません。

3. Entra ID と Azure RBAC の違いを一言で答えてください。

    ??? note "答え"
        Entra ID は「誰か」を確かめる仕組み（認証）、
        Azure RBAC は「Azure のリソースに何ができるか」を決める仕組み（認可）です。

4. 「1 つの可用性ゾーンの障害でもデータを失わず、リージョンの障害は考えなくてよい」とき、ストレージアカウントの冗長性はどれを選びますか。

    ??? note "答え"
        ZRS です。
        LRS ではゾーンの障害に耐えられず、GRS・GZRS はリージョンの障害まで守るため、要件に対して過剰です。

5. sample-app を Azure に移すとき、業務ロジックのクラスを変えずに済むのはなぜですか。

    ??? note "答え"
        ファイルの取得が `FileFetcher` インタフェースの向こうに隠れているからです。
        Blob Storage 用の実装を足して設定で切り替えれば、`OrderImportService` は変わりません。

## コードを読むときの確認観点

- [ ] RBAC のロールの割り当てが、必要最小限の範囲（リソースグループなど）とロールになっているか
- [ ] アプリが、パスワードや接続キーではなくマネージド ID で Key Vault・DB・ストレージにアクセスしているか
- [ ] ストレージアカウントの冗長性が、要件（ゾーン・リージョンの障害）に合っているか
- [ ] DB やストレージが、プライベートエンドポイントで VNet の中からだけ届くようになっているか
- [ ] Azure Policy などで、使うリージョンや禁止する設定が、サブスクリプション単位で決められているか

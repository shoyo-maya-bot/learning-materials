# 30-10 CSV の解析と検証

!!! note "読むコードは `exercise-base` ブランチ"
    この章の引用と行番号は、dev-environment の **`exercise-base` ブランチ**（弱いところを直す前の sample-app）に合わせています。
    `main` は修正済みです。切り替え方と修正後との比べ方は [30 実ソース読解](index.md#exercise-base) を参照してください。

!!! abstract "到達目標"
    - `OrderImportService` が見出し行と各行をどの順で確かめるかを説明できる
    - 形式エラーの行が「行番号: 理由」として記録される流れを読める
    - BOM（バイト順マーク）が何で、なぜ取り除くのかを説明できる
    - 検証ルールを 1 つ追加し、それに合うテストを書ける

## 何か

**CSV**（Comma-Separated Values）は、1 行に 1 件、項目をカンマで区切ったテキストです。
JOB0001 の入力は、次のような CSV です（`local/data/orders.csv`）。

<!-- src: local/data/orders.csv @exercise-base -->
```text title="local/data/orders.csv（全体）"
order_no,member_id,product_code,quantity
A0001,1,P-001,2
A0002,1,P-002,1
A0003,2,P-001,3
A0004,2,P-003,0
```

**解析**（パース）は、1 行の文字列を `Order` という型に変換することです。
**検証**（バリデーション）は、その値が業務のルールに合っているかを確かめることです。
sample-app では、`OrderImportService` の `importLines` と `parse` がこの 2 つを受け持ちます。

## なぜ必要か

外部から受け取るファイルは、いつも正しいとは限りません。
列が足りない、数値の欄に文字が入っている、数量が 0 といった行は、実際によく届きます。

設計書 STEP1 は、形式エラーについて次のように決めています。

- 見出し行が違えば、ファイル全体を異常終了（終了コード 8）にする
- 各行が不正なら、その行だけを飛ばして続け、行番号と理由を警告ログ（APPW0001）に出す

「1 行の誤りで全体を止める」のか「飛ばして続ける」のかは、業務上の大事な判断です。
コードがその判断どおりに書かれているかを読み取れることが、この章の目的です。

## どうやるか

検証のコードを読むときは、**「どの順で」「何を確かめ」「失敗したらどうなるか」** を表にまとめます。

!!! failure "悪い例"
    `parse` の `if` 文を読み、「いろいろチェックしている」で済ませる。
    どのチェックが先に効くか、失敗した行がその後どう扱われるかを確かめていない。

!!! success "良い例"
    次のような表を作り、設計書の STEP1 と 1 行ずつ照らし合わせる。

    | 順 | 確かめること | 失敗時の扱い | 場所 |
    |---|---|---|---|
    | 0 | 見出し行が一致する | 例外（ファイル全体を中止） | 27〜29 行目 |
    | 1 | 列数が 4 | その行を飛ばして記録 | 57〜59 行目 |
    | 2 | `order_no` が空でない | 同上 | 60〜63 行目 |
    | 3 | `member_id` が数値 | 同上 | 64 行目 |
    | 4 | `product_code` が空でない | 同上 | 65〜68 行目 |
    | 5 | `quantity` が数値で 1〜999 | 同上 | 69〜72 行目 |

1 つの行に誤りが複数あっても、記録されるのは **最初に見つかった 1 つだけ** です。
たとえば `A001,x,P-01,0` は、`member_id` の誤りだけが記録され、数量の誤りは報告されません。

## サンプルアプリでは

### 見出し行の確認と、行ごとのループ

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java#L17-L17,L25-L45,L51-L53 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/OrderImportService.java（17 行目、25〜53 行目）"
    static final String HEADER = "order_no,member_id,product_code,quantity";
    // ...
    @Transactional
    public ImportResult importLines(List<String> lines) {
        if (lines.isEmpty() || !HEADER.equals(stripBom(lines.get(0)).trim())) {
            throw new IllegalArgumentException("見出し行が不正です（期待値: " + HEADER + "）");
        }
        int imported = 0;
        int duplicated = 0;
        List<String> errors = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            String line = lines.get(i);
            if (line.isBlank()) {
                continue;
            }
            int lineNo = i + 1;
            Order order;
            try {
                order = parse(line);
            } catch (IllegalArgumentException e) {
                errors.add(lineNo + ": " + e.getMessage());
                continue;
            }
            // 46〜50 行目: 登録（30-11 で読む）
        }
        return new ImportResult(imported, duplicated, List.copyOf(errors));
    }
```

- 17 行目: 見出しは定数です。`static`（`private` なし）なので、同じパッケージのテストから参照できます
- 27 行目: 空のファイル、または見出しが違うときは、例外を投げてファイル全体を中止します
- 27 行目の `trim()`: 前後の空白だけを取ります。項目の **間** の空白は取りません
- 33 行目: `i = 1` から始めるので、見出し行（0 番目）は飛ばします
- 35〜37 行目: 空行は、エラーにもせず黙って飛ばします
- 38 行目: 行番号は「ファイルの何行目か」です。リストの添字 `i` は 0 始まりなので `+ 1` します
- 40〜45 行目: `parse` が `IllegalArgumentException` を投げたら、理由を記録して次の行へ進みます

### 1 行の解析

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java#L55-L82 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/OrderImportService.java（55〜82 行目）"
    static Order parse(String line) {
        String[] cols = line.split(",", -1);
        if (cols.length != 4) {
            throw new IllegalArgumentException("列数が 4 ではありません（" + cols.length + " 列）");
        }
        String orderNo = cols[0].trim();
        if (orderNo.isEmpty()) {
            throw new IllegalArgumentException("order_no が空です");
        }
        long memberId = parseLong(cols[1], "member_id");
        String product = cols[2].trim();
        if (product.isEmpty()) {
            throw new IllegalArgumentException("product_code が空です");
        }
        long quantity = parseLong(cols[3], "quantity");
        if (quantity < 1 || quantity > 999) {
            throw new IllegalArgumentException("quantity は 1〜999 です（" + quantity + "）");
        }
        return new Order(orderNo, memberId, product, (int) quantity);
    }

    private static long parseLong(String value, String name) {
        try {
            return Long.parseLong(value.trim());
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(name + " が数値ではありません", e);
        }
    }
```

読みどころは 3 つです。

1. **`split(",", -1)` の `-1`**: Java の `split` は、既定では末尾の空の項目を捨てます。`-1` を付けると捨てません。`A001,1,P-01,` は 4 列（最後が空）として扱われ、「quantity が数値ではありません」になります
2. **数量を `long` で読んでから範囲を確かめる**: いきなり `int` に変換すると、`99999999999` のような値で別の例外になります。`long` で受けてから 1〜999 を確かめ、最後に `(int)` で縮めています
3. **例外の種類をそろえる**: `NumberFormatException` を `IllegalArgumentException` に包み直しています（79〜80 行目）。呼び出し側（42 行目）は 1 種類の例外だけを受け止めれば済みます

### BOM の除去

<!-- src: sample-app/src/main/java/com/example/sample/order/OrderImportService.java#L84-L86 @exercise-base -->
```java title="sample-app/src/main/java/com/example/sample/order/OrderImportService.java（84〜86 行目）"
    private static String stripBom(String s) {
        return s.startsWith("﻿") ? s.substring(1) : s;
    }
```

**BOM**（Byte Order Mark）は、UTF-8 のファイルの先頭に付くことがある目に見えない 1 文字（U+FEFF）です。
表計算ソフトで「UTF-8 で保存」すると、付くことがあります。
BOM が付いたままだと、見出しの比較（27 行目）が一致せず、正しいファイルを不正と判定してしまいます。

!!! note "ソースの見た目について"
    実際のソースでは、`"﻿"` ではなく BOM の文字そのものが `""` の間に入っています。
    エディタでは `""`（空文字）に見えるので注意してください。上の引用は、読みやすさのために `﻿` と書き換えています。
    テスト `OrderImportServiceTest.java` 21 行目も同じです。

### 実案件での読み替え

| sample-app | 実案件で探すもの |
|---|---|
| `HEADER` 定数と 27 行目の比較 | ファイル仕様書（レイアウト定義）と、見出し・レコード区分の確認処理 |
| `parse` の `if` の並び | 項目ごとの検証（共通の検証部品、入力チェック定義書、Bean Validation の注釈など） |
| `errors.add(lineNo + ": " + ...)` | エラー行の記録先（警告ログ、エラーファイル、エラー用テーブル） |
| `split(",", -1)` | CSV ライブラリの設定（引用符・改行を含む項目への対応） |
| `stripBom` | 文字コードの扱い（Shift_JIS か UTF-8 か、BOM の有無）を決めている箇所 |

!!! tip "sample-app の CSV は単純化してある"
    `split(",")` は、`"東京,大阪"` のように引用符で囲んだ項目の中のカンマに対応できません。
    実案件の CSV では、引用符や項目内の改行を扱えるライブラリを使っていることが多いです。

## もし行ごとの検証がなかったら？

検証をせずに、受け取った値をそのまま登録しようとすると、誤りは DB に入れる瞬間まで見つかりません。
数量 0 の行は、テーブルの制約（`local/db/init/01_schema.sql` 13 行目の `CHECK (quantity BETWEEN 1 AND 999)`）で例外になります。
すると、ファイル全体が 1 つのトランザクションなので、正しい行まで含めてすべて取り消されます（30-11 で読みます）。

さらに、DB の例外メッセージには「ファイルの何行目か」が含まれません。
運用担当者は、どの行を直して再送してもらえばよいか判断できなくなります。

## 理解度チェック

1. 見出し行が不正なときと、データ行が不正なときで、扱いはどう違いますか。

    ??? note "答え"
        見出し行が不正なら、`IllegalArgumentException` を投げてファイル全体を中止します（27〜29 行目）。
        データ行が不正なら、その行だけを `errors` に記録して次の行に進みます（42〜45 行目）。

2. `orders.csv` の `A0004` の行は、エラーとして何行目と記録されますか。

    ??? note "答え"
        5 行目です。見出しが 1 行目なので、4 件目のデータはファイルの 5 行目です。
        記録される文字列は `5: quantity は 1〜999 です（0）` です。

3. 空行は、エラーとして記録されますか。

    ??? note "答え"
        記録されません。35〜37 行目で黙って飛ばします。ただし行番号は数え続けるので、後ろの行の番号はずれません。

4. `parseLong` が `NumberFormatException` を `IllegalArgumentException` に包み直しているのはなぜですか。

    ??? note "答え"
        呼び出し側（`importLines` の 42 行目）が `IllegalArgumentException` だけを受け止めているからです。
        なお `NumberFormatException` は `IllegalArgumentException` の子クラスなので、包まなくても受け止められます。
        包み直す本当の効果は、メッセージを「member_id が数値ではありません」のような業務向けの文にそろえることです。

## コードを読むときの確認観点

- [ ] ファイル全体を止める検証と、行だけを飛ばす検証を区別したか
- [ ] 検証の順番と、1 行に誤りが複数あるときに何が記録されるかを確認したか
- [ ] 行番号の数え方（0 始まりか 1 始まりか、見出しや空行を含むか）を確認したか
- [ ] 文字コード・BOM・前後の空白の扱いを確認したか
- [ ] 検証ルールと、DB の制約（桁数・範囲・必須）が一致しているかを確認したか

## 演習

まず自分で考え、ソースを開いて確かめてから解答を見てください。

1. **動きを予想する**: 見出し行が `order_no, member_id,product_code,quantity`（2 つ目の項目の前に空白）のファイルを JOB0001 に渡すと、どうなりますか。終了コードも答えてください。
2. **動きを予想する**: 3 行目が `A0005,1,P-001,abc` のとき、`ImportResult.errors()` に入る文字列を正確に答えてください。
3. **どのテストが落ちるか**: `parse` の `line.split(",", -1)` を `line.split(",")` に変えたとき、`OrderImportServiceTest` のどのテストが失敗しますか。
4. **どのテストが落ちるか**: `importLines` 27 行目の `stripBom(lines.get(0))` を `lines.get(0)` に変えたとき、どのテストが失敗しますか。
5. **小さな変更**: DB の `product_code` は `VARCHAR(20)` です（`01_schema.sql` 12 行目）。21 文字以上の商品コードを形式エラーにする検証を `parse` に追加し、`parseRejects` にテストケースを 1 つ足してください。

解答: [30-10 解答](answers/30-10.md)

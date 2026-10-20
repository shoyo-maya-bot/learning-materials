// 教材の Java のコード例の構文だけを検査する（scripts/check_java_examples.py から呼ぶ. 型や import の解決はしない）.
//
//   java -cp javaparser-core.jar scripts/java/JavaSyntaxCheck.java <言語レベル> <ファイル>...
//
// コード例は断片が多いので、次の 3 通りで読み、どれか 1 つで読めれば OK とする:
//   1. そのまま（package / import / クラス宣言を含むファイル全体）
//   2. クラスの中身（フィールド・メソッド・アノテーション付きのメソッド）
//   3. メソッドの中身（文の並び）
// どれでも読めなければ、いちばん先まで読めた読み方の最初の誤りを出す.
// 出力は 1 ファイル 1 行: "OK<TAB>ファイル" か "NG<TAB>ファイル<TAB>行<TAB>列<TAB>読み方<TAB>メッセージ"（行・列は元のファイルの位置）.
// 終了コード: 0 すべて OK / 1 NG あり / 2 引数の誤り

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.Position;
import com.github.javaparser.Problem;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

public class JavaSyntaxCheck {
    private static final String CLASS_OPEN = "class Example__ {\n";
    private static final String METHOD_OPEN = "class Example__ { void example__() throws Exception {\n";

    record Attempt(String mode, boolean ok, int line, int column, String message) {}

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: JavaSyntaxCheck <JAVA_17 などの言語レベル> <file>...");
            System.exit(2);
        }
        ParserConfiguration config = new ParserConfiguration()
                .setLanguageLevel(ParserConfiguration.LanguageLevel.valueOf(args[0]))
                .setAttributeComments(false);
        int failures = 0;
        for (int i = 1; i < args.length; i++) {
            String code = Files.readString(Path.of(args[i]), StandardCharsets.UTF_8);
            Attempt best = null;
            String[][] modes = {
                {"file", "", ""},
                {"class-body", CLASS_OPEN, "\n}\n"},
                {"method-body", METHOD_OPEN, "\n}}\n"},
            };
            for (String[] m : modes) {
                Attempt a = parse(new JavaParser(config), m[0], m[1] + code + m[2], m[1].isEmpty() ? 0 : 1);
                if (a.ok()) {
                    best = a;
                    break;
                }
                if (best == null || a.line() > best.line() || (a.line() == best.line() && a.column() >= best.column())) {
                    best = a;
                }
            }
            if (best.ok()) {
                System.out.println("OK\t" + args[i]);
            } else {
                failures++;
                System.out.println(String.join("\t", "NG", args[i], String.valueOf(best.line()),
                        String.valueOf(best.column()), best.mode(), best.message()));
            }
        }
        System.exit(failures == 0 ? 0 : 1);
    }

    private static Attempt parse(JavaParser parser, String mode, String source, int offset) {
        ParseResult<?> result = parser.parse(source);
        if (result.isSuccessful()) {
            return new Attempt(mode, true, 0, 0, "");
        }
        Problem p = result.getProblems().get(0);
        Position pos = p.getLocation().flatMap(l -> l.getBegin().getRange()).map(r -> r.begin).orElse(new Position(1, 1));
        String message = p.getMessage().split("\n")[0].replace('\t', ' ');
        int cut = message.indexOf(", expected one of");
        if (cut > 0) {
            message = message.substring(0, cut);
        }
        return new Attempt(mode, false, Math.max(1, pos.line - offset), pos.column, message);
    }
}

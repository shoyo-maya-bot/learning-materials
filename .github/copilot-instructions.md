# Copilot への指示（learning-materials）

このリポジトリで教材を書く・直すときは、リポジトリ直下の [AGENTS.md](../AGENTS.md) に従ってください。要点:

- dev-environment のコードは `dev-environment-pin.json` の SHA の実物から写し、直前に `<!-- src: ... @main -->` を書く
- サンプルは架空のもの（会員・注文・商品など）だけ。実在の会社名・個人名・メールアドレス・ローカルのパスを書かない
- 変更後は `scripts/check_*.py`・`python -m unittest discover -s tests`・`ruff check .`・`mkdocs build --strict` を実行する

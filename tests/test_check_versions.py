"""scripts/check_versions.py のテスト（仮の dev-environment・mkdocs.yml・章を作り、版のずれを検知できるか）."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_versions as cv  # noqa: E402
from _util import rmtree  # noqa: E402
from check_code_quotes import Source  # noqa: E402

BUILD = """plugins {
    id 'org.springframework.boot' version '%s'
}
tasks.withType(JavaCompile).configureEach {
    options.release = 17
}
dependencies {
    implementation 'org.mybatis.spring.boot:mybatis-spring-boot-starter:4.0.1'
    testImplementation 'io.karatelabs:karate-junit5:1.5.1'
}
"""
WRAPPER = "distributionUrl=https\\://services.gradle.org/distributions/gradle-%s-bin.zip\n"
COMPOSE = "services:\n  db:\n    image: postgres:16\n"
MKDOCS = """site_name: x
markdown_extensions:
  - pymdownx.superfences:
      custom_fences:
        - format: !!python/name:pymdownx.superfences.fence_code_format
extra:
  versions:
    branch: exercise-base
    java: "17"
    spring_boot: "4.0.7"
    mybatis_starter: "4.0.1"
    gradle: "8.14.3"
    postgres: "16"   # ローカルの DB
    karate: "1.5.1"
nav:
  - index.md
"""
PAGE_OK = """---
render_macros: true
---

# 10-01 全体像

| ビルド | Gradle {{ versions.gradle }}（Wrapper で固定） |

```groovy
id 'org.springframework.boot' version '4.0.7'
```

<!-- Spring Boot 4.0 はコメントの中なので対象外 -->
"""


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
    )


class CheckVersionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "dev-environment"
        (self.repo / "sample-app/gradle/wrapper").mkdir(parents=True)
        (self.repo / "local").mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        self.write_repo("4.0.7", "8.14.3")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "exercise")
        git(self.repo, "branch", "exercise-base")
        # main は版が新しい（採点で見つかった状況: main は 4.1.1・9.8.0、教材は exercise-base の 4.0.7・8.14.3）
        self.write_repo("4.1.1", "9.8.0")
        git(self.repo, "commit", "-qam", "main")
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        self.mkdocs = self.tmp / "mkdocs.yml"
        self.mkdocs.write_text(MKDOCS, encoding="utf-8")

    def tearDown(self):
        rmtree(self.tmp)

    def write_repo(self, boot, gradle):
        (self.repo / "sample-app/build.gradle").write_text(BUILD % boot, encoding="utf-8")
        (self.repo / "sample-app/gradle/wrapper/gradle-wrapper.properties").write_text(WRAPPER % gradle, encoding="utf-8")
        (self.repo / "local/docker-compose.yml").write_text(COMPOSE, encoding="utf-8")

    def page(self, text, name="10-01.md"):
        (self.docs / name).write_text(text, encoding="utf-8")

    def run_all(self):
        versions = cv.load_versions(self.mkdocs)
        return cv.check_docs(self.docs, versions) + cv.check_sources(versions, Source(self.repo))

    def test_load_versions_ignores_python_tags_and_comments(self):
        v = cv.load_versions(self.mkdocs)
        self.assertEqual(v["postgres"], "16")
        self.assertEqual(v["branch"], "exercise-base")
        self.assertEqual(len(v), 7)

    def test_ok(self):
        self.page(PAGE_OK)
        self.assertEqual(self.run_all(), [])

    def test_literal_version_in_prose_is_reported(self):
        # 採点で見つかった書き方: 本文に「Spring Boot 4.0」「Gradle 8.14」を直接書いていた
        self.page(PAGE_OK + "\n| 言語・FW | Java 17、Spring Boot 4.0、MyBatis |\n| ビルド | Gradle 8.14（Wrapper で固定） |\n")
        errors = self.run_all()
        self.assertEqual(len(errors), 2, errors)
        self.assertIn("Spring Boot 4.0", errors[0])

    def test_full_version_value_in_prose_is_reported(self):
        self.page(PAGE_OK + "\nSpring Boot の版（6 行目の 4.0.7）に合った版を決めます。\n")
        errors = self.run_all()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("4.0.7", errors[0])

    def test_mkdocs_value_differs_from_exercise_base(self):
        self.page(PAGE_OK)
        self.mkdocs.write_text(MKDOCS.replace('gradle: "8.14.3"', 'gradle: "9.8.0"'), encoding="utf-8")
        errors = self.run_all()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("exercise-base:sample-app/gradle/wrapper/gradle-wrapper.properties は 8.14.3", errors[0])

    def test_macro_without_front_matter_is_reported(self):
        self.page(PAGE_OK.split("---\n\n", 1)[1])
        errors = self.run_all()
        self.assertTrue(any("render_macros" in e for e in errors), errors)

    def test_unknown_variable_is_reported(self):
        self.page(PAGE_OK + "\nJUnit {{ versions.junit }}\n")
        errors = self.run_all()
        self.assertTrue(any("versions.junit" in e for e in errors), errors)

    def test_missing_branch_fails(self):
        self.page(PAGE_OK)
        self.mkdocs.write_text(MKDOCS.replace("    branch: exercise-base\n", ""), encoding="utf-8")
        errors = self.run_all()
        self.assertTrue(any("branch" in e for e in errors), errors)

    def test_rds_instance_count_is_not_a_version(self):
        self.page(PAGE_OK + "\n| 簡易環境 | RDS PostgreSQL 1 台 |\n")
        self.assertEqual(self.run_all(), [])


if __name__ == "__main__":
    unittest.main()

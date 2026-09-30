import os
import pathlib
import unittest

REQUIRED_DOCS = [
    "docs/ARCHITECTURE.md",
    "docs/SECURITY.md",
    "docs/DATA_MODEL.md",
    "docs/API.md",
    "docs/DEVELOPMENT.md",
    "docs/FORENSIC_TRACEABILITY.md",
    "README.md",
    ".env.example",
    ".gitignore",
    "pyproject.toml",
]

REQUIRED_DIRECTORIES = [
    "backend",
    "workers",
    "parser",
    "analytics",
    "ai",
    "database",
    "frontend",
    "tests",
    "docs",
    "scripts",
    "infra",
]


class TestFoundationStructure(unittest.TestCase):
    def setUp(self):
        self.base_dir = pathlib.Path(__file__).resolve().parent.parent.parent

    def test_required_documentation_and_configs_exist(self):
        for doc in REQUIRED_DOCS:
            target_path = self.base_dir / doc
            self.assertTrue(target_path.exists(), f"Missing required file: {doc}")
            self.assertGreater(target_path.stat().st_size, 0, f"File is empty: {doc}")

    def test_required_directories_exist(self):
        for d in REQUIRED_DIRECTORIES:
            target_path = self.base_dir / d
            self.assertTrue(
                target_path.exists() and target_path.is_dir(),
                f"Missing required directory: {d}",
            )

    def test_env_example_contains_core_keys_and_no_real_secrets(self):
        env_example = self.base_dir / ".env.example"
        content = env_example.read_text(encoding="utf-8")

        expected_vars = [
            "DATABASE_URL",
            "MONGODB_URI",
            "REDIS_URL",
            "SECRET_KEY",
            "EVIDENCE_STORAGE_PATH",
            "LLM_PROVIDER",
            "SEARCH_ENGINE_URL",
        ]
        for var in expected_vars:
            self.assertIn(f"{var}=", content, f"Missing {var} in .env.example")

        self.assertNotIn("BEGIN RSA PRIVATE KEY", content)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", content)

    def test_package_structure_importability(self):
        packages = ["backend", "workers", "parser", "analytics", "ai", "database"]
        for pkg in packages:
            init_file = self.base_dir / pkg / "__init__.py"
            self.assertTrue(init_file.exists(), f"Package missing __init__.py: {pkg}")


if __name__ == "__main__":
    unittest.main()

"""Cross-platform bootstrap for the SpeakFlow backend."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
REQUIREMENTS = BACKEND_ROOT / "requirements.txt"
COMPOSE_FILE = PROJECT_ROOT / "compose.yaml"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

_PACKAGING_COMMANDS = {
    "bdist_wheel",
    "build",
    "build_ext",
    "dist_info",
    "egg_info",
    "sdist",
}


def _run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _prepare_env() -> None:
    if ENV_FILE.exists():
        return
    shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
    print(f"Created {ENV_FILE}. Add the shared API keys before running the app.")


def _install_dependencies() -> None:
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--requirement",
            str(REQUIREMENTS),
        ]
    )


def _load_env() -> None:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from speakflow.config import load_runtime_env

    load_runtime_env()


def _install_models(revision: str) -> None:
    _run(
        [
            sys.executable,
            str(BACKEND_ROOT / "tools" / "model_bundle.py"),
            "download",
            "--revision",
            revision,
        ]
    )


def _docker_compose(*arguments: str) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError(
            "Docker is not installed. Install Docker Desktop or Docker Engine "
            "with the Compose plugin."
        )
    _run(["docker", "compose", "-f", str(COMPOSE_FILE), *arguments])


def _wait_for_postgres() -> None:
    host = "127.0.0.1"
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"PostgreSQL is accepting connections on {host}:{port}.")
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"PostgreSQL did not become ready on {host}:{port}.")


def _prepare_database() -> None:
    _docker_compose("up", "-d", "postgres")
    _wait_for_postgres()
    _run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=BACKEND_ROOT,
    )


def _prepare_ollama() -> None:
    if shutil.which("ollama") is None:
        raise RuntimeError(
            "Ollama is not installed. Install it, start it, and rerun setup."
        )
    model = os.environ.get("OLLAMA_EMBED_MODEL", "embeddinggemma:latest")
    _run(["ollama", "pull", model])


def _ingest_curriculum() -> None:
    snapshot = (
        BACKEND_ROOT
        / ".models"
        / "curriculum"
        / "rag-curriculum-v1.zip"
    )
    if not snapshot.is_file():
        raise RuntimeError(
            "The verified model bundle is missing its RAG curriculum snapshot: "
            f"{snapshot}"
        )
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(BACKEND_ROOT), existing))
    )
    print(f"\n> {sys.executable} -m plp.ingest", flush=True)
    subprocess.run(
        [sys.executable, "-m", "plp.ingest"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
    )
    print(
        f"\n> {sys.executable} -m plp.curriculum_snapshot import "
        f"--snapshot {snapshot}",
        flush=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "plp.curriculum_snapshot",
            "import",
            "--snapshot",
            str(snapshot),
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
    )


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("SpeakFlow's pinned backend environment requires Python 3.12.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-revision", default="main")
    parser.add_argument("--skip-dependencies", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--skip-database", action="store_true")
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--skip-curriculum", action="store_true")
    args = parser.parse_args()

    _prepare_env()
    if not args.skip_dependencies:
        _install_dependencies()
    _load_env()
    if not args.skip_models:
        _install_models(args.model_revision)
    if not args.skip_database:
        _prepare_database()
    if not args.skip_ollama:
        _prepare_ollama()
    if not args.skip_curriculum:
        if args.skip_database or args.skip_ollama:
            raise RuntimeError(
                "curriculum ingestion requires both PostgreSQL and Ollama; "
                "also pass --skip-curriculum"
            )
        _ingest_curriculum()
    print("\nSpeakFlow backend setup completed successfully.")


if __name__ == "__main__":
    # Setuptools still executes a top-level setup.py while building a modern
    # pyproject package. Keep the historical bootstrap command available to
    # developers without letting it consume packaging arguments such as
    # ``egg_info`` or ``bdist_wheel``.
    if any(argument in _PACKAGING_COMMANDS for argument in sys.argv[1:]):
        from setuptools import setup as setuptools_setup

        setuptools_setup()
    else:
        main()

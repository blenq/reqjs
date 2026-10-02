from pathlib import Path

import nox

proj_toml = nox.project.load_toml()
py_versions = nox.project.python_versions(proj_toml)

nox.options.default_venv_backend = "uv"
nox.options.reuse_venv = "yes"
nox.options.allow_parallel = True
nox.options.parallel = "auto"


@nox.session(py=py_versions)
def mypy(session: nox.Session):
    session.install("mypy")
    session.run("mypy")


@nox.session(py=py_versions)
def pyright(session: nox.Session):
    session.install("pyright")
    session.run("pyright")


@nox.session(python=py_versions)
def ty(session: nox.Session):
    session.install("ty")
    session.run("ty", "check")


@nox.session(python=py_versions[0])
def ruff_format(session: nox.Session):
    session.install("ruff")
    session.run("ruff", "format")


@nox.session(python=py_versions[0])
def ruff_lint(session: nox.Session):
    session.install("ruff")
    session.run("ruff", "check")


@nox.session(python=py_versions[0])
def clang_format(session: nox.Session):
    session.install("clang-format")
    session.run(
        "clang-format",
        "--dry-run",
        "--Werror",
        "src/reqjsc/reqjs.c",
    )


@nox.session(python=py_versions)
def unittest(session: nox.Session):
    session.install("coverage[toml]", "setuptools")
    session.run_install("./setup.py", "build_ext", "--inplace", external=True)
    session.env["PYTHONPATH"] = str(Path(__file__).parent / "src")
    session.run("coverage", "run", "--parallel-mode", "-m", "unittest")


@nox.session(python=py_versions[0], requires=["unittest"])
def coverage_combine(session: nox.Session):
    session.install("coverage[toml]")
    session.run("coverage", "combine")

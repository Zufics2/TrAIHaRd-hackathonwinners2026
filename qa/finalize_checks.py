"""Offline handoff checks. Does not push, fetch, install hooks or edit core files."""
import ast
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from geolab.experiment import EXP_DIR, digest, load_experiment, run_experiment


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    assert git("branch", "--show-current") == "codex/qa-experiments"
    assert Path(git("rev-parse", "--show-toplevel")).resolve() == ROOT
    exp = load_experiment("EXP-001-COMPETITIVE-v1")
    saved = json.loads((EXP_DIR / "results/EXP-001-COMPETITIVE-v1_result.json").read_text())
    assert run_experiment(exp) == saved == run_experiment(exp)
    baseline = saved["evidence"]["documents"]["baseline"]
    treatment = saved["evidence"]["documents"]["treatment"]
    documents = []
    for variant, docs in (("baseline", baseline), ("treatment", treatment)):
        for doc in docs:
            path = EXP_DIR / exp["corpus_subdir"] / variant / f"{doc['doc_id']}.json"
            if not path.exists():
                path = EXP_DIR / exp["corpus_subdir"] / "baseline" / f"{doc['doc_id']}.json"
            raw = json.loads(path.read_text())
            assert digest(raw) == doc["sha256"]
            assert urlsplit(raw["url"]).scheme == "https" and urlsplit(raw["url"]).hostname
            assert datetime.fromisoformat(raw["fetched_at"]).tzinfo is not None
            assert raw["provenance"].strip()
            if variant == "baseline":
                documents.append({k: raw[k] for k in ("doc_id", "entity_id", "url", "fetched_at", "provenance")})
    assert len(baseline) == 15 and len({d["entity_id"] for d in baseline}) == 6
    assert [b["doc_id"] for b, t in zip(baseline, treatment) if b != t] == ["ck_kids"]
    for original in (EXP_DIR / "corpus/baseline").glob("*.json"):
        assert original.read_bytes() == (EXP_DIR / exp["corpus_subdir"] / "baseline" / original.name).read_bytes()
    original_treatment = EXP_DIR / "corpus/treatment/ck_kids.json"
    assert original_treatment.read_bytes() == (EXP_DIR / exp["corpus_subdir"] / "treatment/ck_kids.json").read_bytes()

    # Exercise the installed hook via stdin only, never git push.
    common = Path(git("rev-parse", "--git-common-dir")).resolve()
    hook = common / "hooks/pre-push"
    assert hook.is_file() and os.access(hook, os.X_OK)
    config = subprocess.run(["git", "config", "--get-all", "core.hooksPath"], cwd=ROOT, capture_output=True, text=True)
    assert config.returncode == 1 and not config.stdout
    other = Path(git("worktree", "list", "--porcelain").splitlines()[0].removeprefix("worktree "))
    other_common = Path(git("-C", str(other), "rev-parse", "--git-common-dir"))
    if not other_common.is_absolute():
        other_common = other / other_common
    assert other_common.resolve() == common
    other_config = subprocess.run(["git", "-C", str(other), "config", "--get-all", "core.hooksPath"], capture_output=True, text=True)
    assert other_config.returncode == 1 and not other_config.stdout
    env = {k: v for k, v in os.environ.items() if k != "GEOLAB_ALLOW_PROTECTED_PUSH"}
    sha, zero = "a" * 40, "0" * 40
    def update(local, remote, deleting=False):
        return f"{local} {zero if deleting else sha} {remote} {sha}\n"
    cases = {
        "main_update": (update("refs/heads/main", "refs/heads/main"), 1),
        "head_to_main": (update("HEAD", "refs/heads/main"), 1),
        "main_delete": (update("(delete)", "refs/heads/main", True), 1),
        "feat_core_app": (update("refs/heads/feat/core-app", "refs/heads/feat/core-app"), 0),
        "codex_qa": (update("refs/heads/codex/qa-experiments", "refs/heads/codex/qa-experiments"), 0),
        "mixed_contains_main": (update("HEAD", "refs/heads/codex/qa-experiments") + update("HEAD", "refs/heads/main"), 1),
        "empty": ("", 0),
    }
    hook_results = {}
    for name, (payload, expected) in cases.items():
        result = subprocess.run([str(hook), "origin", "unused-local-test"], input=payload, text=True, env=env, cwd=ROOT, capture_output=True)
        assert result.returncode == expected, (name, result.stderr)
        hook_results[name] = result.returncode

    for module in (ROOT / "src/geolab").glob("*.py"):
        importlib.import_module("geolab." + module.stem)
    ast.parse((ROOT / "app.py").read_text())
    paths = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()))
    patterns = [r"AKIA[0-9A-Z]{16}", r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", r"gh[pousr]_[A-Za-z0-9]{30,}", r"sk-[A-Za-z0-9_-]{32,}"]
    matches = [name for name in paths if (ROOT / name).is_file() and any(re.search(p, (ROOT / name).read_text(errors="replace")) for p in patterns)]
    assert not matches, matches
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rx", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "43 passed, 9 xfailed" in result.stdout, result.stdout
    assert subprocess.run(["git", "diff", "--check"], cwd=ROOT).returncode == 0
    output = dict(branch=git("branch", "--show-current"), tested_base=git("rev-parse", "HEAD"),
                  compared_claude_commit=git("rev-parse", "feat/core-app"), pytest=result.stdout,
                  corpus_documents=documents, reproducibility="saved plus two reruns identical",
                  summary=saved["summary"], hook_path=str(hook), core_hooksPath="unset in both worktrees",
                  hook_stdin_tests=hook_results, hook_modified=False, secret_signature_matches=matches,
                  scope="geolab imports + app AST; interactive UI NOT_RUN; secret signatures are not a full security audit")
    (ROOT / "qa/evidence/finalization.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print("PASS: corpus/provenance, reruns, imports, app AST, secret signatures, hook stdin cases, 43 passed / 9 strict xfailed")


if __name__ == "__main__":
    main()

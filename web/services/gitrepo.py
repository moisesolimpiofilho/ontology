"""Repositório Git de cada ontologia governada (PocGov seções 3 e 6).

- main: versão oficial publicada; cada publicação gera uma tag vX.Y.Z.
- proposta/<id>: cópia de trabalho de uma proposta, criada a partir da tag da versão base.
Todas as operações passam por um lock (o working tree é compartilhado).
"""
import os
import subprocess
import threading

_LOCK = threading.RLock()
ONTOLOGY_FILE = "ontology.owl"


class GitError(RuntimeError):
    pass


def tag_name(version):
    return f"v{version}"


def branch_name(proposal_id):
    return f"proposta/{proposal_id}"


class OntologyRepo:
    def __init__(self, base_dir, slug):
        self.path = os.path.join(base_dir, slug)

    # -- infraestrutura ------------------------------------------------------
    def _git(self, *args, user=None, check=True):
        identity = ("OntoCube", "ontocube@ontocube.local")
        if user:
            identity = (user["display_name"], f"{user['username']}@ontocube.local")
        cmd = ["git", "-C", self.path,
               "-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}",
               "-c", "commit.gpgsign=false", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout.strip()

    def _write(self, files):
        for rel, content in files.items():
            full = os.path.join(self.path, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        self._git("add", "--", *files.keys())

    def _commit(self, message, user):
        if not self._git("status", "--porcelain"):
            return self.head()
        self._git("commit", "-m", message, user=user)
        return self.head()

    def head(self):
        return self._git("rev-parse", "HEAD")

    def exists(self):
        return os.path.isdir(os.path.join(self.path, ".git"))

    # -- operações -----------------------------------------------------------
    def init(self, files, message, user, version):
        with _LOCK:
            if self.exists():
                raise GitError(f"Repositório já existe: {self.path}")
            os.makedirs(self.path, exist_ok=True)
            self._git("init", "-b", "main")
            self._write(files)
            sha = self._commit(message, user)
            self._git("tag", "-a", tag_name(version), "-m", f"Versão {version}", user=user)
            return sha

    def save_working_copy(self, proposal_id, base_version, content, message, user):
        """Commit da cópia de trabalho no branch da proposta (criado a partir da tag base)."""
        branch = branch_name(proposal_id)
        with _LOCK:
            exists = self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
            if exists:
                self._git("checkout", "-q", branch)
            else:
                self._git("checkout", "-q", "-b", branch, tag_name(base_version))
            try:
                self._write({ONTOLOGY_FILE: content})
                return branch, self._commit(message, user)
            finally:
                self._git("checkout", "-q", "main")

    def publish(self, proposal_id, version, files, message, user):
        """Merge do branch da proposta na main + commit final (cabeçalho, docs) + tag."""
        branch = branch_name(proposal_id)
        with _LOCK:
            self._git("checkout", "-q", "main")
            previous = self.head()
            try:
                self._git("merge", "--no-ff", "-m", f"Merge {branch} (proposta #{proposal_id})", branch, user=user)
                self._write(files)
                sha = self._commit(message, user)
                self._git("tag", "-a", tag_name(version), "-m", f"Versão {version} (proposta #{proposal_id})", user=user)
                return sha
            except Exception:
                self._git("merge", "--abort", check=False)
                self._git("reset", "-q", "--hard", previous, check=False)
                self._git("tag", "-d", tag_name(version), check=False)
                raise

    def undo_publish(self, previous_sha, version):
        """Compensação se a gravação no banco falhar depois do commit/tag."""
        with _LOCK:
            self._git("tag", "-d", tag_name(version), check=False)
            self._git("checkout", "-q", "main")
            self._git("reset", "-q", "--hard", previous_sha, check=False)

    def read(self, ref, rel_path=ONTOLOGY_FILE):
        with _LOCK:
            return self._git("show", f"{ref}:{rel_path}")

    def log(self, ref="main", limit=30):
        with _LOCK:
            out = self._git("log", ref, f"-{limit}", "--date=iso-strict",
                            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s%x1f%D", check=False)
        entries = []
        for line in out.splitlines():
            sha, author, when, subject, refs = (line.split("\x1f") + [""] * 5)[:5]
            entries.append({"sha": sha, "author": author, "date": when, "subject": subject, "refs": refs})
        return entries

    def tags(self):
        with _LOCK:
            return [t for t in self._git("tag", "--list", "v*", check=False).splitlines() if t]

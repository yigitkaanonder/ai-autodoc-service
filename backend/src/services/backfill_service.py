from services.github import (
    get_file_content,
    fetch_commits_for_ref,
    fetch_commit_files,
    fetch_default_branch,
)
from services.code_parser import extract_functions
from services.registry_service import (
    diff_functions,
    update_registry,
    mark_functions_deleted,
    mark_file_deleted,
)
from pipeline import process_function
from services.doc_service import save_documentation_to_db, get_latest_documentation

# Same set the webhook uses
SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".h", ".hpp")


def _code_files(files, status):
    """Pick filenames with a given git status that are supported code files."""
    return [
        f["filename"]
        for f in files
        if f.get("status") == status and f["filename"].endswith(SUPPORTED_EXTENSIONS)
    ]


def backfill_repository(db, access_token, repo_full_name, repository):
    """
    Replay the default branch from root (or from the last documented commit)
    up to HEAD, documenting each commit's changes in order.

    This is how a repo gets fully documented on first activation, and how a
    deactivation gap gets filled on reactivation:
      - If repository.documented_head_sha is set and found in the history,
        we start at the commit right AFTER it (fill only the gap).
      - Otherwise we start from the root commit (document everything).

    The registry is rebuilt as we walk, so diff_functions at each commit sees
    the exact state left by the previous commit — new/changed/deleted are
    detected per commit just like a live push.
    """
    default_branch = fetch_default_branch(access_token, repo_full_name)
    if not default_branch:
        print(f"[Backfill] {repo_full_name}: no default branch found")
        return {"status": "no_default_branch", "commits": 0}

    # newest-first from GitHub; reverse to walk oldest -> newest
    commits = fetch_commits_for_ref(access_token, repo_full_name, default_branch, per_page=100)
    commits = list(reversed(commits))

    # decide where to start
    start_index = 0
    if repository.documented_head_sha:
        for i, c in enumerate(commits):
            if c["sha"] == repository.documented_head_sha:
                start_index = i + 1  # start AFTER the already-documented commit
                break

    to_process = commits[start_index:]
    print(f"\n[Backfill] {repo_full_name}: {len(to_process)} commit(s) to document "
          f"(branch '{default_branch}', starting at index {start_index})")

    for commit in to_process:
        sha = commit["sha"]
        files = fetch_commit_files(access_token, repo_full_name, sha)

        added = _code_files(files, "added")
        modified = _code_files(files, "modified")
        removed = _code_files(files, "removed")

        print(f"[Backfill] {sha[:7]} — added:{len(added)} modified:{len(modified)} removed:{len(removed)}")

        # added files: every function is new
        for file_path in added:
            content = get_file_content(access_token, repo_full_name, file_path, sha)
            if not content:
                continue
            functions = extract_functions(content, file_path)
            for func in functions:
                process_function(db, repository.id, file_path, func["name"], func["source"], sha)
            update_registry(db, repository.id, file_path, functions)

        # modified files: diff against the registry (state of the previous commit)
        for file_path in modified:
            content = get_file_content(access_token, repo_full_name, file_path, sha)
            if not content:
                continue
            new, changed, deleted = diff_functions(db, repository.id, file_path, content)

            # added function
            for func in new:
                process_function(db, repository.id, file_path, func["name"], func["source"], sha)

            # modified function
            for func in changed:
                existing = get_latest_documentation(db, repository.id, file_path, func["name"])
                process_function(
                    db, repository.id, file_path, func["name"], func["source"], sha,
                    mode="modified", existing_documentation=existing.content if existing else "",
                )


            if deleted:
                # commit-tied tombstones come in Adım B; for now this soft-deletes
                mark_functions_deleted(db, repository.id, file_path, deleted, sha)

            update_registry(db, repository.id, file_path, new + changed)

        # removed files: soft-delete all their functions
        for file_path in removed:
            mark_file_deleted(db, repository.id, file_path, sha)

        # advance the high-water mark commit by commit
        repository.documented_head_sha = sha
        db.commit()

    print(f"[Backfill] {repo_full_name}: done ({len(to_process)} commits)")
    return {"status": "backfilled", "commits": len(to_process)}
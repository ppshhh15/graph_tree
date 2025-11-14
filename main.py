import argparse
import sys
import os
from urllib.parse import urlparse

def validate_package_name(name: str) -> str:
    if not name or not name.strip():
        raise ValueError("Package name cannot be empty.")
    return name.strip()

def validate_repo_url_or_path(repo: str) -> str:
    if not repo:
        raise ValueError("Repository URL or path must be provided.")
    parsed = urlparse(repo)
    if parsed.scheme in ('http', 'https'):
        return repo
    elif os.path.exists(repo):
        return os.path.abspath(repo)
    else:
        raise ValueError(f"Repository path does not exist and is not a valid URL: {repo}")

def validate_mode(mode: str) -> str:
    allowed_modes = {'online', 'offline', 'test'}
    if mode not in allowed_modes:
        raise ValueError(f"Mode must be one of {allowed_modes}, got: {mode}")
    return mode

def validate_max_depth(depth_str: str) -> int:
    try:
        depth = int(depth_str)
        if depth < 0:
            raise ValueError("Max depth must be non-negative.")
        return depth
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("Max depth must be an integer.")
        else:
            raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--mode", required=True, choices=["online", "offline", "test"])
    parser.add_argument("--max-depth", required=True)

    try:
        args = parser.parse_args()

        package = validate_package_name(args.package)
        repo = validate_repo_url_or_path(args.repo)
        mode = validate_mode(args.mode)
        max_depth = validate_max_depth(args.max_depth)

        print("Configuration:")
        print(f"  package = {package}")
        print(f"  repo = {repo}")
        print(f"  mode = {mode}")
        print(f"  max_depth = {max_depth}")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
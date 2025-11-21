import argparse
import sys
import os
import re
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError


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


def fetch_cargo_toml(repo: str, mode: str, package: str) -> str:
    parsed = urlparse(repo)

    if parsed.scheme in ('http', 'https'):
        if mode != 'online':
            raise ValueError("URL repository requires --mode online")
        try:
            req = Request(repo)
            with urlopen(req) as response:
                return response.read().decode('utf-8')
        except URLError as e:
            raise ValueError(f"Failed to fetch Cargo.toml from {repo}: {e}")
    else:
        if mode not in ('offline', 'test'):
            raise ValueError("Local repository requires --mode offline or test")
        cargo_path = os.path.join(repo, "Cargo.toml")
        if not os.path.isfile(cargo_path):
            raise ValueError(f"Cargo.toml not found at {cargo_path}")
        with open(cargo_path, 'r', encoding='utf-8') as f:
            return f.read()


def parse_dependencies(toml_content: str) -> list[str]:
    lines = toml_content.splitlines()
    in_dependencies = False
    dependencies = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line == "[dependencies]":
            in_dependencies = True
            continue
        elif line.startswith('[') and line != "[dependencies]":
            in_dependencies = False
            continue

        if in_dependencies:
            match = re.match(r'^([a-zA-Z0-9_-]+)\s*=', line)
            if match:
                dep_name = match.group(1)
                dependencies.append(dep_name)

    return dependencies


# --- Test mode handling ---
def parse_test_graph(repo_path: str) -> dict[str, list[str]]:
    graph = {}
    with open(repo_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                raise ValueError(f"Invalid line in test graph: {line}")
            pkg, deps_part = line.split(':', 1)
            pkg = pkg.strip()
            if not pkg or not pkg.isupper() or not pkg.isalpha():
                raise ValueError(f"Package name in test mode must be uppercase letters: {pkg}")
            deps = deps_part.split()
            graph[pkg] = deps
    return graph


def get_dependencies_test_mode(graph: dict[str, list[str]], package: str) -> list[str]:
    if package not in graph:
        raise ValueError(f"Package '{package}' not found in test graph.")
    return graph[package]


def build_dependency_graph(
        root_package: str,
        max_depth: int,
        fetcher_func,
        test_graph=None
) -> dict[str, list[str]]:
    if max_depth == 0:
        return {root_package: []}

    graph = {}
    stack = [(root_package, 0)]
    visited = set()

    while stack:
        current, depth = stack.pop()

        if depth >= max_depth:
            continue

        if current not in graph:
            graph[current] = []

        try:
            if test_graph is not None:
                deps = get_dependencies_test_mode(test_graph, current)
            else:
                deps = fetcher_func(current)
        except Exception as e:
            print(f"Warning: failed to fetch dependencies for '{current}': {e}", file=sys.stderr)
            deps = []

        for dep in deps:
            if dep not in graph[current]:
                graph[current].append(dep)

            if dep not in visited:
                visited.add(dep)
                stack.append((dep, depth + 1))

    return graph


def make_fetcher_func(repo: str, mode: str):
    parsed = urlparse(repo)

    if parsed.scheme in ('http', 'https'):
        url = repo

        def fetcher(package_name: str):
            try:
                req = Request(url)
                with urlopen(req) as response:
                    toml_content = response.read().decode('utf-8')
                return parse_dependencies(toml_content)
            except URLError as e:
                raise ValueError(f"Failed to fetch {url}: {e}")
    else:
        base_path = repo

        def fetcher(package_name: str):
            cargo_path = os.path.join(base_path, package_name, "Cargo.toml")
            if not os.path.isfile(cargo_path):
                raise ValueError(f"Cargo.toml not found for '{package_name}' at {cargo_path}")
            with open(cargo_path, 'r', encoding='utf-8') as f:
                toml_content = f.read()
            return parse_dependencies(toml_content)

    return fetcher


def get_installation_order(graph: dict[str, list[str]], root: str) -> list[str]:
    visited = set()
    order = []
    stack = [root]
    processed = set()

    while stack:
        node = stack[-1]
        if node in processed:
            stack.pop()
            continue

        visited.add(node)
        all_deps_processed = True

        for dep in reversed(graph.get(node, [])):
            if dep not in visited:
                stack.append(dep)
                all_deps_processed = False

        if all_deps_processed:
            processed.add(node)
            stack.pop()
            order.append(node)

    return order


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

        if mode == "test":
            if not os.path.isfile(repo):
                raise ValueError("--repo must be a file in test mode")
            test_graph = parse_test_graph(repo)
            dep_graph = build_dependency_graph(
                root_package=package,
                max_depth=max_depth,
                fetcher_func=None,
                test_graph=test_graph
            )

            install_order = get_installation_order(dep_graph, package)
            print("\nInstallation order (dependencies first):")
            for i, pkg in enumerate(install_order, 1):
                print(f"  {i}. {pkg}")
        else:
            fetcher = make_fetcher_func(repo, mode)
            dep_graph = build_dependency_graph(
                root_package=package,
                max_depth=max_depth,
                fetcher_func=fetcher,
                test_graph=None
            )

        print("\nDependency graph (up to max depth):")
        for pkg, deps in dep_graph.items():
            if deps:
                print(f"  {pkg} -> {', '.join(deps)}")
            else:
                print(f"  {pkg} -> (no dependencies)")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
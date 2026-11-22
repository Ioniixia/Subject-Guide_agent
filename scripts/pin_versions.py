"""Print the installed version of every package in requirements.txt, so the deployed build uses
the same versions that work on your computer.

    python scripts/pin_versions.py            # prints pinned lines
    python scripts/pin_versions.py --write    # rewrites requirements.txt with the pins
"""
import re
import sys
from importlib import metadata


def package_names(lines):
    names = []
    for line in lines:
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            names.append(re.split(r"[<>=!~\[; ]", line)[0])
    return names


def pinned(names):
    result, missing = [], []
    for name in names:
        try:
            result.append(f"{name}=={metadata.version(name)}")
        except metadata.PackageNotFoundError:
            missing.append(name)
    return result, missing


if __name__ == "__main__":
    with open("requirements.txt", encoding="utf-8") as f:
        names = package_names(f.read().splitlines())
    lines, missing = pinned(names)
    print("\n".join(lines))
    if missing:
        print("\nNot installed here (left out):", ", ".join(missing), file=sys.stderr)
    if "--write" in sys.argv and not missing:
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("\nrequirements.txt updated.", file=sys.stderr)

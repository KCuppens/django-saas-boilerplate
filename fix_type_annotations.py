#!/usr/bin/env python
"""Fix type annotations for Python 3.9 compatibility."""

import os
import re


def fix_file(filepath):
    """Fix type annotations in a single file."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    original_content = content

    # First ensure imports are correct
    if "from typing import" in content:
        # Check what needs to be imported
        needs_optional = " | None" in content or "| None" in content
        needs_union = (
            " | " in content and "None" not in content.split(" | ")[1]
            if " | " in content
            else False
        )
        needs_list = "list[" in content or "List[" in content
        needs_dict = "dict[" in content or "Dict[" in content

        # Build the import list
        imports = ["Any"] if "Any" in content else []
        if needs_dict:
            imports.append("Dict")
        if needs_list:
            imports.append("List")
        if needs_optional:
            imports.append("Optional")
        if needs_union:
            imports.append("Union")

        # Update the import line
        import_line = f"from typing import {', '.join(sorted(set(imports)))}"
        content = re.sub(r"from typing import .*", import_line, content)

    # Fix type annotations
    # Fix str | None -> Optional[str]
    content = re.sub(r"(\w+): str \| None", r"\1: Optional[str]", content)
    content = re.sub(r"(\w+): int \| None", r"\1: Optional[int]", content)
    content = re.sub(r"(\w+): bool \| None", r"\1: Optional[bool]", content)
    content = re.sub(r"(\w+): float \| None", r"\1: Optional[float]", content)

    # Fix User | None -> Optional[User]
    content = re.sub(r"(\w+): User \| None", r"\1: Optional[User]", content)

    # Fix list[str] | None -> Optional[List[str]]
    content = re.sub(r"(\w+): list\[str\] \| None", r"\1: Optional[List[str]]", content)
    content = re.sub(r"(\w+): list\[int\] \| None", r"\1: Optional[List[int]]", content)

    # Fix dict[str, Any] | None -> Optional[Dict[str, Any]]
    content = re.sub(
        r"(\w+): dict\[str, Any\] \| None", r"\1: Optional[Dict[str, Any]]", content
    )

    # Fix str | list[str] -> Union[str, List[str]]
    content = re.sub(
        r"(\w+): str \| list\[str\]", r"\1: Union[str, List[str]]", content
    )

    # Fix list[str] -> List[str]
    content = re.sub(r": list\[str\]", r": List[str]", content)
    content = re.sub(r": list\[int\]", r": List[int]", content)
    content = re.sub(r": list\[", r": List[", content)

    # Fix dict[str, Any] -> Dict[str, Any]
    content = re.sub(r": dict\[str, Any\]", r": Dict[str, Any]", content)
    content = re.sub(r": dict\[str, int\]", r": Dict[str, int]", content)
    content = re.sub(r": dict\[str, str\]", r": Dict[str, str]", content)
    content = re.sub(r": dict\[", r": Dict[", content)

    # Fix return types
    content = re.sub(r"\) -> dict\[str, Any\]:", r") -> Dict[str, Any]:", content)
    content = re.sub(r"\) -> dict\[str, int\]:", r") -> Dict[str, int]:", content)
    content = re.sub(r"\) -> dict\[str, str\]:", r") -> Dict[str, str]:", content)
    content = re.sub(r"\) -> list\[", r") -> List[", content)

    if content != original_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    return False


def main():
    """Fix all Python files in the apps directory."""
    fixed_count = 0

    files_to_fix = [
        "apps/accounts/models.py",
        "apps/emails/services.py",
        "apps/files/services.py",
        "apps/core/utils.py",
        "apps/featureflags/helpers.py",
    ]

    for filepath in files_to_fix:
        if os.path.exists(filepath) and fix_file(filepath):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()

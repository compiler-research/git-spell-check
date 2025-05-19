#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import glob
import argparse
from pathlib import Path

def parse_diff_content(diff_text):
    """Parse unified diff content and extract changed lines with their line numbers."""
    file_changes = {}
    current_file = None
    current_line = None

    for line in diff_text.splitlines():
        if line.startswith('+++'):
            current_file = line[4:]
            if current_file.startswith('b/'):
                current_file = current_file[2:]
        elif line.startswith('@@'):
            match = next((m for m in line.split() if m.startswith('+')), None)
            if match:
                try:
                    current_line = int(match.split(',')[0][1:])
                except ValueError:
                    current_line = None
        elif line.startswith('+') and not line.startswith('+++'):
            if current_file and current_line is not None:
                file_changes.setdefault(current_file, []).append((current_line, line[1:]))
                current_line += 1
    return file_changes

def is_detached_head():
    """Returns True if Git is in detached HEAD state."""
    result = subprocess.run(['git', 'symbolic-ref', '--quiet', 'HEAD'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return result.returncode != 0

def get_diff_files(base_branch="master", includes=None, excludes=None):
    if is_detached_head():
        if is_debug: print(f"Detached HEAD detected. Fetching '{base_branch}'...")
        subprocess.run(['git', 'fetch', 'origin', base_branch], text=True)

    cmd = ['git', 'diff', '--name-only', f"origin/{base_branch}"]
    if is_debug: print(f"git diff cmd: '{cmd}'")
    result = subprocess.run(cmd, capture_output=True, text=True)

    changed_files = set(result.stdout.strip().splitlines())

    if is_debug: print(f"All files '{changed_files}'")
    # Helper to glob and normalize paths
    def glob_relative(patterns):
        paths = set()
        for pattern in patterns:
            for path in glob.glob(pattern, recursive=True):
                try:
                    repo_root = Path(".").resolve()
                    rel = str(Path(path).resolve().relative_to(repo_root))
                    paths.add(rel)
                except ValueError:
                    continue  # ignore files outside repo
        return paths

    included = glob_relative(includes)
    excluded = glob_relative(excludes)

    changed_files = sorted((changed_files & included) - excluded)
    if is_debug: print(f"Filtered files {changed_files}")

    return changed_files


def get_diff_lines(file, base_branch="master"):
    cmd = ['git', 'diff', '-U0', f"origin/{base_branch}", '--', file]
    if is_debug: print(f"Diff cmd '{cmd}'")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return parse_diff_content(result.stdout).get(file, [])


def run_spell_checker(lines, cmd="aspell list", dictionary_words=None):
    if is_debug: print(f"Aspell cmd '{cmd}'")
    process = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    input_text = '\n'.join([text for _, text in lines])
    out, _ = process.communicate(input=input_text)
    misspelled = set(out.strip().splitlines())
    annotations = []
    for lineno, line in lines:
        for word in line.split():
            clean = ''.join(filter(str.isalpha, word))
            if clean and clean in misspelled:
                if dictionary_words and clean in dictionary_words:
                    continue
                annotations.append((lineno, clean, line.strip()))
    return annotations


def emit_github_annotations(file, annotations):
    for lineno, word, context in annotations:
        if is_debug: print(f"Emitting github annotation for file='{file}',line='{lineno}'")
        print(f"::error file={file},line={lineno}::Possible typo: '{word}' in line: {context}")


def emit_console_output(file, annotations):
    for lineno, word, context in annotations:
        print(f"{file}:{lineno}: typo: '{word}' in: {context}")


def main():
    parser = argparse.ArgumentParser(
        description="Spell check only changed lines in Git diffs or a diff file."
    )
    parser.add_argument('--base-branch', default=os.getenv("INPUT_BASE_BRANCH",
                                                           "master"),
                        help='Branch to diff against (ignored if --diff-file is set)')
    parser.add_argument('--include', default=os.getenv("INPUT_INCLUDE",
                                                       '["**/*.md","**/*.txt",'
                                                       '"**/*.rst","**/*.json",'
                                                       '"**/*.yaml","**/*.yml",'
                                                       '"**/*.ini","**/*.tex",'
                                                       '"**/*.html","**/*.xml",'
                                                       '"**/*.xhtml", "**/*.csv"]'),
                        help='JSON list of glob patterns to include')
    parser.add_argument('--exclude', default=os.getenv("INPUT_EXCLUDE", '[]'),
                        help='JSON list of glob patterns to exclude')
    parser.add_argument('--cmd', default=os.getenv("INPUT_CMD",
                                                   "aspell --mode=sgml"
                                                   "       --add-sgml-skip=code,pre,style,script,command,literal,ulink,parameter,filename,programlisting"
                                                   "       --lang=en list"),
                        help='Spell checker command (default: aspell list)')
    parser.add_argument('--dictionary', default=os.getenv("INPUT_DICTIONARY", ""),
                        help='Space-separated list of allowed words')
    parser.add_argument('--console-output', action='store_true',
                        help='Emit console output instead of GitHub-style error annotations')
    parser.add_argument('--diff-file', help='Path to a unified diff file (optional)')
    parser.add_argument("--input-string", help="Raw text string to spellcheck directly (optional)")
    parser.add_argument("--debug", action='store_true',
                        help="Raw text string to spellcheck directly (optional)")

    args = parser.parse_args()

    global is_debug
    is_debug = os.getenv("INPUT_DEBUG") or args.debug

    includes = json.loads(args.include)
    excludes = json.loads(args.exclude)
    dictionary_words = set(args.dictionary.split()) if args.dictionary else set()

    if args.input_string:
        lines = bytes(args.input_string, "utf-8").decode("unicode_escape")
        if lines.lstrip().startswith('diff'):
            file_changes = parse_diff_content(lines)
        else:
            file_changes = {"<stdin>": [(i + 1, line) for i, line in enumerate(lines.splitlines())]}
    elif args.diff_file:
        if not os.path.isfile(args.diff_file):
            print(f"❌ Diff file not found: {args.diff_file}")
            sys.exit(1)
        with open(args.diff_file, 'r') as f:
            diff_text = f.read()
        file_changes = parse_diff_content(diff_text)
    else:
        files = get_diff_files(args.base_branch, includes, excludes)
        if not files:
            print("✅ No files to check.")
            return
        file_changes = {f: get_diff_lines(f, args.base_branch) for f in files}

    any_issues = False
    for file, lines in file_changes.items():
        annotations = run_spell_checker(lines, args.cmd, dictionary_words)
        if annotations:
            any_issues = True
            if args.console_output:
                emit_console_output(file, annotations)
            else:
                emit_github_annotations(file, annotations)

    if any_issues:
        sys.exit(1)
    else:
        print("✅ No typos found.")


if __name__ == "__main__":
    main()

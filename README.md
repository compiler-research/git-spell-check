# git-spell-check

Run aaa spell checker **only on changed lines in pull requests**.

## Features

- Only checks added/modified lines
- Ignore custom words
- Works with any spell checker (default: `aspell`)
- Uses GitHub annotations for inline results

## Usage

```yaml
- uses: compiler-research/git-spell-check@v1
  with:
    base_branch: origin/master
    include: '["**/*.md"]'
    exclude: '["CHANGELOG.md"]'
    cmd: "aspell list"
    dictionary: "Compiler-Research GitHub Actions"
```

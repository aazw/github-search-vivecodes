# github-search-vivecodes

* Utilizes the [GitHub Code Search API](https://docs.github.com/en/rest/search/search#search-code)
* Performs code search with `sort=indexed&order=desc` to find recently added files and outputs results in Atom feed format
* Should work as long as the API supports `sort=indexed` (reportedly will be deprecated eventually)
* Hosts and regularly updates results for the following queries using GitHub Actions � GitHub Pages:
    * `filename:.clinerules`
    * `filename:CLAUDE.md`

## Setup

1. Recommended to start with VSCode Dev Container ([.devcontainer/](./.devcontainer))
2. Initialize with Task (Taskfile) ([Taskfile.yml](./Taskfile.yml))

  ```bash
  task uv_sync
  ```

## Usage

```bash
python src/github_search.py --query "filename:CLAUDE.md" --token YOUR_GITHUB_TOKEN
```

## Options

- `--query`, `-q`: Search query (required)
- `--token`, `-t`: GitHub API token (required/environment variable available)
- `--output`, `-o`: Output file path (stdout if omitted)
- `--log-level`, `-l`: Log level (DEBUG/INFO/WARNING/ERROR)

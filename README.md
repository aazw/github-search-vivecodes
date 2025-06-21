# github-search-vivecodes

GitHub Code Search APIを使用してコード検索を行い、結果をAtomフィード形式で出力するツールです.  
[Code Search API](https://docs.github.com/en/rest/search/search#search-code)が `sort=indexed`に対応しているまで使えるはず. (いずれなくなるらしい)

## 使用方法

```bash
python src/github_search.py --query "filename:CLAUDE.md" --token YOUR_GITHUB_TOKEN
```

## オプション

- `--query`, `-q`: 検索クエリ（必須）
- `--token`, `-t`: GitHub APIトークン（必須）
- `--output`, `-o`: 出力ファイルパス（省略時は標準出力）
- `--log-level`, `-l`: ログレベル（DEBUG/INFO/WARNING/ERROR）

## セットアップ

```bash
task uv_sync
```

# github-search-vivecodes

* [GitHub Code Search API](https://docs.github.com/en/rest/search/search#search-code)を利用
* `sort=indexed&order=desc`なコード検索で最近追加されたファイルの検索を行い、結果をAtomフィード形式で出力する
* APIが`sort=indexed`に対応しているまで使えるはず (いずれなくなるらしい)
* Github Actions x GitHub Pagesで以下のクエリ結果をホスティング・定期更新
    * `filename:.clinerules`
    * `filename:CLAUDE.md`

## セットアップ

1. VSCode Dev Containerでの起動推奨 ([.devcontainer/](./.devcontainer))
2. Task(Taskfile)で初期化処理 ([Taskfile.yml](./Taskfile.yml))

  ```bash
  task uv_sync
  ```

## 使用方法

```bash
python src/github_search.py --query "filename:CLAUDE.md" --token YOUR_GITHUB_TOKEN
```

## オプション

- `--query`, `-q`: 検索クエリ（必須）
- `--token`, `-t`: GitHub APIトークン（必須/環境変数利用可）
- `--output`, `-o`: 出力ファイルパス（省略時は標準出力）
- `--log-level`, `-l`: ログレベル（DEBUG/INFO/WARNING/ERROR）

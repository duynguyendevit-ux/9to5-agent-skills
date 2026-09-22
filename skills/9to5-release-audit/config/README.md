# Release audit configuration

Copy `endpoints.example.json` to `endpoints.json` and set the internal Confluence
base URL. The real file is gitignored and should remain mode `600`.

The Confluence token is read from the existing zjira configuration or the local
`~/.config/opencode/release-sync.json` secret overlay. It is never printed or
stored in snapshots.

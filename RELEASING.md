# Releasing kaiten-mcp

Releases are published from GitHub Actions when a GitHub Release with a matching
`vX.Y.Z` tag is published. The workflow produces:

- wheel and source distribution on PyPI for `uvx kaiten-mcp`;
- a multi-platform Streamable HTTP image on GHCR;
- metadata in the Official MCP Registry.

The release workflow uses short-lived GitHub OIDC credentials. Do not add PyPI
or MCP Registry tokens to repository secrets.

## One-time setup

### PyPI

1. Sign in to [PyPI](https://pypi.org/) and confirm that the `kaiten-mcp`
   project name is available.
2. Create a pending Trusted Publisher for the first release, or configure one
   on the existing project:
   - Owner: `evvfebruary`
   - Repository: `kaiten-mcp`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. In the GitHub repository, create an environment named `pypi`.
4. Add required reviewers to that environment if releases need a manual
   approval gate.

The workflow has `id-token: write` only in the publishing jobs. PyPI exchanges
that identity for a short-lived upload credential.

### GitHub Packages / GHCR

The workflow publishes `ghcr.io/evvfebruary/kaiten-mcp` with the repository
`GITHUB_TOKEN`; no PAT is required.

The repository is private, so after the first image is published:

1. Open the package settings on GitHub.
2. Confirm the package is linked to this repository.
3. Change package visibility to **Public**.

Public visibility is required for unauthenticated users to pull marketplace and
deployment images.

### Official MCP Registry

The Registry manifest uses the GitHub-owned namespace
`io.github.evvfebruary/kaiten-mcp`. The workflow authenticates with
`mcp-publisher login github-oidc`; no Registry secret is required.

The Registry validates the public PyPI package before accepting `server.json`.
The hidden `mcp-name` marker in `README.md` proves package ownership.

## Create a release

1. Choose a SemVer version without the `v` prefix, for example `0.2.0`.
2. Update the Python project and lock file:

   ```bash
   uv version 0.2.0
   uv lock
   ```

3. Set both `version` fields in `server.json` to the same value.
4. Validate the release locally:

   ```bash
   python scripts/check_release_metadata.py
   uv sync --locked --group dev
   uv run ruff check .
   uv run ruff format --check .
   uv run ty check
   uv run pytest -m "not live"
   uv run kaiten-mcp-benchmark --check
   uv build
   ```

5. Merge the version change after CI passes.
6. Create a GitHub Release from that commit with tag `v0.2.0`.
7. Publish the GitHub Release. Publishing, not merely creating a draft or tag,
   starts `.github/workflows/release.yml`.
8. If the protected `pypi` environment requires approval, approve that
   deployment.

The workflow rejects a tag that does not match `pyproject.toml` and
`server.json`.

## Verify a release

After the workflow succeeds:

```bash
uvx --from kaiten-mcp==0.2.0 kaiten-mcp --help
docker pull ghcr.io/evvfebruary/kaiten-mcp:0.2.0
```

Search the Official MCP Registry for:

```text
io.github.evvfebruary/kaiten-mcp
```

The image also receives floating major/minor tags and `latest` for normal
releases. Prereleases do not update `latest`.

## Marketplace reach

The release pipeline deliberately publishes only to durable artifact and
metadata registries:

- **PulseMCP** and **Glama** ingest the Official MCP Registry automatically.
- **mcp.so** and **cursor.directory** require one-time/manual submissions and
  do not expose a stable release API.
- **Cursor Marketplace** requires a public repository, Cursor plugin metadata,
  and manual review for the initial listing and every update.
- **Smithery** exposes a publishing API, but it requires separate credentials
  and distribution metadata. Add it as an independent workflow only if a
  Smithery-specific release is desired.

Do not grant every directory release credentials. Claim or submit the first
listing manually where needed, and use the Official MCP Registry as the
canonical machine-readable release record.

## Recovery

- Re-run a failed GitHub Actions job rather than creating a second release for
  the same version.
- PyPI and the Official MCP Registry do not allow replacing published version
  contents. If published artifacts are wrong, create a new patch version.
- If GHCR succeeded but PyPI or the Registry failed, it is safe to re-run only
  the failed jobs; the image digest remains attested to the release workflow.

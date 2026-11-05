# kaiten-mcp

[Русский](README.md) | English

An MCP server that connects [Kaiten](https://kaiten.ru/) tasks and kanban boards to AI assistants. Find cards, create tasks, move work between columns, and manage comments and tags from your chat.

- Compact responses keep large API payloads out of the model's context.
- Run locally over stdio, or self-host Streamable HTTP with Docker or Kubernetes.
- Bring your own Kaiten API token; HTTP requests use each caller's token.
- Optional [Kaiten skill](skills/kaiten/SKILL.md) guides everyday task work and board reviews.

## Quick start in Cursor

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), and a Kaiten API token from your profile's API-key page. No repository clone is required to run the server.

Set these variables in the environment inherited by Cursor, then fully restart Cursor from that environment:

```bash
export KAITEN_API_TOKEN='your-token'
export KAITEN_WORKSPACE_SLUG='your-company'
```

Merge this entry into your project's `.cursor/mcp.json` (keep any existing servers):

```json
{
  "mcpServers": {
    "kaiten": {
      "command": "uvx",
      "args": ["kaiten-mcp", "--transport", "stdio"],
      "env": {
        "KAITEN_API_TOKEN": "${env:KAITEN_API_TOKEN}",
        "KAITEN_WORKSPACE_SLUG": "${env:KAITEN_WORKSPACE_SLUG}"
      }
    }
  }
}
```

`uvx` downloads the package from PyPI into an isolated environment. Ensure it is on Cursor's PATH. Check that the `kaiten` server connects, then ask “Show my Kaiten spaces.” Keep actual tokens out of committed configuration and chat.

For on-premises or custom domains, replace the workspace-slug entry with `"KAITEN_BASE_URL": "${env:KAITEN_BASE_URL}"` and export your API root, for example `https://kaiten.example.com/api/v1`.

See [Cursor's MCP documentation](https://cursor.com/docs/mcp) for configuration details. Other clients can launch the same `uvx kaiten-mcp --transport stdio` command. For self-hosting, see the [Russian deployment guide](README.md#удалённый-сервер--docker--kubernetes) and [remote client configurations](examples/remote-mcp/).

## Install the companion skill

The MCP server provides tools and access to Kaiten. The skill provides instructions for choosing and using those tools; it does not install the server or supply credentials.

Download the [skill file](skills/kaiten/SKILL.md) and save it as `.cursor/skills/kaiten/SKILL.md` in the project where you use Cursor. Alternatively, from a local clone of this repository:

```bash
mkdir -p /path/to/your-project/.cursor/skills/kaiten
cp skills/kaiten/SKILL.md /path/to/your-project/.cursor/skills/kaiten/SKILL.md
```

Replace `/path/to/your-project` with your project's path. Review any existing skill before replacing it. Start a new Agent chat and check that the skill is available. Cursor can select it for matching Kaiten requests; see [Cursor's skills documentation](https://cursor.com/docs/skills). The same standalone file can be copied into another skill-capable client's documented skill directory.

## Try it

- “Find the login bug on the Product board and show its description.”
- “Create a task on the Product board to add a password visibility toggle. Include acceptance criteria: toggling preserves the input, and the control works with the keyboard.”
- “Move card #1234 to In Progress and add the comment: Ready for implementation.”
- “Review the Product backlog. Suggest which task descriptions need clarification; leave the cards unchanged.”
- “Summarize the current board by column and link the cards that need attention.”

Board reviews describe the current data and identify incomplete coverage. Historical throughput and cycle-time reports are not provided by these tools.

## Demo

The [Cursor recording scenario](docs/demo.md) covers creating a card, moving it and reviewing demo tasks. The dedicated fixture is prepared; the real Cursor recording is still pending. See the [fixture setup and checks](CHECKING.md#воспроизводимый-демо-стенд).

## Development and license

See [README.md](README.md#разработка) for development commands and [CHECKING.md](CHECKING.md) for compatibility checks. Distributed under the [MIT license](LICENSE), including the companion skill.

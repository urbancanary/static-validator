# static-validator MCP server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes the [static-validator](https://github.com/urbancanary/static-validator) bond-static validation toolkit to Claude Desktop, Claude Code, and any other MCP-compatible client.

The server runs locally on your machine. Bond data you ask Claude to validate is hashed inside this process; in the bundled-fixtures variant (v0.1) no network call is made at all.

## Install

```bash
pip install static-validator-mcp
```

Or from a local checkout (the layout this repo ships with):

```bash
pip install -e ./python -e ./mcp
```

## Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the platform equivalent:

```json
{
  "mcpServers": {
    "static-validator": {
      "command": "static-validator-mcp"
    }
  }
}
```

Restart Claude Desktop. The tools become available to the model — try asking:

> "What ISINs does the static validator know about?"
>
> "Fetch the canonical record for US698299BL70."
>
> "Validate this bond against the canonical: ISIN US698299BL70, coupon 3.87, day count ISMA_30_360, frequency 2, maturity 2060-07-23."

## Tools

| Tool | Purpose |
|---|---|
| `list_known_isins` | Discovery: which ISINs this installation has canonical records for |
| `fetch_canonical_record` | Return the full PublishedRecord for an ISIN (tier hashes, structural flags, sources, where_to_find) |
| `validate_bond_static` | Hash the user's local bond, compare against canonical, surface match status + mismatched fields + structural warnings + sourcing hints |

See the [project SCHEMA.md](../SCHEMA.md) for the canonical schema spec and the [schema/ directory](../schema/) for the wire format.

## What's bundled (v0.1)

This server ships with one canonical record: PANAMA 3.87% 07/23/2060 (US698299BL70), prospectus-confirmed against SEC EDGAR. Subsequent releases will bundle more bonds and add an opt-in remote fetch from the public read API.

## Privacy

- Hashing happens locally inside this process.
- The bundled-fixtures variant makes no network call.
- When the remote fetch path ships, the only data sent will be the public ISIN — never bond field values. The wire contract physically refuses requests carrying field values; see [`../schema/validate_request.schema.json`](../schema/validate_request.schema.json).

## License

MIT.

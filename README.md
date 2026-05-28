# Astrid

Astrid is a harness toolkit for agents and humans to make art.

> **Agents:** Read [`AGENTS.md`](./AGENTS.md) — the canonical operating guide.
> The entrypoint flow is `python3 -m astrid next` → `python3 -m astrid status`.
> Attach only when instructed.

## Quick start

```bash
git clone https://github.com/peteromallet/Astrid.git
cd Astrid
python3 -m astrid next            # get the next legal action
python3 -m astrid status          # show session and project detail when needed
python3 -m astrid attach <project>  # bind to a project (only when instructed)
```

Deeper discovery (`orchestrators list`, `executors list`, `doctor`, etc.)
follows after session binding — see [`docs/architecture.md`](docs/architecture.md).

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).

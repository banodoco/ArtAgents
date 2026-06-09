# Astrid

Astrid is a Python SDK for building and running open-source agentic UXes — a harness toolkit for agents and humans to make art.

New here? Start with **[Build your first agentic UX](docs/guides/build-your-first-agentic-ux.md)**.

## How it works

Give this to your agents to get started:

<div align="center">

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ·                                                                        · ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳               ═══  A S T R I D  ═══                ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃                                                                            ┃
┃                             ◇  What This Is  ◇                             ┃
┃            a harness toolkit for agents and humans to make art             ┃
┃                                                                            ┃
┃                EXECUTORS      perform one piece of work                    ┃
┃                ORCHESTRATORS  combine executors together                   ┃
┃                ELEMENTS       reusable pieces used by both                 ┃
◇                                                                            ◇
┃                           ◇  Getting Started  ◇                            ┃
┃            git clone https://github.com/peteromallet/Astrid.git            ┃
┃        python3 -m astrid next      # cold start: one legal next action     ┃
┃        python3 -m astrid status    # the read-side breadcrumb              ┃
┃        python3 -m astrid attach <project>   # bind when next/status says   ┃
┃                      — then, with a session bound: —                       ┃
┃        python3 -m astrid [executors|orchestrators|packs] list              ┃
┃        python3 -m astrid modalities list                                   ┃
┃        python3 -m astrid elements list --kind <kind>                       ┃
┃        python3 -m astrid [executors|orchestrators] inspect <id>            ┃
┃        python3 -m astrid elements inspect <kind> <element_id>              ┃
┃        python3 -m astrid [executors|orchestrators] run <id> -- <args>      ┃
┃        python3 -m astrid doctor       # health check                       ┃
┃        python3 -m astrid setup        # configure local env                ┃
◇                                                                            ◇
┃                          ◇  Make Something New  ◇                          ┃
┃            copy docs/templates/{executor,orchestrator,element}/            ┃
┃                        read docs/guides/creating-tools.md                         ┃
┃                                                                            ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳          ask the maker what they must do           ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳         docs/guides/ideas.md has a thought or two         ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳        runs/ is where the outputs stay              ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳          just begin, you'll find your way          ╳ ╳ ╳ ╳ ╳   ┃
┃   ╳ ╳ ╳ ╳ ╳────────────────────────────────────────────────────╳ ╳ ╳ ╳ ╳   ┃
┃ ·                                                                        · ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━◇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

</div>

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).

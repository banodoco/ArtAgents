# Astrid

A Python SDK for building and running open-source agentic UXes — a harness for agents and humans to make art.

**Give this to your agent to get started:**

<div align="center">

<pre>
╭──────────────────────────── ◇ ─────────────────────────────╮
│                                                            │
│                   A   S   T   R   I   D                    │
│                                                            │
│              agents harnessed, humans free —               │
│               open tools for what could be:                │
│              moving image, voice, and frame,               │
│            clone it, run it, stake your claim.             │
│                                                            │
│                          ·  ·  ·                           │
│                                                            │
│       <em>$ git clone https://github.com/banodoco/Astrid</em>       │
│              <em>$ cd Astrid &amp;&amp; pip install -e .</em>               │
│                 <em>$ python3 -m astrid --help</em>                 │
│                                                            │
│                          ·  ·  ·                           │
│                                                            │
│                 ask the maker what to do,                  │
│             runs/ holds all it makes for you —             │
│              no map, no plan, no perfect day:              │
│         begin, hold fast  — you'll find your way.          │
│                                                            │
╰──────────────────────────── ◇ ─────────────────────────────╯
</pre>

</div>

Astrid's product CLI and Python SDK are clients of the Banodoco workspace
runtime. Start the runtime with `banodoco-local up --profile astrid`, then use
the generated-client-backed `python3 -m astrid` gateway or `import astrid`.
The runtime owns projects, media, timelines, tasks, runs, receipts, and event
history; Astrid does not use a checkout-local project database as live
authority. See [Getting Started](docs/getting-started.md).

## License

Open Source Native License (OSNL) v0.2 — see [`LICENSE`](LICENSE).

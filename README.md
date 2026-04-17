# smallville-mini-reinterpretation

A mini reinterpretation of Joon Sung Park et al.'s **Generative Agents: Interactive Simulacra of Human Behavior** (Park et al., 2023). Scoped for research/demo replay.

## What this is

**Keeps** the paper's core contribution:
- The 5-stage cognitive loop: `perceive → retrieve → plan → reflect → execute` (+ `converse`)
- 3-tier memory: associative (long-term), scratch (working), spatial (world knowledge)
- Retrieval scored by `recency * relevance * importance`

**Adds**:
- **Model tiering**: cheap calls (perceive/execute) → `gemini-2.5-flash-lite`, plan → `gemini-2.5-flash`, reflect → `gemini-2.5-pro`
- **Structured output** via Pydantic schemas, no regex fallback loops
- **Replay-first design**: simulation writes an event log, web player reads it, GIF capture is headless playback

**GIF**


## Directory layout

```
smallville_2026/
├── config.yaml              # scenario config (models, tick count, scene)
├── src/
│   ├── llm/                 # Gemini client, prompts, embeddings
│   ├── memory/              # associative / scratch / spatial
│   ├── cognition/           # perceive / retrieve / plan / reflect / execute / converse
│   ├── world/               # location graph
│   ├── agent/               # persona
│   └── simulation/          # engine + event recorder
├── scripts/
│   ├── run_sim.py           # run N ticks, write events.json
│   └── capture_gif.py       # headless web playback → GIF
├── data/
│   ├── personas/*.yaml      # persona definitions
│   └── worlds/*.yaml        # scene config (locations + adjacency)
├── web/                     # icon+dialogue timeline player (vanilla JS)
└── output/
    ├── runs/<run_name>/     # per-run events.json + memory snapshots
    └── gifs/                # captured GIFs
```

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. set API key
#    the runner looks for .env.local first, then .env, walking up from CWD
#    so placing .env.local in the parent dir (projects/.env.local) also works
cp .env.example .env   # or create .env.local in this dir or a parent
# then set GEMINI_API_KEY=...

# 3. BEFORE spending any credits: preview the UI with synthetic data
python scripts/make_demo_data.py
python -m http.server 8000 --directory web
# open http://localhost:8000/?run=demo

# 4. run simulation (reads config.yaml by default)
#    CAUTION: default 40 ticks × 3 personas ≈ $0.7–$1.5 in Gemini credits
#    for a first real run try --ticks 5 (≈ $0.10)
python scripts/run_sim.py --ticks 5

# 4. preview in browser
python -m http.server 8000 --directory web
# open http://localhost:8000/?run=cafe-morning

# 5. capture GIF (requires playwright browsers installed)
playwright install chromium
python scripts/capture_gif.py --run cafe-morning --fps 6
# output: output/gifs/cafe-morning.gif
```

## How the loop runs per tick

```
for persona in personas:
    perceived   = perceive(persona, world)           # who/what is here?
    memories    = retrieve(persona, perceived)       # top-k relevant nodes
    plan        = plan(persona, perceived, memories) # {move|speak|idle}
    execute(plan)                                    # update location / trigger conversation
    if persona.should_reflect(): reflect(persona)    # synthesize higher-level thoughts
    recorder.log(...)                                # append to event log
```

Each loop iteration emits structured events to `output/runs/<run>/events.json`, which the web player consumes.

## Attribution

This project is an independent reimplementation of the architecture described in:

> Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris,
> Percy Liang, and Michael S. Bernstein. 2023.
> *Generative Agents: Interactive Simulacra of Human Behavior.*
> In Proceedings of UIST '23.
> [Paper](https://arxiv.org/abs/2304.03442) ·
> [Original repo](https://github.com/joonspk-research/generative_agents)

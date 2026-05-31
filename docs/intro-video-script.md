# Astrid — Intro Video (capture & clip guide)

> **Approach:** Don't perform a script. Do a long (~20–60 min) screen recording where you
> actually use Astrid and *talk through it as you go* — reacting to results in real time.
> Then clip the good bits of talking + the good screen moments down to ~3 min.
> Organic source → organic feel. Target: r/StableDiffusion. Goal: reads like a builder
> sharing what they made, not a product launch.
>
> This doc is **not lines to read.** It's (1) a checklist so you cover every beat while you
> ramble, and (2) a guide for what to keep when you cut it down.

---

## While recording — ground rules

- **Narrate as the result appears, not after.** Your live reaction ("oh, Z-Image actually
  nailed that", "huh, that LoRA's overcooked") is the most valuable audio you'll get. Can't
  fake it, can't re-script it.
- **Leave the failures in the take.** A retry, a janky output, a "let me fix that" is what
  makes it credible to that sub. You'll clip one or two in on purpose.
- **Don't explain what Astrid *is* up front.** Just start doing something. The "what is this"
  can come at the very end, almost as a footnote. (See Outro.)
- **It's fine to ramble.** The checklist below is just so you don't *finish the hour and
  realize you skipped the ControlNet step.* Hit these beats in roughly this order and the
  edit assembles itself.

---

## Beat checklist (cover these while you talk)

### 1 — Best realistic model, then make it yours
- [ ] Generate the same prompt across **Qwen / Flux 2 / Z-Image**, show as a collage
- [ ] Say which you picked and why (out loud, reacting to the grid)
- [ ] Find **LoRAs** for it (Hugging Face search), try a few, react to which looks real
- [ ] Find pose refs + **ControlNet**, pose the character mid-race (via VibeComfy)

### 2 — Train a character LoRA (Frank, It's Always Sunny)
- [ ] Pull training data off **YouTube**, build a dataset
- [ ] Show the **approve/deny dataset UI** — actually reject a bad one on camera
- [ ] Hit train → **RunPod + AI Toolkit** spins up
- [ ] Generate clips → land on **the Frank clip saying [your line]** ← the punchline

### 3 — Navigable 2D audioscape
- [ ] Explain the idea in one breath ("different parts of the video have their own sound")
- [ ] Split video into segments → **HunyuanVideo Foley** per segment (VibeComfy)
- [ ] Tweak segments in the UI
- [ ] Show it stitched back over the video, **navigable in a browser**

### 4 — It edited this video
- [ ] Hand it the clips → **timeline** lays out
- [ ] Edit / re-render / add effects, tweaking until happy
- [ ] "...and that's this video" reveal

### Outro (say it offhand, near the end)
- [ ] Runs **locally on your own machine**, tested with **DeepSeek + other open models**
- [ ] Comes with **packs built in**; you can **build your own and share them** (keep this
      casual — not a flywheel pitch)
- [ ] Point to repo / setup commands

---

## Clip / edit guide (turning the hour into ~3 min)

**Structure the cut results-first, name-last:**
- Open **cold on an actual result** (the collage or a Frank clip) with zero framing.
- Let "this is a thing I built called Astrid, it drives ComfyUI, it's open" land *after*
  they've already seen something cool — or only at the very end.

**What to keep:**
- Moments where you **react to a result in real time** — those sell it.
- **One visible failure/retry.** Flawless reads as an ad; one stumble reads as real.
- The **Frank clip** — your single most shareable 5 seconds. If you cut hard, keep this.
- Tight transitions: "then I wanted..." / "so I had it..." — let your own connective
  tissue do the narration.

**What to cut:**
- Any sentence that defines or sells Astrid in the abstract ("leverage the ecosystem",
  "powerful", "unlock"). If it sounds like a tagline, cut it.
- Dead air while things generate — speed-ramp or jump-cut through render waits.
- Tangents that don't serve one of the four beats.

**Pacing target:** ~3 min. Four beats ≈ 35–45s each + ~10s cold open + ~15s outro.
If it's running long, Frank (beat 2) is the keeper; beat 4 is the most expendable.

---

## Production / post notes

- [ ] Keep production value *low* on purpose — raw-ish screen capture beats a polished promo
      on r/SD. Minimal/no music. Looks like a recording, not a launch video.
- [ ] Lower-third tool labels as each appears (optional, light): ComfyUI · HF skill ·
      VibeComfy · ControlNet · RunPod + AI Toolkit · HunyuanVideo Foley
- [ ] Reddit title: concrete, no adjectives. e.g. *"I built an agent that drives ComfyUI —
      had it compare Qwen/Flux2/Z-Image, train a LoRA, and generate spatial audio"*
- [ ] Confirm exact setup command(s) for the outro / post body
- [ ] Record the Frank VO line (beat 2)

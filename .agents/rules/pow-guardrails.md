# Proof of Wonder — Production Guardrails (always on)

These rules apply to every task in this workspace (`/Applications/code/science-knowledge`).

1. **Zero cost.** Use only free local tools and open-weight models. Never call paid APIs, never enable
   Google Cloud Vertex AI or any billing-linked service. ElevenLabs is used only if `ELEVENLABS_API_KEY`
   is already set by the user; never ask for or create keys yourself.
2. **No publishing without explicit approval.** Never run `cli.py publish`, never POST to
   `/api/youtube/upload`, never schedule or make a video public unless the user says so in the current
   conversation for that specific episode.
3. **Never overwrite completed work.** Respect `PROTECTED_COMPLETED_OUTPUT_DIRS` in
   `youtube-shorts-channel/pipeline/pow_studio/schema.py`. Experiments go into a NEW slug/output_dir.
   Never edit or delete files inside a protected episode folder.
4. **License whitelist is code, not opinion.** Only Public Domain, CC0, CC BY, or first-party original
   media. `rights_gate.validate_license_string` is the authority (it rejects NC, ND and ShareAlike/BY-SA,
   even though older docs mention CC BY-SA). ESA main multimedia (CC BY-SA IGO) and JAXA are excluded.
   Strip audio from NASA SVS / ESA videos (third-party music risk).
5. **Footage first, honest media.** Run the visual feasibility gate before locking narration. Never
   present stills, Ken Burns moves, AI imagery, reenactments, or proxy locations as real footage of the
   narrated event. Keep `source_media_class` derived from pixels (`inspect_media_authenticity`).
6. **Use the studio environment.** Python is `youtube-shorts-channel/.venv/bin/python` (Python 3.11).
   Run `pytest youtube-shorts-channel/pipeline/tests -q` after code changes and report the result.
   ytb-tools is a separate git submodule (Next.js 16): read `ytb-tools/AGENTS.md` before editing it.
7. **Pause points need the user.** Voice lock, storyboard approval, thumbnail choice, and publishing
   always stop and wait for the user. Do not self-approve.

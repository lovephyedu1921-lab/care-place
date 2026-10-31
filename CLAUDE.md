# CLAUDE.md

## Instagram agent skills (`.claude/skills/ig-*`)

Installed from https://github.com/Jakeschincariol/instagram-agent-skill (MIT, see
`.claude/skills/INSTAGRAM-AGENT-SKILL-LICENSE`).

The skills refer to `~/.claude/instagram/` for `voice.md`, `swipe.md`, `log.md` and
`plan.md`. Cloud sessions lose the home directory, so in this repo use
`.claude/instagram/` (relative to the repo root) instead, wherever a skill says
`~/.claude/instagram/`. For `swipe.py`, pass `--out .claude/instagram/swipe.md`.

Fill in `.claude/instagram/voice.md` before using the skills; every skill reads it.

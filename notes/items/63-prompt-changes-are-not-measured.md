# 63. Changes to what the model is told are not measured — adopt SkillOpt's validation-gated edit loop

Open item, filed 2026-10-07. Design only — nothing built. Its row in the [todo.md](../todo.md) index carries the current status.

---

**The problem.** The agent rules, `TOOL_SECTIONS` and domain rules in `src/agent_loop.py` are edited by judgement and checked, if at all, on a single run. Item 20 is what that produces: a 116-line rules block that has never reached a model, and nobody could tell from behaviour. The first rule-adherence reading was 1 of 4.

**The idea, taken from Microsoft's SkillOpt** ([project page](https://microsoft.github.io/SkillOpt), [repo](https://github.com/microsoft/SkillOpt), MIT): treat a short instruction text as the trainable state of a frozen model. Run scored tasks, read the failures, propose ONE bounded edit (add / replace / delete one rule), and keep it only if a held-out task set improves. The paper reports +9 to +25 % average gains, Qwen 3.5-4B among the targets. **Use the principle, not their code:** their harnesses are plain chat, Codex CLI and Claude Code, not Odysseus's agent loop, and the reflecting step needs no tooling — a session reads the failures and proposes the edit.

**Plan, in order:**

1. **Item 20 first.** `_AGENT_RULES` and `_API_AGENT_RULES` are each assigned twice; decide which text is live, so there is a known baseline.
2. **One fork-owned rules file** — `config/agent_rules_fork.md`, appended by a single call in `_assemble_prompt` (CLAUDE.md §0). Upstream text stays untouched; this file is what gets tuned. It must be identical across turns for a given model, or it breaks prompt caching (items 57, 58).
3. **A setting `agent_rules_file`** naming a candidate file, so the benchmark can swap rules without a code change. `bench_agent.py` sets it before a run, restores it after, and records the file's sha256 in `meta.json`. Log the assembled prompt's length so a rule that bloats the prompt shows as cost.
4. **Benchmark changes** (`scripts/bench_agent.py`, `bench_agent_tasks.py`):
   - a `split` field per task, `train` or `holdout`;
   - `--rules FILE`;
   - `compare BASE_DIR CANDIDATE_DIR`: holdout pass rate per task for both, and an accept / reject verdict by the rule in step 6.
5. **Grow the task set to ~40**, taking new tasks from failures already recorded (gather-then-stop, LAN prompt dropping document tools, tool call written instead of made, wrong numbers in documents). 18 tasks split train/holdout leaves ~6 to gate on, which measures luck. Keep the Odysseus wiring checks (items 21, 2a) in their own category, out of this score.
6. **The gate, as a CLAUDE.md rule** (proposed §8, add when step 4 exists):
   > Model-facing text is changed like code with a test. One bounded edit per change, motivated by at least two failing runs that show the same pattern. Run the `holdout` tasks with `--runs 2` or more before and after; keep the edit only if the holdout pass rate goes up and no holdout task that passed every run now fails. Otherwise revert it. Record it either way in `notes/prompt-log.md` — diff, motivating runs, both scores, model, date. A rejected edit is a retraction. A gate result holds only for the model it was measured on.
7. **Baseline on Qwen, then one-edit iterations.**

**Cost.** Qwen: a ~15-task holdout at `--runs 2` ≈ 30 min. Bonsai 2: overnight (`caffeinate`). Steps 1–4 ≈ a day of code; step 5 is mostly the maintainer's call on which tasks matter.

**Not in scope:** running SkillOpt's own optimizer. Revisit only if the task set reaches 50+ and the rule-adherence measurement (item 20, *Next* in todo.md) shows the rules are what limits the model.

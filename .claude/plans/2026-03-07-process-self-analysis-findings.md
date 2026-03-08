# Process Self-Analysis: What the Pipeline Data Reveals

**Date**: 2026-03-07
**Data window**: 2025-11 to 2026-03-07 (peak: Feb 2026)
**Source**: `organvm atoms pipeline` output — 4,039 prompts, 3,257 tasks, 1,601 links, 1,434 sessions

---

## Key Findings

1. **8% completion rate across 3,257 planned tasks.** 261 tasks confirmed done via git reconciliation. 74% of plans (182/245) have zero completions. The system plans at 12x the rate it executes.

2. **Infrastructure consumes 72% of planning energy.** META (32%) + LIMINAL (21%) + IV (19%) = 72% of all tasks. Creative organs I+II get 4% combined. The system builds tools for building tools.

3. **Exploration is nearly absent.** Only 3% of prompts are exploratory. 9/108 narrative threads start with exploration. 70/108 are "steady-build" — jumping straight to implementation.

4. **Plans are enormous and aspirational.** The top 20 plans average 50 tasks each. All 20 have 0% completion. These are research documents or wish lists being atomized as if they were sprint backlogs.

5. **Prompts are effective when specific.** Long prompts (31% of total) drive 52% of completions. High-specificity prompts complete at 27% (77/281) vs low-specificity at 10% (127/1,320). Plan invocations are the single most productive prompt type: 105 completions from 717 prompts.

6. **Context-switching is extreme.** 3.9 projects/day average, peaking at 14 in one day. 17.4% of sessions are single-prompt (fire-and-forget). Activity spans nearly 24 hours with only a 4-8am valley.

7. **The linking pipeline has a fingerprint gap.** 66% of prompts (2,686/4,039) have empty domain fingerprints, making content-based matching impossible. Only 9.3% of tasks achieve quality links (Jaccard >= 0.30).

---

## What's Working Well

### Plan invocations as execution accelerators
When you paste a plan and say "implement this," the completion rate is 2x higher than ad-hoc commands. The plan-invocation pathway (17% of prompts, 40% of completions) is your highest-leverage prompt pattern.

### Focused sprints produce results
The plans with >80% completion are tight, specific, and time-bounded:
- "SOP v2.0 — Document Audit" (15/15, 100%)
- "Fix Ask Feature for External Collaborators" (6/6, 100%)
- "Sprint Gap Audit + Hardening v2" (6/6, 100%)
- "Full Sweep: Test Hardening + E2E + CI/CD" (29/35, 83%)

These share traits: <20 tasks, single-project focus, concrete deliverables (not research).

### Multi-agent breadth
Using Claude (81%), Codex (9%), and Gemini (8%) across 30+ technologies (Python, TypeScript, Go, React, Docker, p5.js, SuperCollider, Terraform) demonstrates genuine creative-engineering range. The agent mix matches task types — Codex for boilerplate, Gemini for exploration, Claude for complex implementation.

### Git-backed accountability
16.9% of sessions end with git operations (commits/pushes), providing a real audit trail. The reconciler correctly identifies 210 completed + 20 partial tasks from commit history.

---

## Process Anti-Patterns Detected

### 1. Plan Sprawl (evidence: 182 ghost plans, 2,490 orphan tasks)

**What**: 74% of plans have zero completions. The 10 largest ghost plans contain 537 tasks that were never started. Plans like "Research Ingestion SOP Discovery" (64 tasks) and "Evaluation-to-Growth: Codebase Study v2" (56 tasks) are exploratory analyses masquerading as implementation plans.

**Impact**: Atomizing these inflates the task backlog by 76%, making the real completion rate invisible. The true denominator should be ~767 actionable tasks (from the 63 plans with any completion), giving a real completion rate of ~34%.

**Fix**: Classify plans as `blueprint` (actionable, <25 tasks) vs `research` (analysis, exploration, wish-list). Only atomize blueprints. Archive research plans separately.

### 2. Infrastructure Gravity Well (evidence: META 3.7%, IV 3.7% completion vs III 16.1%)

**What**: The two organs receiving the most planning energy (META: 1,062 tasks, IV: 644 tasks) have the lowest completion rates. Meanwhile ORGAN-III (commercial products) completes at 16.1% — the highest of any organ with significant volume.

**Impact**: Infrastructure work generates more infrastructure work. Each new pipeline, dashboard, or analysis tool spawns maintenance tasks and further tooling plans. The creative organs (I, II) that should drive the system's artistic mission get 4% of planning attention.

**Fix**: Apply a 60/30/10 rule: 60% of new plans target organs I-III (creative + commercial), 30% for IV/META (infrastructure), 10% for V-VII (distribution). Track this ratio monthly.

### 3. Explore-Before-Build Deficit (evidence: 3% exploration, 0% correction)

**What**: Only 140/4,039 prompts are exploratory. Only 9/108 threads start with exploration. The dominant pattern is "steady-build" (65%) — jumping directly to implementation without discovery phases. The 0% correction rate suggests either extraordinary prompt precision or (more likely) that corrections happen through new sessions rather than in-thread course corrections.

**Impact**: Without exploration phases, implementations may solve the wrong problem or miss existing solutions. The single-prompt session rate (17.4%) reinforces this: many interactions are quick commands without context-building.

**Fix**: Adopt a "3-question start" protocol: before any implementation session, spend 3 prompts on exploration (what exists? what's similar? what could go wrong?). This alone would shift the exploration rate from 3% to ~15%.

### 4. Session Fragmentation (evidence: 17.4% single-prompt, bimodal duration)

**What**: 160 sessions are single-prompt. The duration distribution is bimodal: many under 15 minutes (216 sessions), plus a long tail over 2 hours (115 sessions). The 2h+ sessions likely represent deep work, while the short sessions are quick checks or context-switching artifacts.

**Impact**: Short sessions have low completion rates because there isn't enough context established. The 3.9 projects/day average with a max of 14 suggests attention is fragmented across too many fronts.

**Fix**: Batch short tasks. Instead of 5 separate single-prompt sessions across 5 projects, open one session and handle all 5 quick items sequentially. This preserves cognitive context and reduces session churn.

### 5. Temporal Over-Extension (evidence: near-24h activity, only 4-8am gap)

**What**: Prompts arrive at every hour of the day. Peak hours: midnight (262), 4pm (269), 8pm (296). The only quiet window is 4-8am (25-35 prompts/hour).

**Impact**: Sustained work across 20 hours indicates either extreme schedule flexibility or boundary erosion. Combined with high context-switching, this pattern risks burnout and quality degradation in late-night sessions.

**Fix**: Define two "deep work" blocks (e.g., 10am-1pm, 8-11pm based on existing peaks) and batch exploratory/short tasks outside those blocks. Protect the 2-8am window as genuine rest.

---

## Recommended Changes

### Immediate (this week)

1. **Archive ghost plans.** Move the 182 zero-completion plans to `plans/archive/`. This immediately clarifies the real backlog from ~3,257 to ~767 tasks.

2. **Tag 3 plans as "active sprint."** Pick the 3 most important incomplete plans (<20 tasks each) and commit to completing them before creating new plans.

3. **Run `organvm plans tidy --write`** to move stale plans and surface the real active set.

### Near-term (this month)

4. **Implement plan classification.** Add a `plan_class` field to the atomizer: `blueprint` (actionable), `research` (exploratory), `retrospective` (post-hoc). Only track completion rates for blueprints.

5. **Add exploration prompts to your workflow.** Before starting any implementation, spend 3 prompts reading code, asking questions, and checking for prior art. Target: 15% exploration rate by next audit.

6. **Set an organ allocation target.** Track weekly plan creation by organ. Target: >=1 plan/week for organs I or II.

### Strategic (this quarter)

7. **Reduce plan size.** Cap new plans at 15 tasks. Break larger efforts into sequential sprints. The data shows 100% completion only happens at <=15 tasks.

8. **Build a "plan ROI" metric.** `completed_tasks / total_tasks * link_quality_score`. Surface this in the dashboard to identify which planning patterns produce results.

9. **Create a weekly process digest.** Auto-generate from pipeline data: tasks completed, plans created vs archived, organ distribution, exploration rate. Makes the anti-patterns visible in real time.

---

## Metrics to Track (for next audit comparison)

| Metric | Current | Target | How to measure |
|--------|---------|--------|----------------|
| Task completion rate (all) | 8.0% | 15% | `organvm prompts audit` |
| Task completion rate (blueprints only) | ~34% | 50% | After plan classification |
| Ghost plan ratio | 74% | <40% | Plans with 0 completions / total |
| Exploration prompt rate | 3.5% | 15% | Narrative summary |
| Avg projects/day | 3.9 | <=3 | Session patterns |
| Single-prompt session rate | 17.4% | <10% | Session patterns |
| Creative organ task share (I+II) | 4% | 15% | Atomized summary by organ |
| Empty fingerprint rate | 66% | <40% | Pipeline manifest quality |
| Active plans (non-ghost) | 63 | 20-30 | Plan index |

---

## The Core Insight

The data reveals a system optimized for **planning breadth** rather than **execution depth**. The 12:1 plan-to-completion ratio isn't a failure of execution — it's a mismatch between how plans are used (as thinking tools, research artifacts, wish lists) and how they're measured (as sprint backlogs).

The fix isn't "execute more" — it's "plan differently." Separate thinking-plans from doing-plans. Measure only the doing-plans. And redirect 2/3 of planning energy away from infrastructure toward the creative and commercial organs that justify the infrastructure's existence.

The system builds the engine brilliantly. Now it needs to drive somewhere.

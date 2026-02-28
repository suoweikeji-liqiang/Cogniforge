# Feature Research

**Domain:** Socratic AI Tutoring / Cognitive Adversarial Testing
**Researched:** 2026-02-28
**Confidence:** MEDIUM (academic research HIGH, product feature specifics MEDIUM, dual-agent tutoring LOW — limited real-world deployments)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any Socratic AI tutoring system. Missing these = product feels broken or pointless.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Guided questioning (no direct answers) | Core Socratic contract — if the AI just answers, it's not tutoring | MEDIUM | Khanmigo's defining mechanic; must resist giving answers even when learner pushes |
| Session anchored to a specific concept | Tutoring without a topic anchor is unfocused; learner needs to know what's being tested | LOW | In this project: triggered from a model card, concept is pre-loaded |
| Multi-turn dialogue with memory | Each question must build on prior answers; stateless Q&A is not tutoring | MEDIUM | Requires conversation history passed to LLM each turn |
| Learner can stop at any time | Learner controls the session; forced completion creates anxiety | LOW | "Stop and get current diagnosis" is the exit contract |
| Feedback that explains why an answer is incomplete | Learner needs to know what gap was exposed, not just "wrong" | MEDIUM | Socratic systems distinguish between "wrong" and "incomplete reasoning" |
| Streaming / real-time response output | Waiting for full AI response breaks conversational flow | MEDIUM | SSE or WebSocket; Khanmigo and all modern tutors stream |
| Session history / transcript | Learner needs to review what was discussed | LOW | Persist conversation turns to DB |
| Safe, non-threatening tone | Adversarial framing causes learner anxiety and disengagement | LOW | Tone is a prompt engineering concern, but must be enforced consistently |

### Differentiators (Competitive Advantage)

Features that set this system apart from standard Q&A chatbots or single-agent tutors.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dual-agent role split (Guide + Challenger) | Creates productive cognitive tension without a single agent being both supportive and adversarial — role clarity improves dialogue quality | HIGH | Core innovation of this project; Guide builds understanding, Challenger surfaces contradictions. Academic research (SocratiQ) confirms dual-agent protocols improve critical thinking outcomes |
| Turn scheduler (decides which agent speaks) | Prevents both agents from piling on; controls pacing and adversarial intensity | MEDIUM | Adapted from ProdMind debate engine; scheduler decides Guide vs Challenger based on conversation state |
| Understanding score (per-session, per-turn) | Quantifies comprehension progress; gives learner a concrete signal of where they stand | HIGH | Similar to ProdMind confidence index; must be derived from dialogue analysis, not self-report |
| Blind spot library (extracted from dialogue) | Surfaces specific gaps the learner didn't know they had — the core value proposition | HIGH | Requires LLM to classify learner responses as "gap exposed" vs "understood"; persisted per concept |
| Cognitive evolution snapshot (state tree per turn) | Lets learner see how their understanding changed across the session | HIGH | Adapted from ProdMind state snapshots; each turn saves understanding state |
| Cognitive diagnostic report (Markdown export) | Tangible artifact learner keeps; makes invisible learning visible | MEDIUM | Summarizes: concept tested, gaps found, understanding score trajectory, recommended follow-up |
| Integration with existing model cards | Tutoring is anchored to a specific concept the learner is already studying — not generic | LOW | Trigger from model card is the integration point; concept metadata pre-loads session context |
| Contradiction detection across turns | Catches when learner contradicts themselves across turns — a strong signal of shallow understanding | HIGH | Requires cross-turn analysis; Challenger agent's primary job |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Direct answer mode ("just tell me") | Learners get frustrated and want the answer | Defeats the entire purpose; once you give answers, learners will always ask for them | Offer a "hint" that narrows the question without answering it |
| 6-agent full adversarial debate | More agents = more thorough testing | Overwhelming for a single learner; creates anxiety not insight; research shows sycophancy and conformity failures in large MAD systems | 2-agent Guide + Challenger is the right intensity for learning |
| Gamification (points, badges, leaderboards) | Engagement boost | Shifts motivation from understanding to score-chasing; learners optimize for points not comprehension | Use understanding score as internal signal, not public competition metric |
| Forced session length / minimum turns | Ensures "thorough" testing | Learner loses agency; anxiety increases; SocraticAI research shows daily limits work better than forced minimums | Let learner stop anytime; show current diagnosis on exit |
| Real-time understanding score visible during session | Transparency feels good | Learners optimize for the score rather than genuine reasoning; they learn to game the metric | Show score only in the post-session diagnostic report |
| Automatic concept remediation (pivot to teaching) | Seems helpful when gaps are found | Breaks the Socratic contract; tutoring becomes lecturing; learner stops engaging with questions | Flag gaps in the diagnostic report; let the learner's existing spaced repetition system handle remediation |
| Voice input/output | Accessibility and naturalness | High complexity, low priority for v1; voice adds latency and error surface | Text-first; voice is a v2+ consideration |
| Peer comparison / social features | Motivation through social proof | Privacy concerns; learners feel judged; not relevant to individual cognitive gap detection | Keep sessions private; diagnostic report is personal |

---

## Feature Dependencies

```
[Model Card] (existing)
    └──triggers──> [Session Initialization]
                       └──requires──> [Concept Context Loader]
                                          └──feeds──> [Turn Scheduler]
                                                          ├──dispatches──> [Guide Agent]
                                                          └──dispatches──> [Challenger Agent]
                                                                               └──both feed──> [Understanding Scorer]
                                                                                                   └──writes──> [Blind Spot Library]
                                                                                                                    └──generates──> [Cognitive Diagnostic Report]

[Session History] ──required by──> [Cognitive Evolution Snapshot]
[Cognitive Evolution Snapshot] ──required by──> [Diagnostic Report]
[Blind Spot Library] ──enhances──> [Spaced Repetition] (existing feature)
```

### Dependency Notes

- **Session Initialization requires Concept Context Loader:** The agents need the concept definition, existing notes, and any prior blind spots from the model card before the first turn. Without this, the session is generic.
- **Turn Scheduler requires both agents to be defined:** Scheduler logic is meaningless without two distinct agent roles to dispatch to.
- **Understanding Scorer requires multi-turn history:** A single-turn score is noise; the score only becomes meaningful after 3+ turns of dialogue.
- **Blind Spot Library requires Understanding Scorer:** Gaps are extracted when the scorer detects a drop or plateau in understanding; the scorer is the trigger.
- **Diagnostic Report requires Blind Spot Library + Cognitive Evolution Snapshot:** The report is a synthesis of both; neither alone is sufficient.
- **Blind Spot Library enhances Spaced Repetition (existing):** Gaps found in cognitive testing should surface as higher-priority review items in the existing spaced repetition system. This is an enhancement, not a hard dependency.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate that dual-agent Socratic testing actually surfaces blind spots.

- [ ] Session initialization from model card (concept pre-loaded)
- [ ] Guide Agent + Challenger Agent with distinct system prompts
- [ ] Turn scheduler (simple rule-based: alternate with Guide-first, Challenger when contradiction detected)
- [ ] SSE streaming for both agents
- [ ] Multi-turn conversation history (persisted to DB)
- [ ] Understanding score (per-turn, derived from LLM analysis of learner response)
- [ ] Blind spot extraction (LLM classifies each learner response as gap/understood/unclear)
- [ ] Stop-anytime with immediate diagnostic summary
- [ ] Cognitive diagnostic report export (Markdown)
- [ ] Navigation entry point in learning assistant sidebar

### Add After Validation (v1.x)

Features to add once the core loop is validated and learners are actually using it.

- [ ] Cognitive evolution snapshot (state tree per turn) — add when learners ask "how did my understanding change?"
- [ ] Blind spot library persistence across sessions (not just within one session) — add when learners return for second sessions
- [ ] Integration with spaced repetition (surface gaps as review items) — add when blind spot data is reliable enough to trust
- [ ] Contradiction detection across turns (cross-turn analysis) — add when single-turn gap detection is working well

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Android mobile adaptation — not in scope for v1 per PROJECT.md
- [ ] Voice input/output — high complexity, low validated demand
- [ ] Peer/cohort blind spot aggregation (anonymized) — privacy implications need careful design
- [ ] Teacher/instructor dashboard — different user persona, different product surface

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Guide + Challenger dual agents | HIGH | HIGH | P1 |
| Turn scheduler | HIGH | MEDIUM | P1 |
| SSE streaming | HIGH | MEDIUM | P1 |
| Session from model card | HIGH | LOW | P1 |
| Understanding score | HIGH | HIGH | P1 |
| Blind spot extraction | HIGH | HIGH | P1 |
| Stop-anytime + diagnosis | HIGH | LOW | P1 |
| Diagnostic report export | MEDIUM | MEDIUM | P1 |
| Cognitive evolution snapshot | MEDIUM | HIGH | P2 |
| Cross-session blind spot persistence | MEDIUM | MEDIUM | P2 |
| Spaced repetition integration | MEDIUM | LOW | P2 |
| Contradiction detection (cross-turn) | HIGH | HIGH | P2 |
| Voice I/O | LOW | HIGH | P3 |
| Mobile adaptation | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Khanmigo | Socratic by Google | SPL / SocraticAI (academic) | Our Approach |
|---------|----------|-------------------|------------------------------|--------------|
| Socratic questioning | Yes — refuses direct answers, asks follow-up questions | No — surfaces resources and explanations, not dialogue | Yes — multi-turn guided dialogue with EMT principles | Yes — Guide agent leads with questions |
| Understanding assessment | Implicit (no explicit score shown) | None | Implicit (adapts based on response quality) | Explicit per-turn score, shown in report |
| Blind spot detection | Implicit (guides toward gaps) | None | Partial (misconception-tailored feedback) | Explicit gap extraction and library |
| Multi-agent architecture | Single agent | Single agent | Single agent (SPL); dual-agent (SocratiQ) | Dual agent: Guide + Challenger |
| Session export / report | No | No | No (research prototype) | Yes — Markdown diagnostic report |
| Concept-anchored sessions | Yes (tied to Khan Academy content) | Yes (tied to homework question) | Partial (scenario construction) | Yes — triggered from model card |
| Learner controls session end | Partial | Yes (just close app) | No (fixed session structure) | Yes — stop anytime, get diagnosis |
| Streaming output | Yes | Yes | N/A (research prototype) | Yes — SSE |
| Integration with spaced repetition | No | No | No | Planned (v1.x) |

---

## Sources

- Khanmigo features and Socratic method: [Khanmigo AI Review 2025](https://aiflowreview.com/khanmigo-ai-review-2025/) — MEDIUM confidence
- Khanmigo official features: [Khanmigo Features for Teachers](https://blog.khanacademy.org/khanmigo-features/) — MEDIUM confidence
- Socratic by Google: [Google's AI Study Companion](https://aipure.ai/articles/socratic-review-googles-ai-study-companion-explored) — MEDIUM confidence
- SPL academic system: [A Socratic Playground for Learning (arxiv)](https://arxiv.org/html/2406.13919v1) — HIGH confidence (peer-reviewed)
- SocraticAI scaffolded tutoring: [Transforming LLMs into Guided CS Tutors (arxiv)](https://arxiv.org/html/2512.03501v1) — HIGH confidence (peer-reviewed)
- SocratiQ dual-agent system: [AI-Driven Socratic Dialogue Systems](https://www.emergentmind.com/topics/socratiq) — MEDIUM confidence
- Multi-agent debate failure modes: [Understanding Failure Modes in Multi-Agent Debate (arxiv)](https://arxiv.org/html/2509.05396v2) — HIGH confidence (informs anti-features)
- Cognitive diagnostic systems: [Cognitive Diagnostic Module](https://www.emergentmind.com/topics/cognitive-diagnostic-module) — MEDIUM confidence
- Socratic wisdom comparative study: [Frontiers in Education 2025](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1528603/full) — HIGH confidence (peer-reviewed)

---
*Feature research for: Cognitive Adversarial Testing — Socratic AI Tutoring*
*Researched: 2026-02-28*

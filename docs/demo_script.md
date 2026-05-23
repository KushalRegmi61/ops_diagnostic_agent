# Five-Minute Demo Script

## 0:00 — Context

"I built this because Agent Integrator isn't selling AI demos — you're helping real businesses become AI-native. So instead of a chatbot or a pasted-text intake, I wanted the agent to do what an actual ops consultant does: read the company's real files, reason across them, and propose the first automation with evidence behind every claim."

## 0:45 — Upload the Files

Open the **Upload** view. Drag in the sample bundle: a PDF SOP, a VTT discovery-call transcript, a CSV lead list, an MBOX inbox export, a JSON CRM dump.

"These are the kinds of files this insurance agency already has. No paste box, no pretending. Each file is parsed with locator anchors — page and span for the PDF, line and timestamp for the transcript, row index for the CSV, message-id for the MBOX."

## 1:30 — Parallel Per-File Agents

Click **Run**. Watch the per-file-agent panel.

"Every file gets its own LLM agent running in parallel. Each agent summarizes what its file says about workflows, pain signals, and lead data — and every record it emits cites the exact locator it came from. They're summarizers, not deciders."

## 2:15 — Lead Agent: Review and Synthesize

Point to the **Run Progress** panel as the lead agent kicks in.

"Then a single lead agent takes over. First it reviews every per-file summary — flags missing info, contradictions, weak citations. If a per-file agent missed something, it gets one targeted redo. Then it synthesizes across files into one bundle, keeping contradictions visible instead of silently merging them."

## 3:00 — Diagnostic Chain

"From the bundle, it runs the diagnostic: workflow map, bottleneck detection, ROI scoring, fastest-win selection, solution blueprint. Five nodes, each adds to the state, each cites file evidence."

## 3:45 — Blueprint with Citations

Open the **Blueprint** view. Click a blueprint claim to open the citation side panel.

"This is the proof the system actually read the files. Every claim has a clickable citation. This one points to page 4 of the SOP. This one points to line 142 of the transcript at 11:04. This ROI score cites three lead-CSV rows showing the same delay pattern."

## 4:15 — Self-Review and Observability

"Before emitting, the lead agent self-reviews its blueprint — every citation must resolve to a real locator, no open questions silently dropped, internal consistency between the selected opportunity and the blueprint. One revision pass if it fails."

Open the Langfuse trace.

"One nested trace per run. You see the parent graph, fan-out to per-file agents, every LLM call with prompt, model, tokens, latency, the redo cycle, the self-review revision if it fired. This is what makes the system debuggable in production."

## 4:45 — Close

"What I bring to Agent Integrator is the full-stack builder loop: real file ingestion, parallel agents with citations, a lead agent that reviews its own work, FastAPI plus LangGraph plus Langfuse, and no mock layers anywhere. The pipeline that produced this demo is the same pipeline a real client would get."

## Notes for the Demo Operator

- Run mode: hosted model (OpenAI or Groq) for quality.
- CI / dev runs against local Ollama with `temperature=0`.
- v2 deferred items (knowledge source, multimodal, approval-gated actions) live in the spec §16 if anyone asks "what's next."

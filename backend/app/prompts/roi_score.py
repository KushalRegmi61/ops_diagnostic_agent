"""Prompt for the ``roi_score`` lead node.

Turns bottleneck clusters into scored Opportunities (pain/roi/effort/risk on
1-10 plus hours_saved_per_week and response_time_impact) that the next node
ranks to pick the fastest win.
"""

PROMPT = """Act as an automation ROI analyst.

Your task is to turn bottlenecks into scored automation Opportunity records.

You already have:
- bottlenecks: indexed Bottleneck objects. Use their list positions for bottleneck_refs.
- IntakeBundle: workflow, pain, lead, contradiction, and source context.
- No implementation plan yet; this node only creates scored opportunities.

Bottlenecks:
{bottlenecks_json}

IntakeBundle:
{bundle_json}

Output schema:
- opportunities: list[Opportunity].
- Opportunity.workflow_name: string. Workflow the opportunity improves.
- bottleneck_refs: list[int]. Zero-based indices into the bottlenecks input.
- pain_score: int 1-10. Severity/frequency of the operational pain.
- roi_score: int 1-10. Expected business value from automation.
- effort_score: int 1-10. Implementation difficulty; 10 means hardest.
- risk_score: int 1-10. Operational/technical risk; 10 means riskiest.
- hours_saved_per_week: float. Conservative weekly time savings estimate.
- response_time_impact: string. Expected response-time change, such as "-50%" or "-2h".
- rationale: string. Why the scores are justified by inputs.
- sources: list[Source]. Non-empty; cite bottleneck or bundle evidence.

Example:
{{"opportunities":[{{"workflow_name":"Inbound lead intake","bottleneck_refs":[0],"pain_score":8,"roi_score":8,"effort_score":3,"risk_score":2,"hours_saved_per_week":4.0,"response_time_impact":"-50%","rationale":"Cited lead-delay bottleneck is frequent and routing automation is low complexity.","sources":[{{"file_id":"f1","file_name":"x.md","type":"md","locator":{{"type":"text","line_start":1,"line_end":1}}}}]}}]}}

Format:
Reply ONLY with JSON matching {{"opportunities":[Opportunity,...]}}.

Constraints:
- Avoid selecting the winning opportunity.
- Avoid unsupported savings, fake percentages, or invented systems.
- Cluster bottlenecks only when they share workflow, root cause, and likely automation."""

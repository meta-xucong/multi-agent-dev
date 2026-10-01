# Model and effort routing

The requested route is data in the TaskSpec. It is not proof of runtime use. A live runtime result must separately provide observed model and effort; otherwise the route status is ROUTE_UNVERIFIED.

| Responsibility | Default route |
| --- | --- |
| Main session / integration | gpt-6-luna / high |
| Controller state machine | no LLM |
| Controller plan suggestion | gpt-6-luna / high |
| Think | gpt-6-sol / xhigh |
| Execute I0 | gpt-6-luna / low |
| Execute I1 | gpt-6-luna / high |
| Execute I2 | gpt-6-luna / xhigh |
| Execute I3 | gpt-6-luna / max |
| Test | gpt-6-luna / high |
| Semantic Guard A0/A1/A2 | gpt-6-luna / high, xhigh, max |
| Independent Audit A0/A1/A2 | gpt-6-luna / high, xhigh, max |
| Source Fidelity A1/A2 | gpt-6-luna / xhigh, max |

A requested model or effort may be changed only by a new manifest revision. Observed mismatch is ROUTE_MISMATCH and requires a gate hold.

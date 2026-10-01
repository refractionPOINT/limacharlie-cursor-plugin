---
name: limacharlie-detection-engineering
description: Write, test and deploy LimaCharlie D&R (Detection & Response) rules and false-positive rules. Draft the rule, validate it, unit-test it against matching and non-matching events, replay it against history, and deploy it disabled or enabled only after approval, then read it back. Use for new detections, tuning, turning threat reports into detections, and false-positive suppression.
---

# Detection engineering

Read the `limacharlie` skill first for the connections, org selection and the approval rule.

- **Read-only** (`limacharlie` connection): drafting, validating and unit-testing.
- **Changes** (approve first, then use `limacharlie-actions`): replaying (billed), deploying, enabling, disabling and deleting rules.

## Rule anatomy

A D&R rule has a `detect` block (what to match) and a `respond` list (what to do). By default a rule sees endpoint (`edr`) events. `target:` switches it to `detection`, `deployment`, `artifact`, `artifact_event`, `schedule`, `audit` or `billing` events.

```yaml
detect:
  event: NEW_PROCESS
  op: and
  rules:
    - op: ends with
      path: event/FILE_PATH
      value: certutil.exe
      case sensitive: false
    - op: contains
      path: event/COMMAND_LINE
      value: urlcache
      case sensitive: false
respond:
  - action: report
    name: certutil-download
    metadata:
      mitre: T1105
```

- **Operators**: `is`, `contains`, `starts with`, `ends with`, `matches` (regex), `exists`, `is greater than`, `is lower than`, `string distance`. Combine them with `op: and` / `op: or` and a `rules:` list. Add `not: true` to invert one.
- **Stateful matching**: `with child:`, `with descendant:`, `with events:`, plus `count:` and `within:` (seconds).
- **Responses**: `report`, `add tag` (with optional `ttl`), `task`, `isolate network`, `output`. Any action can take a `suppression:` block to limit how often it fires.
- **Reference**: https://docs.limacharlie.io/3-detection-response/

**Response actions have side effects.** Every response action other than `report` (for example `task`, `isolate network`, `rejoin network`, `seal`, `add tag`, `add var`, `output`, `extension request` or `start ai agent`) acts automatically on every match, with nobody asking first. Default to `report` only. Propose automated containment as a separate change, name the hosts it could affect, and deploy it only when the user asks for it by name and approves.

## Workflow

Keep the rule in a file (for example `/workspace/limacharlie/<org>/rules/<name>.yaml`), so that every step works on exactly the same content.

1. **Check the fields.** Confirm the event type and paths with `get_event_schema`, plus one real sample event. If it helps, draft a starting point with `generate_dr_rule_detection` and `generate_dr_rule_respond`, and review the result. Generated rules still go through every step below.
2. **Validate** with `validate_dr_rule_components` (`detect`, `respond`). Fix and re-validate after every edit.
3. **Unit-test both directions** with `test_dr_rule_events` (`detect`, `respond`, `events`, `trace: true`). Events use the LimaCharlie shape `{"event": {...}, "routing": {"event_type": "...", ...}}`.
   - Matching events: realistic events that must fire the rule.
   - Non-matching events: the closest benign look-alikes, which must not fire it.

   Both results must be what you expect. A rule that compiles is not proven to work.

   **Match the advertised tool schema.** D&R YAML always stores `respond` as a list. Inspect the validation, test and replay tools before passing it: when their `respond` schema accepts arrays, pass the complete list unchanged. Older servers advertise only an object; for a rule with exactly one response, pass that single action object (the server wraps it back into a list). If the rule has multiple responses and the schema accepts only an object, stop and explain that the MCP server needs its response-array schema update. Never omit responses, test them separately as a substitute for the full rule, or deploy an untested multi-response rule.
4. **Replay against history** to measure noise before the rule goes live. Replay is billed over the window and needs approval:
   - Approve the estimate: run `replay_dr_rule` with `detect`, `respond`, `start_time`, `end_time`, an optional `sid` or `selector`, and `dry_run: true`.
   - Show the estimate, and approve the real run with the same arguments and no `dry_run`.

   The rule does not need to be deployed for replay. Report how many hits there were, with representative ones. Past volume only roughly predicts future volume.
5. **Deploy, after approval.** The approval prompt names the org, the rule name, whether it will be enabled, and any response action other than `report`. Put the final YAML and the replay result in the help text. Then:
   - **New rule**: `set_dr_general_rule` with `rule_name`, `rule_content` (the `detect` and `respond` blocks) and `enabled: false`. Enabling is a second step with its own approval (`enable_dr_rule`), unless the user approved "deploy enabled" explicitly.
   - **Existing rule**: read it first with `get_dr_general_rule`, and show a before/after diff in the approval. `set_dr_general_rule` keeps its enabled state, tags and comment unless you pass them. If the rule changed since you read it, re-read it and re-approve instead of overwriting.
6. **Verify.** Read the rule back with `get_dr_general_rule`, and check that its content and enabled state are what was approved. "Deployed and enabled" does not mean "has fired", so say whether live firing has been observed.

Only change `general` rules. `managed` and `service` rules belong to LimaCharlie or an extension, and are read-only here unless the user explicitly asks otherwise.

## False-positive rules

FP rules suppress specific detections after they are generated. They run against the detection record: match `cat` (the rule name) and paths under `detect/...` or `routing/...`.

```yaml
op: and
rules:
  - op: is
    path: cat
    value: certutil-download
  - op: is
    path: routing/hostname
    value: build-server-01
    case sensitive: false
  - op: ends with
    path: detect/event/FILE_PATH
    value: \approved\tool\certutil.exe
    case sensitive: false
```

Keep FP rules narrow: one rule name plus the specific benign attributes, never a whole rule or a whole host. Show the user which recent detections the rule would suppress, and a closely related malicious variant that would still fire. Deploy with `set_fp_rule` after approval: `rule_name`, plus `rule_content` with the rule under a `detect` key (`{"detect": {"op": "and", "rules": [...]}}`). Then read it back with `get_fp_rule`.

## Disabling and deleting

Disabling (`disable_dr_rule`) can be undone. Deleting (`delete_dr_general_rule`) cannot. Prefer disabling. Before a delete, save the current rule to a file, and name it in the approval prompt as a permanent deletion.

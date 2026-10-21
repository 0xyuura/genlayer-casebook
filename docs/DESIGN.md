# Casebook: design

## The defect it removes

An AI court that judges every case from scratch has no memory between
rulings. Each ruling can be honest consensus and still disagree with the
last one, because nothing ties them together. Two customers with identical
complaints, worded differently, can be refunded differently. Two members who
insulted someone in the same way can get different marks. Each ruling passes
review in isolation, but taken together the court is arbitrary.

Courts solved this long ago with two habits: they separate **fact** from
**law**, and once a point of law is decided they **follow it** (stare
decisis). Casebook encodes both as contract structure, so consistency is a
property of the code rather than of the model's mood.

## Fact and law, split on purpose

| Step | Sees | Never sees | Validators compare |
| --- | --- | --- | --- |
| `rule_case` (fact) | the fact questions, the narrative | the rule, the outcomes | `{"facts": {fact: value or UNCLEAR}}` |
| `settle_cell` (law) | the rule, one cell, the outcomes | any narrative | `{"outcome": label}` |

The fact finder cannot reason backwards from a desired outcome, because it is
not told the rule or the outcomes. The law step cannot be argued with by a
story, because no story reaches it. A prompt injection in a narrative can at
most move a fact to another closed value, and it has to convince validators
who re-run the same extraction independently.

## The table

Every combination of fact values is a cell. A docket has at most 5 facts of
2 to 4 values and at most 64 cells, so the full table is enumerated
(`all_cells`) and published (`table`). Nothing about the law is sampled:

- `settle_cell` accepts exactly the cells of the table and nothing else
  (`NO_SUCH_CELL`), and `UNCLEAR` is not a value of any cell.
- A settled cell is permanent (`CELL_SETTLED`).
- A case's outcome is computed, not stored: `outcome(case) = law[docket|cell]`.

So for any two cases `x`, `y` on the same docket:
`cell(x) == cell(y)  =>  outcome(x) == outcome(y)`. This is not a statistical
property of the model. It holds because there is only one place the outcome
can come from. `test_consistency_holds_for_any_history` checks it over 150
cases filed in random order against a model that answers the law step at
random.

Cells are settled lazily, when a case needs one, or up front by anyone who
wants the whole law published before the first filing. A registrar who wants
a docket fully specified settles all of its cells first.

## Exactness

Both model steps return one value from a closed set per slot, parsed by
module-level functions (`vector_from_reply`, `outcome_from_reply`) that
reject extra keys, missing keys and unknown values. The leader returns the
canonical JSON, and each validator re-runs the same step and compares the
canonical JSON with `==`. There is no tolerance band and no similarity
threshold. A model that strays outside the set is an `[LLM_ERROR]`, which
stores nothing and lets the leader rotate.

`UNCLEAR` is the honest answer when a narrative does not settle a fact. A
case with any `UNCLEAR` fact is `UNDETERMINED`: it has no cell, no outcome,
and no consumer acts on it. The clerk files a clearer narrative as a new case.

## Who may write

| Write | Who | Policy |
| --- | --- | --- |
| `open_docket` | anyone | the sender is the registrar; rule, facts, outcomes and clerks are fixed forever |
| `file_case` | a clerk named by that docket | not about a clerk (`SUBJECT_IS_CLERK`); 200 cases per docket |
| `rule_case` | anyone | case id only; once per case |
| `settle_cell` | anyone | docket id and a cell only; once per cell |

The only free text that reaches a model is the registrar's rule and the
clerks' narratives, and both come from parties the docket names at opening.
The two model writes take identifiers only, so whoever pays for a ruling
cannot steer it. Nothing in a docket can be edited after opening, which is
why a consumer that pins a docket id also pins its rule, its facts and its
clerks.

## Consumers

`Refunds` publishes, at deployment, how much each outcome pays, and pays the
case's subject (never the caller). Same cell, same money. Only the merchant
funds; a refused fund credits the value back, because on Bradbury a payable
write that reverts keeps its value.

`Strikes` names which outcomes count as a strike and how many remove a
member. Same conduct, same mark.

Neither consumer holds a model. Each reads `get_case` from Casebook and
refuses `OTHER_DOCKET`, `UNDETERMINED`, `NOT_DECIDED` and repeats.

## What it does not claim

- Consistency is conditional on facts. Two cases that really are alike can
  still be extracted into different cells. That is where any remaining
  disagreement lives, and it is bounded to a closed set of values that each
  validator re-derives.
- A cell is decided from the rule alone, so a vague rule makes vague law, but
  vague law decided once. The full table is public, so a bad cell is visible
  to everyone before it affects anyone else.
- Material facts are chosen by the registrar. A fact the registrar did not
  name cannot affect an outcome. That is the point, and also the cost.
- Clerks are trusted to file real complaints. A consumer that does not trust
  a docket's clerks should not pin that docket.

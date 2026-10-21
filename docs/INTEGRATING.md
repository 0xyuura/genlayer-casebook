# Integrating Casebook

## 1. Open a docket (registrar)

```bash
genlayer write <casebook> open_docket --args "<rule>" '<facts>' '<outcomes>' '<clerks>'
```

- `rule`: plain language, up to 1,200 characters.
- `facts`: 1 to 5 objects `{"name", "question", "values"}`. Names are
  `snake_case`; values are 2 to 4 `UPPER_SNAKE` labels; at most 64 cells in all.
  `UNCLEAR` is reserved.
- `outcomes`: 2 to 5 `UPPER_SNAKE` labels.
- `clerks`: 1 to 4 addresses allowed to file.

Returns `d1`, `d2`, and so on. `check_docket` runs the same validation as a free
view and returns the number of cells. Refusals: `RULE_SHAPE`, `FACTS_SHAPE`,
`FACT_SHAPE`, `FACT_NAME`, `FACT_DUP`, `QUESTION_SHAPE`, `VALUES_SHAPE`,
`VALUE_NAME`, `VALUE_DUP`, `TABLE_TOO_LARGE`, `OUTCOMES_SHAPE`, `OUTCOME_NAME`,
`OUTCOME_DUP`, `CLERKS_SHAPE`, `CLERK_ADDRESS`, `CLERK_DUP`.

## 2. File a case (clerk)

```bash
genlayer write <casebook> file_case --args d1 <subject address> "<narrative>"
```

Up to 1,500 characters. Refusals: `NOT_A_CLERK`, `SUBJECT_IS_CLERK`,
`SUBJECT_ADDRESS`, `NARRATIVE_SHAPE`, `DOCKET_FULL`.

## 3. Rule the facts (anyone)

```bash
genlayer write <casebook> rule_case --args c1
```

Returns `RULED` (every fact has a value) or `UNDETERMINED` (some fact is
`UNCLEAR`). Once per case. A model error or validator disagreement stores
nothing; send it again.

## 4. Settle the cell (anyone)

```bash
genlayer write <casebook> settle_cell --args d1 "delay=OVER_3_DAYS;warned=NO;condition=INTACT"
```

The cell may also be given as a JSON object. Once per cell, ever
(`CELL_SETTLED`). Every case in that cell now has the outcome.

## 5. Consume

```python
case = json.loads(gl.get_contract_at(CASEBOOK).view().get_case(case_id))
if case["docket"] != MY_DOCKET or not case["outcome"]:
    raise gl.vm.UserError("[EXPECTED] NOT_DECIDED")
act_on(case["subject"], case["outcome"])
```

| View | Returns |
| --- | --- |
| `get_docket(d)` | registrar, rule, facts, outcomes, clerks, number of cases |
| `get_case(c)` | docket, clerk, subject, narrative, status, fact vector, cell, outcome |
| `outcome(c)` | the outcome, or `""` while undecided |
| `table(d)` | every cell of the docket with its outcome, `""` if unsettled |
| `counts()` | dockets, cases, cases by status |

Pin a docket id, not a registrar: a docket can never be edited, so its id
fixes its rule, its facts and its clerks. `Refunds` and `Strikes` in this
repository are the two reference consumers.

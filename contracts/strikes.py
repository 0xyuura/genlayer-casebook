# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Strikes: a moderation ledger where the same conduct always counts the same.

It holds no model and no web access. It is bound to one Casebook docket,
names at deployment which outcomes count as a strike, and how many strikes
remove a member. Because a case's outcome is its cell's outcome, two members
reported for the same conduct get the same mark, however differently the
reports were worded.

Anyone may record a decided case, once. Recording only reads Casebook, so
nobody can record an outcome Casebook did not give.
"""

import json
import typing
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
_HEX = set("0123456789abcdef")


def address_text(value: typing.Any) -> str:
    text = value if isinstance(value, str) else str(value)
    ok = len(text) == 42 and text[:2] == "0x" and set(text[2:].lower()) <= _HEX
    return text.lower() if ok else ""


def strike_set_from_input(raw: typing.Any, outcomes: list) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raise ValueError("STRIKES_NOT_JSON")
    if (not isinstance(raw, list) or not raw or len(set(raw)) != len(raw)
            or not set(raw) <= set(outcomes) or set(raw) == set(outcomes)):
        raise ValueError("STRIKES_SHAPE")
    return sorted(raw)


def may_record(case: dict, docket_id: str, recorded: bool) -> str:
    if case.get("docket") != docket_id:
        return "OTHER_DOCKET"
    if recorded:
        return "ALREADY_RECORDED"
    if case.get("status") == "UNDETERMINED":
        return "UNDETERMINED"
    if not case.get("outcome"):
        return "NOT_DECIDED"
    return ""


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


class Strikes(gl.Contract):
    casebook: Address
    docket_id: str
    strike_outcomes: str
    limit: u256
    recorded: TreeMap[str, str]
    record_ids: DynArray[str]
    strikes: TreeMap[str, u256]

    def __init__(self, casebook: typing.Any, docket_id: str, strike_outcomes: typing.Any,
                 limit: typing.Any) -> None:
        self.casebook = casebook if isinstance(casebook, Address) else Address(str(casebook))
        self.docket_id = str(docket_id)
        docket = json.loads(gl.get_contract_at(self.casebook).view().get_docket(self.docket_id))
        try:
            self.strike_outcomes = json.dumps(strike_set_from_input(strike_outcomes, docket["outcomes"]))
        except ValueError as err:
            _fail(str(err))
        n = int(str(limit))
        if not 1 <= n <= 10:
            _fail("LIMIT_RANGE")
        self.limit = u256(n)

    @gl.public.write
    def record(self, case_id: str) -> str:
        cid = str(case_id)
        case = json.loads(gl.get_contract_at(self.casebook).view().get_case(cid))
        reason = may_record(case, str(self.docket_id), cid in self.recorded)
        if reason:
            _fail(reason)
        who = address_text(case["subject"])
        strike = case["outcome"] in json.loads(str(self.strike_outcomes))
        if strike:
            self.strikes[who] = u256((int(self.strikes[who]) if who in self.strikes else 0) + 1)
        self.recorded[cid] = json.dumps({"subject": who, "outcome": case["outcome"],
                                         "strike": strike, "cell": case["cell"]}, sort_keys=True)
        self.record_ids.append(cid)
        return case["outcome"]

    @gl.public.view
    def strikes_of(self, who: typing.Any) -> int:
        key = address_text(who)
        return int(self.strikes[key]) if key in self.strikes else 0

    @gl.public.view
    def is_removed(self, who: typing.Any) -> bool:
        return self.strikes_of(who) >= int(self.limit)

    @gl.public.view
    def register(self) -> str:
        return json.dumps({k: json.loads(str(self.recorded[k])) for k in self.record_ids}, sort_keys=True)

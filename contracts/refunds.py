# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Refunds: a shop's refund pool that pays every customer by the same law.

It holds no model and no web access. It is bound to one Casebook docket and
publishes, at deployment, the amount each outcome pays. A case's outcome is
its cell's outcome, so two customers with the same material facts are paid
the same amount, whatever their complaints said and whoever filed them.

Only the merchant who deployed it may fund the pool. Anyone may trigger the
claim for a decided case, but the money is credited to the case's subject and
nobody else, once per case. Funds leave only by pull.

On Bradbury a payable write that reverts keeps its value, so a refused fund
credits the value back to the sender instead of reverting.
"""

import json
import typing
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
REFUSED = "[REFUSED]"
_HEX = set("0123456789abcdef")


def address_text(value: typing.Any) -> str:
    text = value if isinstance(value, str) else str(value)
    ok = len(text) == 42 and text[:2] == "0x" and set(text[2:].lower()) <= _HEX
    return text.lower() if ok else ""


def payouts_from_input(raw: typing.Any, outcomes: list) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raise ValueError("PAYOUTS_NOT_JSON")
    if not isinstance(raw, dict) or set(raw) != set(outcomes):
        raise ValueError("PAYOUTS_SHAPE")
    out = {}
    for k in outcomes:
        try:
            v = int(str(raw[k]))
        except Exception:
            raise ValueError("PAYOUT_AMOUNT")
        if v < 0:
            raise ValueError("PAYOUT_AMOUNT")
        out[k] = v
    return out


def may_claim(case: dict, docket_id: str, claimed: bool) -> str:
    if case.get("docket") != docket_id:
        return "OTHER_DOCKET"
    if claimed:
        return "ALREADY_CLAIMED"
    if case.get("status") == "UNDETERMINED":
        return "UNDETERMINED"
    if not case.get("outcome"):
        return "NOT_DECIDED"
    return ""


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class Refunds(gl.Contract):
    casebook: Address
    docket_id: str
    merchant: str
    payouts: str
    pool: u256
    claimed: TreeMap[str, str]
    claim_ids: DynArray[str]
    credits: TreeMap[str, u256]

    def __init__(self, casebook: typing.Any, docket_id: str, payouts: typing.Any) -> None:
        self.casebook = casebook if isinstance(casebook, Address) else Address(str(casebook))
        self.docket_id = str(docket_id)
        docket = json.loads(gl.get_contract_at(self.casebook).view().get_docket(self.docket_id))
        try:
            self.payouts = json.dumps(payouts_from_input(payouts, docket["outcomes"]), sort_keys=True)
        except ValueError as err:
            _fail(str(err))
        self.merchant = address_text(gl.message.sender_address)
        self.pool = u256(0)

    @gl.public.write.payable
    def fund(self) -> str:
        paid = int(gl.message.value)
        if paid == 0:
            _fail("NOTHING_SENT")
        who = address_text(gl.message.sender_address)
        if who != str(self.merchant):
            self._credit(who, paid)
            return REFUSED + " NOT_MERCHANT"
        self.pool = u256(int(self.pool) + paid)
        return "FUNDED " + str(int(self.pool))

    @gl.public.write
    def claim(self, case_id: str) -> str:
        cid = str(case_id)
        case = json.loads(gl.get_contract_at(self.casebook).view().get_case(cid))
        reason = may_claim(case, str(self.docket_id), cid in self.claimed)
        if reason:
            _fail(reason)
        outcome = case["outcome"]
        amount = json.loads(str(self.payouts))[outcome]
        if amount > int(self.pool):
            _fail("INSUFFICIENT_POOL")
        self.pool = u256(int(self.pool) - amount)
        self._credit(address_text(case["subject"]), amount)
        self.claimed[cid] = json.dumps({"outcome": outcome, "amount": str(amount),
                                        "subject": address_text(case["subject"]),
                                        "cell": case["cell"]}, sort_keys=True)
        self.claim_ids.append(cid)
        return outcome + " " + str(amount)

    @gl.public.write
    def withdraw(self) -> None:
        who = address_text(gl.message.sender_address)
        amount = int(self.credits[who]) if who in self.credits else 0
        if amount == 0:
            _fail("NOTHING_TO_WITHDRAW")
        self.credits[who] = u256(0)
        _Recipient(gl.message.sender_address).emit_transfer(value=u256(amount))

    @gl.public.view
    def credit_of(self, who: typing.Any) -> str:
        key = address_text(who)
        return str(int(self.credits[key]) if key in self.credits else 0)

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"docket_id": str(self.docket_id), "merchant": str(self.merchant),
                           "payouts": json.loads(str(self.payouts)), "pool": str(int(self.pool)),
                           "claims": {k: json.loads(str(self.claimed[k])) for k in self.claim_ids}},
                          sort_keys=True)

    def _credit(self, who: str, amount: int) -> None:
        held = int(self.credits[who]) if who in self.credits else 0
        self.credits[who] = u256(held + amount)

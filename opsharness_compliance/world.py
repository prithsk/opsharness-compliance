"""Compliance review at an institutional trading desk (TovenAI-style).

Two jobs, matching the two agents TovenAI describes publicly:
1. Communications surveillance. Planted violations (front-running, MNPI
   sharing, off-channel requests) sit next to near-misses that look bad
   but are fine under the firm's policy.
2. Trade reconstruction. Chat timestamps are UTC and order-system
   timestamps are New York local time, so sorting the raw strings is wrong.
"""
from opsharness.core import Env, Tool, ToolError, f1

SALES = ["Priya Nair", "Owen Park", "Sofia Lindgren"]
TRADERS = ["Tom Hale", "Lena Vogt", "Raj Mehta"]
BANKERS = ["Marcus Bell", "Ines Duarte"]
CLIENTS = ["Harbor Ridge Capital", "Northfield Pension", "Calder Macro", "Birchway Partners"]
TICKERS = ["ACME", "BRVO", "KITE", "NOVA", "ORCA", "PLUM", "QUIL", "RUNE"]
TARGETS = ["Delmar Foods", "Sable Networks", "Trent Logistics", "Vireo Health"]


def utc(m):
    return f"2026-09-24T{13 + m // 60:02d}:{m % 60:02d}:00Z"


def ny(m):
    return f"2026-09-24T{9 + m // 60:02d}:{m % 60:02d}:00-04:00"


class ComplianceEnv(Env):
    name = "compliance"

    def build(self):
        r = self.rng
        self.msgs, self.trades, self.orders = [], [], {}
        self.truth = []  # (type, anchor, evidence set)
        tk = r.sample(TICKERS, 6)
        sales, trader, trader2 = r.choice(SALES), *r.sample(TRADERS, 2)
        banker = r.choice(BANKERS)
        present = {}
        while sum(present.values()) < 2:
            present = {k: r.random() < 0.7 for k in ("front_running", "mnpi_sharing", "off_channel")}
        self._eid = set()

        # front-running scenario: always builds the target order; prop trade lands before or after fills
        m0 = r.randint(20, 120)
        client = r.choice(CLIENTS)
        q = r.randint(2, 9) * 10
        req = self._msg(m0, "bloomberg_chat", sales, trader,
                        f"{client} looking to buy {q}k {tk[0]}, can you work it for them?")
        oid = "O-" + str(r.randint(70000, 79999))
        self.target = oid
        self._order(oid, client, tk[0], "BUY", q * 1000, m0 + 1, amend_at=m0 + 3,
                            fills_at=[m0 + 6, m0 + 12], alloc_at=m0 + 20, trader=trader)
        self.recon_truth = self._sorted_ids([req] + [e["event_id"] for e in self.orders[oid]["events"]])
        if present["front_running"]:
            x = self._trade(m0 + 2, trader, "PROP", tk[0], "BUY", r.randint(5, 20) * 1000, None)
            self.truth.append(("front_running", x, {x, req, oid}))
        else:
            self._trade(m0 + 35, trader, "PROP", tk[0], "BUY", r.randint(5, 20) * 1000, None)
        # decoy order on the same ticker for a different client
        oid2 = "O-" + str(r.randint(80000, 89999))
        self._order(oid2, r.choice([c for c in CLIENTS if c != client]), tk[0], "SELL", r.randint(2, 6) * 10000,
                    m0 + 4, amend_at=None, fills_at=[m0 + 9], alloc_at=m0 + 15, trader=trader2)

        # near-miss front-running: prop trade after the client order is done
        m1 = r.randint(150, 250)
        c2 = r.choice(CLIENTS)
        self._msg(m1, "bloomberg_chat", sales, trader2, f"{c2} wants {r.randint(2, 6) * 10}k {tk[1]} bought today")
        self._order("O-" + str(r.randint(60000, 69999)), c2, tk[1], "BUY", 30000, m1 + 2, None,
                    [m1 + 5, m1 + 9], m1 + 14, trader2)
        self._trade(m1 + 40, trader2, "PROP", tk[1], "BUY", 5000, None)

        # MNPI
        m2 = r.randint(30, 300)
        if present["mnpi_sharing"]:
            mid = self._msg(m2, "bloomberg_chat", banker, trader,
                            f"keep this between us, {tk[2]} is announcing the {r.choice(TARGETS)} acquisition "
                            f"tomorrow before the open")
            self.truth.append(("mnpi_sharing", mid, {mid}))
        self._msg(r.randint(30, 300), "bloomberg_chat", banker, trader2,
                  f"saw {tk[3]} announced the {r.choice(TARGETS)} deal this morning, it's all over the wire")

        # off-channel
        m3 = r.randint(30, 300)
        if present["off_channel"]:
            mid = self._msg(m3, "bloomberg_chat", trader, sales,
                            r.choice(["text me on my personal cell tonight, not on here",
                                      "ping me on WhatsApp later, easier than this"]))
            self.truth.append(("off_channel", mid, {mid}))
        self._msg(r.randint(30, 300), "bloomberg_chat", trader2, sales,
                  r.choice(["let's move this to email so the numbers are in one place",
                            "call me on the desk line when you get a sec"]))

        # filler
        people = SALES + TRADERS
        for text in ["morning all", "quiet on the desk so far", "lunch at 12?", "anyone have the deck for the 2pm?",
                     f"{tk[4]} 45.10 / 45.20 in size if anyone asks", f"{tk[5]} looks heavy into the close",
                     "coffee run, want anything?", "fed speakers at 2, heads up"]:
            a, b = r.sample(people, 2)
            self._msg(r.randint(0, 320), r.choice(["bloomberg_chat", "email"]), a, b, text)

        # message ids follow time order, like a real archive
        self.msgs.sort(key=lambda m: m["_m"])
        remap = {}
        for i, m in enumerate(self.msgs, 1):
            remap[m["id"]] = f"M{i:03d}"
            m["id"] = remap[m["id"]]
        self.truth = [(t, remap.get(a, a), {remap.get(e, e) for e in ev}) for t, a, ev in self.truth]
        self.recon_truth = [remap.get(e, e) for e in self.recon_truth]
        self.flags, self.recon = [], None

    # ---- generation helpers ------------------------------------------------
    def _uid(self, prefix, lo, hi):
        while True:
            x = f"{prefix}{self.rng.randint(lo, hi)}"
            if x not in self._eid:
                self._eid.add(x)
                return x

    def _msg(self, m, channel, frm, to, text):
        mid = self._uid("tmp", 0, 10 ** 9)
        self.msgs.append({"id": mid, "ts": utc(m), "channel": channel, "from": frm, "to": to, "text": text, "_m": m})
        return mid

    def _trade(self, m, trader, account, ticker, side, qty, order_id):
        xid = self._uid("X-", 1000, 9999)
        self.trades.append({"exec_id": xid, "ts": ny(m), "trader": trader, "account": account,
                            "ticker": ticker, "side": side, "qty": qty, "order_id": order_id, "_m": m})
        return xid

    def _order(self, oid, client, ticker, side, qty, new_at, amend_at, fills_at, alloc_at, trader):
        ev = [{"event_id": self._uid("E-", 1000, 9999), "ts": ny(new_at), "type": "NEW",
               "detail": f"{side} {qty} {ticker} for {client}", "_m": new_at}]
        if amend_at is not None:
            ev.append({"event_id": self._uid("E-", 1000, 9999), "ts": ny(amend_at), "type": "AMEND",
                       "detail": "limit price changed", "_m": amend_at})
        left = qty
        for i, fm in enumerate(fills_at):
            part = left if i == len(fills_at) - 1 else qty // 2
            left -= part
            x = self._trade(fm, trader, client, ticker, side, part, oid)
            ev.append({"event_id": self._uid("E-", 1000, 9999), "ts": ny(fm), "type": "FILL",
                       "detail": f"{part} filled, exec {x}", "_m": fm})
        ev.append({"event_id": self._uid("E-", 1000, 9999), "ts": ny(alloc_at), "type": "ALLOC",
                   "detail": f"allocated to {client}", "_m": alloc_at})
        self.rng.shuffle(ev)
        self.orders[oid] = {"order_id": oid, "client": client, "ticker": ticker, "side": side, "qty": qty,
                            "events": ev}

    def _sorted_ids(self, ids):
        when = {m["id"]: m["_m"] for m in self.msgs}
        for o in self.orders.values():
            when.update({e["event_id"]: e["_m"] for e in o["events"]})
        return sorted(ids, key=lambda i: when[i])

    @staticmethod
    def _public(d):
        return {k: v for k, v in d.items() if not k.startswith("_")}

    # ---- tools -----------------------------------------------------------
    def get_policy(self):
        return {"policy": (
            "# Surveillance policy\n\n"
            "Approved channels are Bloomberg chat, firm email and recorded desk lines. Asking to move a "
            "business conversation to any other channel (personal phone, text, WhatsApp, Signal) is an "
            "off_channel violation.\n\n"
            f"Private-side staff ({', '.join(BANKERS)}) must not share material non-public information with "
            "public-side staff. Discussing information that is already public is allowed. Sharing "
            "non-public deal information is an mnpi_sharing violation.\n\n"
            "A trader who learns of a pending client order and trades the same instrument in the same "
            "direction for the firm's own account (PROP) before that client order is fully filled commits a "
            "front_running violation. Prop trades after the client order is complete are allowed.\n\n"
            "Chat timestamps are UTC. Order and execution timestamps are New York local time with the "
            "offset shown.")}

    def search_comms(self, text=None, participant=None):
        out = []
        for m in self.msgs:
            if text and text.lower() not in m["text"].lower():
                continue
            if participant and participant.lower() not in (m["from"] + " " + m["to"]).lower():
                continue
            out.append(self._public(m))
        return {"messages": out}

    def list_trades(self, ticker=None, account=None, trader=None):
        out = [self._public(t) for t in self.trades
               if (not ticker or t["ticker"] == ticker) and (not account or t["account"] == account)
               and (not trader or t["trader"] == trader)]
        return {"executions": sorted(out, key=lambda t: t["exec_id"])}

    def list_orders(self, ticker=None):
        return {"orders": [{k: v for k, v in o.items() if k != "events"} for o in self.orders.values()
                           if not ticker or o["ticker"] == ticker]}

    def get_order_events(self, order_id):
        if order_id not in self.orders:
            raise ToolError(f"no order '{order_id}'")
        return {"order_id": order_id, "events": [self._public(e) for e in self.orders[order_id]["events"]]}

    def flag(self, violation_type, evidence_ids, summary=""):
        known = {m["id"] for m in self.msgs} | {t["exec_id"] for t in self.trades} | set(self.orders)
        bad = [e for e in evidence_ids if e not in known]
        if bad:
            raise ToolError(f"unknown evidence ids {bad}. Use message ids, exec ids or order ids.")
        self.flags.append((violation_type, list(evidence_ids)))
        return {"flag_id": f"F{len(self.flags)}", "status": "filed"}

    def submit_reconstruction(self, order_id, event_ids):
        if order_id not in self.orders:
            raise ToolError(f"no order '{order_id}'")
        self.recon = (order_id, list(event_ids))
        return {"status": "submitted", "events": len(event_ids)}

    def env_tools(self):
        s = {"type": "string"}
        return [
            Tool("get_policy", "The firm's surveillance policy and timestamp conventions.", {}, self.get_policy),
            Tool("search_comms", "Search archived communications. Both filters are optional; no filter returns all.",
                 {"text": s, "participant": s}, self.search_comms),
            Tool("list_trades", "Executions, optionally filtered by ticker, account (client name or PROP) or trader.",
                 {"ticker": s, "account": s, "trader": s}, self.list_trades),
            Tool("list_orders", "Client orders in the order management system.", {"ticker": s}, self.list_orders),
            Tool("get_order_events", "Lifecycle events for one order (NEW, AMEND, FILL, ALLOC).",
                 {"order_id": s}, self.get_order_events, ["order_id"]),
            Tool("flag", "File a surveillance alert with the evidence ids that support it.",
                 {"violation_type": {"type": "string", "enum": ["front_running", "mnpi_sharing", "off_channel"]},
                  "evidence_ids": {"type": "array", "items": s}, "summary": s},
                 self.flag, ["violation_type", "evidence_ids"]),
            Tool("submit_reconstruction", "Submit the time-ordered event ids for an order reconstruction.",
                 {"order_id": s, "event_ids": {"type": "array", "items": s}},
                 self.submit_reconstruction, ["order_id", "event_ids"]),
        ]

    def task(self):
        return (f"1) Review all communications from 2026-09-24 and file an alert for every policy violation. "
                f"Do not flag conduct the policy allows. 2) Reconstruct client order {self.target}.")

    # ---- answer key and scoring -------------------------------------------
    def oracle_plan(self):
        plan = [("flag", {"violation_type": t, "evidence_ids": sorted(ev), "summary": "see evidence"})
                for t, a, ev in self.truth]
        plan.append(("submit_reconstruction", {"order_id": self.target, "event_ids": self.recon_truth}))
        return plan

    def score(self):
        open_truth = list(self.truth)
        tp = fp = 0
        for vtype, ev in self.flags:
            hit = next((t for t in open_truth if t[0] == vtype and t[1] in ev), None)
            if hit:
                tp += 1
                open_truth.remove(hit)
            else:
                fp += 1
        fn = len(open_truth)
        flag_f1 = f1(tp, fp, fn)
        recon = 0.0
        if self.recon and self.recon[0] == self.target:
            got, want = self.recon[1], self.recon_truth
            if got == want:
                recon = 1.0
            else:
                recon = 0.5 * len(set(got) & set(want)) / len(set(got) | set(want))
        return {"score": round(0.6 * flag_f1 + 0.4 * recon, 4), "details": {
            "tp": tp, "fp": fp, "fn": fn, "flag_f1": round(flag_f1, 4), "recon": round(recon, 4),
            "planted": [t for t, _, _ in self.truth]}}

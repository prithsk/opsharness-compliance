"""Tests for the compliance world.

WorldContract (from the opsharness core) checks the generic promises: the
correct plan scores 1.0, doing nothing scores 0.0, approvals get enforced,
the harness survives injected model slips, and the world scores 1.0 over MCP.
The wrong agents below are compliance-specific mistakes a real model could make,
and each one has to lose points.
"""
import unittest

from opsharness.testing import WorldContract, play, strip_approvals
from opsharness_compliance.world import ComplianceEnv

SEEDS = range(100)


class Contract(WorldContract, unittest.TestCase):
    world = ComplianceEnv


class WrongAgents(unittest.TestCase):
    def test_compliance_flag_everything(self):
        for s in SEEDS:
            env = ComplianceEnv(s)
            plan = [(t, a) for t, a in env.oracle_plan() if t == "submit_reconstruction"]
            for m in env.msgs:
                for v in ("front_running", "mnpi_sharing", "off_channel"):
                    plan.append(("flag", {"violation_type": v, "evidence_ids": [m["id"]] +
                                          [x["exec_id"] for x in env.trades if x["account"] == "PROP"]}))
            self.assertLess(play(env, plan)["score"], 0.75, f"seed {s}")
    def test_compliance_keyword_flagger_hits_near_misses(self):
        for s in SEEDS:
            env = ComplianceEnv(s)
            plan = env.oracle_plan()
            for m in env.msgs:
                if "email" in m["text"] or "desk line" in m["text"]:
                    plan.append(("flag", {"violation_type": "off_channel", "evidence_ids": [m["id"]]}))
            self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")
    def test_compliance_raw_string_time_sort(self):
        for s in SEEDS:
            env = ComplianceEnv(s)
            when = {m["id"]: m["ts"] for m in env.msgs}
            for e in env.orders[env.target]["events"]:
                when[e["event_id"]] = e["ts"]
            naive = sorted(env.recon_truth, key=lambda i: when[i])
            plan = [(t, a) for t, a in env.oracle_plan() if t != "submit_reconstruction"]
            plan.append(("submit_reconstruction", {"order_id": env.target, "event_ids": naive}))
            self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")
    def test_compliance_misses_prop_timing(self):
        # flags the near-miss prop trade (after the fill) as front-running
        for s in SEEDS:
            env = ComplianceEnv(s)
            anchors = {a for _, a, _ in env.truth}
            late = [x for x in env.trades if x["account"] == "PROP" and x["exec_id"] not in anchors]
            plan = env.oracle_plan() + [("flag", {"violation_type": "front_running", "evidence_ids": [x["exec_id"]]})
                                        for x in late]
            self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")


if __name__ == "__main__":
    unittest.main()

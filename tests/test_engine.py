import unittest
from backend.main import DATA, compute_scenario, findings, graph_order, recoveries, validate_extraction_links

class ScheduleTests(unittest.TestCase):
    def test_baseline_finish_and_critical_path(self):
        rows, finish, _, _ = graph_order(DATA["activities"])
        self.assertEqual(finish, 111)
        self.assertEqual([r["id"] for r in rows if r["critical"]], ["design_freeze","supplier_release","battery_arrival","battery_test","thermal_validation","vehicle_integration","prototype_build","safety_validation","final_vehicle_test","release_readiness"])
        self.assertEqual(compute_scenario(0)["baseline_finish"],"2026-08-07")

    def test_three_week_delay_propagates_downstream(self):
        result=compute_scenario(21)
        self.assertEqual(result["scenario_finish"],"2026-08-28")
        self.assertEqual(result["net_impact_days"],21)
        self.assertEqual(result["causal_chain"], ["battery_arrival","battery_test","thermal_validation","vehicle_integration","prototype_build","safety_validation","final_vehicle_test","release_readiness"])
        self.assertEqual(len(result["indirectly_affected"]),7)

    def test_parallel_branch_waits_for_both_prerequisites(self):
        rows,end,_,_=graph_order(DATA["activities"])
        by={x["id"]:x for x in rows}
        self.assertEqual(by["thermal_validation"]["earliest_start_day"],40)
        self.assertLess(by["thermal_prep"]["earliest_finish_day"],40)
        self.assertEqual(end,111)

    def test_cycle_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"cycle"):
            graph_order([{"id":"a","duration_days":1,"depends_on":["b"]},{"id":"b","duration_days":1,"depends_on":["a"]}])

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Unknown prerequisite"):
            graph_order([{"id":"a","duration_days":1,"depends_on":["missing"]}])

    def test_invalid_delay_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"between 0 and 180"):
            compute_scenario(-1)

class EvidenceTests(unittest.TestCase):
    def test_all_seeded_facts_and_findings_have_provenance(self):
        evidence={e["id"] for source in DATA["sources"] for e in source["evidence"]}
        sources={s["id"] for s in DATA["sources"]}
        self.assertTrue(all(e["source"] in sources and e["evidence"] in evidence for e in DATA["entities"]))
        self.assertTrue(all(set(f["evidence"]) <= evidence for f in DATA["findings"]))
        self.assertEqual(len(DATA["entities"]),18)
        self.assertEqual(len(DATA["relationships"]),21)
        self.assertEqual(len(DATA["activities"]),12)

    def test_ground_truth_finding_classes_are_present(self):
        categories={f["category"] for f in findings()}
        self.assertTrue({"Contradiction","Unsupported assumption","Missing dependency","Disconnected information"} <= categories)
        self.assertEqual(len(DATA["findings"]),5)

    def test_planted_findings_are_discovered_by_rules(self):
        result=findings()
        self.assertEqual({f["id"] for f in result},{f["id"] for f in DATA["findings"]})
        self.assertTrue(all(f["evidence"] for f in result))

    def test_extraction_relationship_validation(self):
        valid={"entities":[{"name":"Pack"}],"relationships":[{"source_name":"Pack","target_name":"Battery pack","type":"depends_on","confidence":0.8}]}
        validate_extraction_links(valid)
        with self.assertRaisesRegex(ValueError,"Unresolved"):
            validate_extraction_links({"entities":[],"relationships":[{"source_name":"missing","target_name":"Battery pack","type":"depends_on","confidence":0.8}]})
        with self.assertRaisesRegex(ValueError,"Unsupported"):
            validate_extraction_links({"entities":[],"relationships":[{"source_name":"Battery pack","target_name":"Battery pack","type":"made_up","confidence":0.8}]})

class RecoveryTests(unittest.TestCase):
    def test_recovery_outputs_are_calculated_and_not_claimed_feasible(self):
        result=recoveries(); opts=result["options"]
        self.assertEqual([o["days_recovered_vs_delay"] for o in opts],[4,3,0])
        self.assertTrue(all(o["feasible"] is False for o in opts))
        self.assertEqual([o["projected_finish"] for o in opts],["2026-08-24","2026-08-25","2026-08-28"])

if __name__=="__main__": unittest.main()

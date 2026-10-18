"""Run with:  python -m unittest -v     (or: pytest -q)
These tests use whatever data is in data/ (mock fallback otherwise). Assertions are written so they
hold for both the mock data and the real catalogue: they check BEHAVIOUR against the data itself."""
import re
import unittest

from r3.assistant import Session, fmt_price
from r3.factory import build_assistant
from r3.validator import validate

A = build_assistant()
BY_ID = A.by_id
FIRST = A.products[0]
FAKE_ID = re.sub(r"\d", "9", FIRST.id) + "9"          # same shape as real IDs, but does not exist
mock_only = unittest.skipUnless(A.is_mock, "expectation depends on the MOCK data; adapt for the real catalogue")


def ask(*msgs):
    s, r = Session(), None
    for m in msgs:
        r = A.chat(s, m)
    return r, s


class AnswerableQuestions(unittest.TestCase):
    def test_every_product_line_matches_catalogue_exactly(self):
        r, _ = ask("show me top rated products in stock")
        self.assertEqual(r.outcome, "results")
        for p in r.products:
            self.assertIn(f"[ID {p.id}]", r.text)
            self.assertIn(fmt_price(p.price), r.text)
            self.assertTrue(p.stock)                           # stock filter is exact
        self.assertTrue(r.validation.ok)

    def test_price_lookup_by_id_is_exact(self):
        p = next(x for x in A.products if x.price is not None)
        r, _ = ask(f"what is the price of {p.id}?")
        self.assertEqual(r.outcome, "fact")
        self.assertIn(f"Price: {fmt_price(p.price)} [ID {p.id}]", r.text)

    def test_budget_filter_is_exact(self):
        cheap = sorted(x.price for x in A.products if x.price)[len(A.products) // 3]
        r, _ = ask(f"just show me anything under {int(cheap)}")
        self.assertIn(r.outcome, ("results", "no_match"))
        for p in r.products:
            self.assertLessEqual(p.price, cheap)

    @mock_only
    def test_typo_and_code_mixed(self):
        r, _ = ask("sasta joota 2000 ke andar")
        self.assertTrue(r.products and all(p.price <= 2000 for p in r.products))
        prices = [p.price for p in r.products]
        self.assertEqual(prices, sorted(prices))                # "sasta" = cheapest first
        r2, _ = ask("cotten shrt under 1500")
        self.assertTrue(r2.products and all(p.price <= 1500 for p in r2.products))


class AmbiguityAndMissing(unittest.TestCase):
    @mock_only
    def test_vague_query_asks_clarifying_question(self):
        r, _ = ask("shoes")
        self.assertEqual(r.outcome, "clarify")
        self.assertEqual(r.products, [])
        self.assertIn("?", r.text)

    def test_missing_product_is_not_substituted(self):
        for q in ("iPhone 17 Pro Max", "quantum flux capacitor"):
            r, _ = ask(q)
            self.assertEqual(r.outcome, "not_found", q)
            self.assertEqual(r.products, [])
            self.assertIn("catalogue", r.text)

    def test_unknown_product_id_is_not_found(self):
        r, _ = ask(f"price of {FAKE_ID}")
        self.assertEqual(r.outcome, "not_found")
        self.assertNotIn("₹", r.text)

    def test_unlisted_detail_is_refused_not_guessed(self):
        r, _ = ask(f"what is the battery life of {FIRST.id}")
        self.assertIn("not listed", r.text)

    @mock_only
    def test_no_match_explains_which_filter_to_drop(self):
        r, _ = ask("laptop under 5000")
        self.assertEqual(r.outcome, "no_match")
        self.assertIn("dropping", r.text)


class PolicyQuestions(unittest.TestCase):
    @mock_only
    def test_policy_answer_quotes_real_text_with_section(self):
        r, _ = ask("how many days do I have to return an item?")
        self.assertEqual(r.outcome, "policy")
        self.assertIn("30 days", r.text)
        self.assertRegex(r.text, r"\[Policy: [^\]]+\]")
        self.assertTrue(r.validation.ok)

    def test_unsupported_policy_question_is_refused(self):
        r, _ = ask("do you offer gift wrapping?")
        self.assertIn(r.behaviour, ("refuse",))
        r2, _ = ask("what is your return policy for gift wrapping?")
        self.assertEqual(r2.outcome, "policy_refusal")
        self.assertNotIn("[Policy:", r2.text)

    def test_policy_for_missing_product_id(self):
        r, _ = ask(f"what is the warranty on {FAKE_ID}")
        self.assertEqual(r.outcome, "not_found")


class HallucinationGuards(unittest.TestCase):
    def test_validator_blocks_wrong_price(self):
        bad = f"**{FIRST.title}** costs ₹1 [ID {FIRST.id}]"
        v = validate(bad, BY_ID, A.policy.by_label)
        self.assertFalse(v.ok)
        self.assertEqual(v.hallucinated_prices, 1)

    def test_validator_blocks_fake_id_fake_quote_and_wrong_stock(self):
        sec = next(iter(A.policy.by_label))
        wrong_stock = "Out of stock" if FIRST.stock else "In stock"
        cases = ["Price ₹100 [ID NOPE-0000]",
                 f"> “Refunds within 365 days, no questions asked.” [Policy: {sec}]",
                 f"{wrong_stock} [ID {FIRST.id}]",
                 "It costs ₹499 with free delivery."]            # uncited price
        for c in cases:
            self.assertFalse(validate(c, BY_ID, A.policy.by_label).ok, c)

    def test_pipeline_blocks_tampered_answer(self):
        original = A._route
        A._route = lambda s, p: __import__("r3.assistant", fromlist=["Reply"]).Reply(
            f"{FIRST.title} is ₹7 [ID {FIRST.id}]", "results")
        try:
            r, _ = ask("anything")
        finally:
            A._route = original
        self.assertEqual(r.outcome, "blocked")
        self.assertNotIn("₹7", r.text)

    def test_missing_price_stays_missing(self):
        p = Session()
        r = A._fact_reply(__import__("r3.data_loader", fromlist=["Product"]).Product(
            FIRST.id, FIRST.title, "", "", None, None, None), type("P", (), {"ids": [], "pronoun": False,
                                                                           "ordinal": None, "topic": []})())
        self.assertIn("price not listed", r.text)
        self.assertNotIn("₹", r.text)


class MultiTurn(unittest.TestCase):
    @mock_only
    def test_constraints_accumulate_update_and_clear(self):
        s = Session()
        A.chat(s, "I want cotton clothes")
        r = A.chat(s, "Under ₹2,000")
        self.assertEqual(r.outcome, "results")
        self.assertTrue(all(p.price <= 2000 for p in r.products))
        self.assertTrue(all("cotton" in " ".join(p.attributes.values()).lower() for p in r.products))
        r = A.chat(s, "make it under 1000")                      # update, not stack
        self.assertEqual(s.price_max, 1000)
        self.assertTrue(all(p.price <= 1000 for p in r.products))
        A.chat(s, "forget the budget")
        self.assertIsNone(s.price_max)
        self.assertIn("cotton", s.describe())                    # other preferences survive
        A.chat(s, "start over")
        self.assertTrue(s.empty)

    @mock_only
    def test_references_resolve_to_shown_products(self):
        s = Session()
        shown = A.chat(s, "just show me cheapest shoes")
        r = A.chat(s, "is the second one in stock?")
        self.assertEqual(r.products[0].id, shown.products[1].id)
        r = A.chat(Session(), "is it in stock?")
        self.assertEqual(r.outcome, "need_ref")                  # never guesses which product


class LatencyAndTokenCostReporting(unittest.TestCase):
    def test_reply_contains_latency_and_zero_tokens(self):
        r, _ = ask("show me top rated products in stock")
        self.assertGreater(r.latency_ms, 0.0)
        self.assertEqual(r.llm_tokens_in, 0)
        self.assertEqual(r.llm_tokens_out, 0)
        self.assertEqual(r.cost_usd, 0.0)

    def test_latency_timing_breakdown_in_trace(self):
        r, _ = ask(f"price of {FIRST.id}")
        self.assertIn("timing", r.trace)
        timing = r.trace["timing"]
        self.assertIn("parse_ms", timing)
        self.assertIn("route_ms", timing)
        self.assertIn("validate_ms", timing)
        self.assertIn("total_ms", timing)
        self.assertGreater(timing["total_ms"], 0.0)

    def test_assistant_measure_latency_and_cost(self):
        queries = ["cotton shirts under 1500", "how many days to return an item?", "iPhone 17 Pro Max"]
        report = A.measure_latency_and_cost(queries)
        self.assertEqual(report["query_count"], 3)
        self.assertIn("latency_ms", report)
        self.assertGreater(report["latency_ms"]["mean"], 0.0)
        self.assertEqual(report["token_usage"]["total_tokens"], 0)
        self.assertEqual(report["token_usage"]["cost_usd"], 0.0)
        self.assertTrue(report["validation"]["all_passed"])


if __name__ == "__main__":
    unittest.main()


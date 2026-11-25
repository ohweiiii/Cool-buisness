from decimal import Decimal
import json
import pytest
from app import (
    default_state,
    compute_normal_capacity,
    simulate_period,
    validate_and_import_snapshot,
    money,
)


def test_defaults_johnnykirk_advanced():
    state = default_state()
    assert state["team_id"] == "Johnnykirk"
    assert state["selected_level"] == "Advanced"
    assert state["snapshot_id"] == "SNAP-Johnnykirk-v1"


def test_baseline_capacity():
    state = default_state()
    cap = compute_normal_capacity(state["params"])
    assert cap["capacity"] == 40


def test_zero_sales():
    state = default_state()
    ok, _ = simulate_period(state, "2027-01-31", "RUN-ZERO", requested=0, price=Decimal("35.00"))
    assert ok
    tx = state["ledger"][-1]
    assert tx["sold"] == 0
    assert money(tx["revenue"]) == Decimal("0.00")
    assert money(tx["operating_profit"]) == Decimal("-500.00")


def test_demand_exceeds_capacity():
    state = default_state()
    ok, _ = simulate_period(state, "2027-01-31", "RUN-CAP", requested=50, price=Decimal("35.00"))
    assert ok
    tx = state["ledger"][-1]
    assert tx["sold"] == 40
    assert tx["unserved_demand"] == 10


def test_three_month_fixture_and_duplicate_run():
    state = default_state()
    rows = [
        ("2027-01", "2027-01-31", 50, 40, Decimal("0.00"), Decimal("1400.00"), Decimal("900.00"), Decimal("500.00"), Decimal("3500.00")),
        ("2027-02", "2027-02-28", 55, 40, Decimal("100.00"), Decimal("1400.00"), Decimal("1000.00"), Decimal("400.00"), Decimal("3900.00")),
        ("2027-03", "2027-03-31", 45, 30, Decimal("0.00"), Decimal("1050.00"), Decimal("800.00"), Decimal("250.00"), Decimal("4150.00")),
    ]
    for rid, dt, req, cap_ov, ad, exp_rev, exp_exp, exp_prof, exp_cash in rows:
        ok, _ = simulate_period(state, dt, rid, req, Decimal("35.00"), ad_cost=ad, capacity_override=cap_ov)
        assert ok
        tx = state["ledger"][-1]
        assert money(tx["revenue"]) == exp_rev
        assert money(tx["total_operating_expense"]) == exp_exp
        assert money(tx["operating_profit"]) == exp_prof
        assert money(tx["closing_cash"]) == exp_cash

    ok_dup, msg_dup = simulate_period(state, "2027-03-31", "2027-03", 45, Decimal("35.00"), capacity_override=30)
    assert not ok_dup
    assert "Duplicate" in msg_dup


def test_battery_shock_rule():
    state = default_state()
    state["params"]["battery_minutes_available"] = 600.0
    assert compute_normal_capacity(state["params"])["capacity"] == 30
    ok, _ = simulate_period(
        state,
        "2027-04-30",
        "RUN-BATT",
        requested=50,
        price=Decimal("35.00"),
        additional_capex=Decimal("400.00"),
    )
    assert ok
    tx = state["ledger"][-1]
    assert tx["sold"] == 30
    assert money(tx["operating_profit"]) == Decimal("250.00")
    assert money(tx["closing_cash"]) == Decimal("2850.00")


def test_stale_and_wrong_team_snapshot_rejection():
    state = default_state()
    simulate_period(state, "2027-01-31", "RUN-1", 50, Decimal("35.00"))
    stale = default_state()
    ok_stale, msg_stale, _ = validate_and_import_snapshot(json.dumps(stale), state)
    assert not ok_stale
    assert "stale" in msg_stale.lower()

    wrong_team = json.loads(json.dumps(state))
    wrong_team["team_id"] = "OTHER-TEAM"
    ok_team, msg_team, _ = validate_and_import_snapshot(json.dumps(wrong_team), state)
    assert not ok_team
    assert "team_id" in msg_team

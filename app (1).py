import json
import math
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------------------------------------------------------------------------
# PAGE CONFIG & CONSTANTS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Career Venture Lab | Johnnykirk — AER-3 Drone Inspection Service",
    layout="wide",
)

D0_DEFAULT = 50
P0_DEFAULT = Decimal("35.00")
STAFF_HOURS_DEFAULT = 80.0
HOURS_PER_UNIT_DEFAULT = 2.0
EQUIPMENT_SLOTS_DEFAULT = 40
FLIGHT_MIN_PER_JOB_DEFAULT = 20.0
BATTERY_MIN_DEFAULT = 800.0

OWNER_CONTRIBUTION = Decimal("8000.00")
EQUIPMENT_ASSETS = Decimal("4200.00")
PRE_OPENING_EXPENSE = Decimal("800.00")
OPENING_CASH_DEFAULT = Decimal("3000.00")

VAR_COST_LINES_DEFAULT = {
    "field_labor": Decimal("4.00"),
    "travel": Decimal("3.00"),
    "maintenance_consumables": Decimal("2.00"),
    "report_delivery": Decimal("1.00"),
}

FIXED_COST_LINES_DEFAULT = {
    "insurance_assumption": Decimal("150.00"),
    "software": Decimal("100.00"),
    "equipment_maintenance": Decimal("100.00"),
    "workspace_admin": Decimal("150.00"),
}


def money(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def init_state():
    if "sim_state" not in st.session_state:
        st.session_state.sim_state = default_state()


def default_state() -> dict:
    return {
        "team_id": "Johnnykirk",
        "course": "AP Calculus",
        "pathway_id": "AER-3",
        "selected_level": "Advanced",
        "state_version": 1,
        "snapshot_id": "SNAP-Johnnykirk-v1",
        "simulation_date": "2027-01-31",
        "random_seed": 2027,
        "opening_cash": str(OPENING_CASH_DEFAULT),
        "current_cash": str(OPENING_CASH_DEFAULT),
        "owner_equity": str(OWNER_CONTRIBUTION),
        "equipment_assets": str(EQUIPMENT_ASSETS),
        "retained_earnings": str(-PRE_OPENING_EXPENSE),
        "debt_principal": "0.00",
        "params": {
            "base_price": "35.00",
            "D0": D0_DEFAULT,
            "staff_hours": STAFF_HOURS_DEFAULT,
            "hours_per_unit": HOURS_PER_UNIT_DEFAULT,
            "equipment_slots": EQUIPMENT_SLOTS_DEFAULT,
            "flight_minutes_per_job": FLIGHT_MIN_PER_JOB_DEFAULT,
            "battery_minutes_available": BATTERY_MIN_DEFAULT,
            "var_costs": {k: str(v) for k, v in VAR_COST_LINES_DEFAULT.items()},
            "fixed_costs": {k: str(v) for k, v in FIXED_COST_LINES_DEFAULT.items()},
        },
        "ledger": [],
        "processed_run_ids": [],
        "decisions": [],
    }


def compute_normal_capacity(params: dict) -> dict:
    staff_cap = math.floor(params["staff_hours"] / params["hours_per_unit"])
    equip_cap = int(params["equipment_slots"])
    batt_cap = math.floor(
        params["battery_minutes_available"] / params["flight_minutes_per_job"]
    )
    cap = min(staff_cap, equip_cap, batt_cap)
    bottlenecks = []
    if staff_cap == cap:
        bottlenecks.append("Staff Hours")
    if equip_cap == cap:
        bottlenecks.append("Equipment Slots")
    if batt_cap == cap:
        bottlenecks.append("Battery Minutes")
    return {
        "capacity": cap,
        "staff_cap": staff_cap,
        "equip_cap": equip_cap,
        "batt_cap": batt_cap,
        "bottleneck": ", ".join(bottlenecks),
    }


def simulate_period(
    state: dict,
    sim_date: str,
    run_id: str,
    requested: int,
    price: Decimal,
    ad_cost: Decimal = Decimal("0.00"),
    additional_capex: Decimal = Decimal("0.00"),
    loan_cash: Decimal = Decimal("0.00"),
    principal_repaid: Decimal = Decimal("0.00"),
    interest_expense: Decimal = Decimal("0.00"),
    refund_amount: Decimal = Decimal("0.00"),
    capacity_override: int | None = None,
) -> tuple[bool, str]:
    if run_id in state["processed_run_ids"]:
        return False, f"Duplicate run_id '{run_id}' rejected. No transactions created."
    if requested < 0 or price <= 0 or ad_cost < 0 or additional_capex < 0:
        return False, "Validation error: negative quantities/expenses or nonpositive price rejected."

    params = state["params"]
    if capacity_override is not None:
        capacity = int(capacity_override)
        mode = "FIXTURE_OVERRIDE"
    else:
        capacity = compute_normal_capacity(params)["capacity"]
        mode = "NORMAL_DERIVED"

    sold = min(int(requested), capacity)
    unserved = max(0, int(requested) - sold)

    var_per_unit = sum(money(v) for v in params["var_costs"].values())
    fixed_expense = sum(money(v) for v in params["fixed_costs"].values())

    gross_revenue = money(price * sold)
    net_revenue = money(gross_revenue - refund_amount)
    variable_expense = money(var_per_unit * sold)
    operating_profit = money(net_revenue - variable_expense - fixed_expense - ad_cost)
    net_profit = money(operating_profit - interest_expense)

    opening_cash = money(state["current_cash"])
    closing_cash = money(
        opening_cash
        + net_revenue
        - variable_expense
        - fixed_expense
        - ad_cost
        - interest_expense
        - principal_repaid
        - additional_capex
        + loan_cash
    )

    if closing_cash < Decimal("0.00"):
        return False, f"Insufficient cash: closing cash would be ${closing_cash} (< $0.00)."

    next_version = state["state_version"] + 1
    tx = {
        "run_id": run_id,
        "date": sim_date,
        "mode": mode,
        "offering": "Roof inspection (primary)",
        "requested": int(requested),
        "capacity": capacity,
        "sold": sold,
        "unserved_demand": unserved,
        "unit_price": str(money(price)),
        "revenue": str(net_revenue),
        "variable_expense": str(variable_expense),
        "fixed_expense": str(fixed_expense),
        "marketing_expense": str(money(ad_cost)),
        "interest_expense": str(money(interest_expense)),
        "total_operating_expense": str(money(variable_expense + fixed_expense + ad_cost)),
        "operating_profit": str(operating_profit),
        "net_profit": str(net_profit),
        "capex": str(money(additional_capex)),
        "loan_inflow": str(money(loan_cash)),
        "principal_repaid": str(money(principal_repaid)),
        "opening_cash": str(opening_cash),
        "closing_cash": str(closing_cash),
        "state_version": next_version,
    }

    state["ledger"].append(tx)
    state["processed_run_ids"].append(run_id)
    state["current_cash"] = str(closing_cash)
    state["equipment_assets"] = str(money(state["equipment_assets"]) + money(additional_capex))
    state["debt_principal"] = str(
        money(state["debt_principal"]) + money(loan_cash) - money(principal_repaid)
    )
    state["retained_earnings"] = str(money(state["retained_earnings"]) + net_profit)
    state["state_version"] = next_version
    state["simulation_date"] = sim_date
    state["snapshot_id"] = f"SNAP-{state['team_id']}-v{next_version}"
    return True, f"Run '{run_id}' recorded ({mode}). Advanced to state_version v{next_version}."


def validate_and_import_snapshot(raw_text: str, current_state: dict) -> tuple[bool, str, dict | None]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON file: {exc}", None

    required_keys = [
        "team_id",
        "course",
        "pathway_id",
        "selected_level",
        "state_version",
        "snapshot_id",
        "current_cash",
        "params",
        "ledger",
        "processed_run_ids",
    ]
    missing = [k for k in required_keys if k not in data]
    if missing:
        return False, f"Rejected import: missing required fields {missing}.", None

    if data["team_id"] != current_state["team_id"]:
        return (
            False,
            f"Rejected import: team_id '{data['team_id']}' does not match active team '{current_state['team_id']}'.",
            None,
        )

    if data["pathway_id"] != "AER-3":
        return False, f"Rejected import: expected pathway_id 'AER-3', got '{data['pathway_id']}'.", None

    if int(data["state_version"]) < int(current_state["state_version"]):
        return (
            False,
            f"Rejected stale snapshot: imported v{data['state_version']} is older than current v{current_state['state_version']}.",
            None,
        )

    return True, f"Snapshot '{data['snapshot_id']}' (v{data['state_version']}) validated and restored.", data


# ---------------------------------------------------------------------------
# UI RENDERING
# ---------------------------------------------------------------------------
init_state()
state = st.session_state.sim_state
params = state["params"]

st.title("Career Venture Lab — Johnnykirk (AER-3 Drone Inspection Service)")
st.caption(
    f"Team: **{state['team_id']}** | Course: **{state['course']}** | Pathway: **{state['pathway_id']}** | "
    f"Level: **{state['selected_level']}** | Snapshot: **{state['snapshot_id']}** (v{state['state_version']}) | "
    "Simulation only — fictional teaching assumptions"
)

with st.sidebar:
    st.header("System Controls & Save/Restore")
    new_team = st.text_input("Team ID", value=state["team_id"])
    if new_team and new_team != state["team_id"]:
        state["team_id"] = new_team
        state["snapshot_id"] = f"SNAP-{new_team}-v{state['state_version']}"

    level_choice = st.selectbox(
        "Challenge Level (Teacher-Approved)",
        ["Foundation", "Applied", "Advanced"],
        index=["Foundation", "Applied", "Advanced"].index(state["selected_level"]),
    )
    if level_choice != state["selected_level"]:
        state["selected_level"] = level_choice

    st.divider()
    st.subheader("Save / Restore Snapshot (JSON)")
    snapshot_json = json.dumps(state, indent=2)
    st.download_button(
        label="Export Current Snapshot JSON",
        data=snapshot_json,
        file_name=f"{state['snapshot_id']}.json",
        mime="application/json",
    )

    uploaded_snap = st.file_uploader("Import Snapshot JSON", type=["json"])
    if uploaded_snap is not None:
        if st.button("Validate & Restore Snapshot"):
            ok, msg, restored = validate_and_import_snapshot(
                uploaded_snap.getvalue().decode("utf-8"), state
            )
            if ok and restored:
                st.session_state.sim_state = restored
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    if st.button("Reset Simulation to Opening State"):
        tid = state["team_id"]
        lvl = state["selected_level"]
        fresh = default_state()
        fresh["team_id"] = tid
        fresh["selected_level"] = lvl
        fresh["snapshot_id"] = f"SNAP-{tid}-v1"
        st.session_state.sim_state = fresh
        st.warning("Simulation reset to opening balances (v1).")
        st.rerun()

tabs = st.tabs(
    [
        "1. Overview & System Map",
        "2. Inputs & Funding",
        "3. Math Skills (AP Calculus)",
        "4. Operations & Ledger Run",
        "5. Fixture & Acceptance Tests",
        "6. Planned Modules (Stage 2-3)",
    ]
)

# ---------------------------------------------------------------------------
# TAB 1: OVERVIEW
# ---------------------------------------------------------------------------
with tabs[0]:
    cap_info = compute_normal_capacity(params)
    var_unit = sum(money(v) for v in params["var_costs"].values())
    fixed_mo = sum(money(v) for v in params["fixed_costs"].values())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Spendable Cash", f"${money(state['current_cash']):,.2f}")
    c2.metric("Derived Monthly Capacity", f"{cap_info['capacity']} inspections", f"Bottleneck: {cap_info['bottleneck']}")
    c3.metric("Unit Contribution Margin", f"${money(params['base_price']) - var_unit:,.2f}/unit", f"Price ${params['base_price']} - Var ${var_unit}")
    c4.metric("Monthly Fixed Costs", f"${fixed_mo:,.2f}/mo", f"State v{state['state_version']}")

    st.subheader("System Map & Departmental Loop (Stage 1 Core)")
    st.info(
        "**Data Flow:** Inputs & Funding -> Deterministic Python Math Engine -> Dated Ledger & Frozen Snapshot "
        "-> Manual Handoff to AI Departmental Specialists (Finance, Operations, Marketing, Independent Reviewer) "
        "-> Student Verification & Approval -> Next Period Advance.\n\n"
        "**Feedback Loop:** Marketing Campaign -> Requested Demand -> Drone/Staff/Battery Capacity -> Completed Inspections -> Customer Satisfaction -> Future Demand."
    )

    st.subheader("Offerings & Accounting Boundaries")
    st.markdown(
        "- **Primary Offering (Baseline Modeled):** Roof Inspection ($35 baseline)\n"
        "- **Secondary Offerings (Planned Stage 2 allocation):** Solar-Panel Inspection, Site Progress Survey\n"
        "- **Accounting Rules Enforced:** Equipment ($4,200) and additional capex reduce cash and increase assets without double-counting as monthly operating expenses. Loans increase cash and debt, never sales revenue."
    )

# ---------------------------------------------------------------------------
# TAB 2: INPUTS & FUNDING
# ---------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Startup Financing & Opening Balance Sheet")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Owner Contribution", f"${OWNER_CONTRIBUTION:,.2f}")
    b2.metric("Equipment Assets", f"${money(state['equipment_assets']):,.2f}")
    b3.metric("Pre-Opening Setup Expense", f"${PRE_OPENING_EXPENSE:,.2f}")
    b4.metric("Retained Earnings", f"${money(state['retained_earnings']):,.2f}")

    st.divider()
    st.subheader("Editable Operational & Cost Parameters (Normal Mode)")
    col_a, col_b = st.columns(2)
    with col_a:
        p_in = st.number_input("Base Price ($ / inspection)", min_value=1.0, value=float(params["base_price"]), step=1.0)
        d0_in = st.number_input("Baseline Demand D0 (inspections/mo)", min_value=0, value=int(params["D0"]), step=1)
        staff_in = st.number_input("Staff Hours / Month", min_value=0.0, value=float(params["staff_hours"]), step=2.0)
        hrs_unit_in = st.number_input("Hours per Inspection", min_value=0.1, value=float(params["hours_per_unit"]), step=0.5)
        slots_in = st.number_input("Equipment Slots / Month", min_value=0, value=int(params["equipment_slots"]), step=1)
        flight_min_in = st.number_input("Flight Minutes / Job", min_value=1.0, value=float(params["flight_minutes_per_job"]), step=1.0)
        batt_min_in = st.number_input("Battery Minutes Available / Month", min_value=0.0, value=float(params["battery_minutes_available"]), step=20.0)

    with col_b:
        st.markdown("**Variable Costs per Completed Inspection ($/unit)**")
        v_edited = {}
        for k, val in params["var_costs"].items():
            v_edited[k] = str(money(st.number_input(f"Variable: {k}", min_value=0.0, value=float(val), step=0.5)))

        st.markdown("**Monthly Fixed Costs ($/month)**")
        f_edited = {}
        for k, val in params["fixed_costs"].items():
            f_edited[k] = str(money(st.number_input(f"Fixed: {k}", min_value=0.0, value=float(val), step=10.0)))

    if st.button("Save Parameter Changes"):
        params["base_price"] = str(money(p_in))
        params["D0"] = int(d0_in)
        params["staff_hours"] = float(staff_in)
        params["hours_per_unit"] = float(hrs_unit_in)
        params["equipment_slots"] = int(slots_in)
        params["flight_minutes_per_job"] = float(flight_min_in)
        params["battery_minutes_available"] = float(batt_min_in)
        params["var_costs"] = v_edited
        params["fixed_costs"] = f_edited
        st.success("Parameters updated.")
        st.rerun()

# ---------------------------------------------------------------------------
# TAB 3: MATH SKILLS (AP CALCULUS ADAPTER)
# ---------------------------------------------------------------------------
with tabs[2]:
    lvl = state["selected_level"]
    D0 = float(params["D0"])
    p0 = float(params["base_price"])
    v = float(sum(money(x) for x in params["var_costs"].values()))
    F = float(sum(money(x) for x in params["fixed_costs"].values()))
    cap = compute_normal_capacity(params)["capacity"]

    a = 2.0 * D0
    b = D0 / p0 if p0 > 0 else 1.4286
    p_max = 2.0 * p0

    st.subheader(f"AP Calculus Panel — {lvl} Level (AER-3)")
    st.markdown(
        f"**Continuous Model Assumptions (Separate from Integer Ledger):**  \n"
        f"- Linear demand curve: $q(p) = a - b p = {a:.2f} - {b:.4f}p$ on domain $0 \le p \le {p_max:.2f}$ (USD/inspection)  \n"
        f"- Variable cost $v = \${v:.2f}$/inspection | Fixed cost $F = \${F:.2f}$/month | Capacity $= {cap}$ inspections/month"
    )

    p_grid = np.linspace(0, p_max, 300)
    q_unconstrained = np.maximum(0.0, a - b * p_grid)

    if lvl == "Foundation":
        st.markdown(
            "**Foundation Task:** Derive unconstrained profit $P(p) = (p - v)(a - bp) - F$ and its derivative "
            "$P'(p) = a + bv - 2bp$ (units: dollars per dollar of price). Find the critical point and check endpoints."
        )
        p_crit = (a + b * v) / (2.0 * b)
        profit_crit = (p_crit - v) * (a - b * p_crit) - F
        profit_0 = (0 - v) * (a - 0) - F
        profit_max_p = (p_max - v) * 0.0 - F

        m1, m2, m3 = st.columns(3)
        m1.metric("Critical Price p*", f"${p_crit:.2f}", "Where P'(p) = 0")
        m2.metric("Unconstrained Max Profit", f"${profit_crit:,.2f}", f"At q(p*) = {a - b * p_crit:.1f} units")
        m3.metric("Endpoint Profits P(0) / P(2p0)", f"${profit_0:,.0f} / ${profit_max_p:,.0f}")

        P_vals = (p_grid - v) * (a - b * p_grid) - F
        dP_vals = a + b * v - 2.0 * b * p_grid

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Unconstrained Profit P(p) ($)", "Marginal Profit w.r.t. Price P'(p) ($ per $/unit)"))
        fig.add_trace(go.Scatter(x=p_grid, y=P_vals, name="P(p)", line=dict(color="#1f77b4", width=3)), row=1, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
        fig.add_vline(x=p_crit, line_dash="dot", line_color="#d95f02", annotation_text=f"p*=${p_crit:.2f}", row=1, col=1)

        fig.add_trace(go.Scatter(x=p_grid, y=dP_vals, name="P'(p)", line=dict(color="#2ca02c", width=3)), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
        fig.update_xaxes(title_text="Price p ($ / inspection)", row=2, col=1)
        fig.update_layout(height=540)
        st.plotly_chart(fig, use_container_width=True)

        st.info("**Interpretation Prompt:** What are the units of $P'(p)$, and why might the unconstrained critical price $p^*$ be impossible to fulfill when monthly capacity is 40 inspections?")

    elif lvl == "Applied":
        p_corner = max(0.0, (a - cap) / b)
        p_crit_unc = (a + b * v) / (2.0 * b)
        st.markdown(
            f"**Applied Task:** Enforce capacity $s(p) = \min({cap}, \max(0, q(p)))$.  \n"
            f"- For $p < {p_corner:.2f}$ (capacity-capped branch): $s(p) = {cap}$, so $P(p) = {cap}(p - {v:.2f}) - {F:.2f}$ and $P'(p) = {cap}$ ($/dollar).  \n"
            f"- For $p > {p_corner:.2f}$ (demand-limited branch): $s(p) = a - bp$, so $P'(p) = a + bv - 2bp$.  \n"
            f"- At the corner $p = \${p_corner:.2f}$, $P'(p)$ is **undefined** (left derivative ${cap}$ != right derivative {a + b*v - 2*b*p_corner:.2f})."
        )
        s_vals = np.minimum(cap, q_unconstrained)
        P_constrained = (p_grid - v) * s_vals - F
        dP_left = np.where(p_grid < p_corner, float(cap), np.nan)
        dP_right = np.where(p_grid > p_corner, a + b * v - 2.0 * b * p_grid, np.nan)

        opt_idx = int(np.argmax(P_constrained))
        p_opt = p_grid[opt_idx]
        prof_opt = P_constrained[opt_idx]
        c1, c2, c3 = st.columns(3)
        c1.metric("Capacity Corner Price", f"${p_corner:.2f}", f"Where q(p) = {cap}")
        c2.metric("Unconstrained Critical Point", f"${p_crit_unc:.2f}", "Infeasible if < corner")
        c3.metric("Constrained Optimum Profit", f"${prof_opt:,.2f}", f"At p = ${p_opt:.2f}")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Constrained Piecewise Profit P(p) ($)", "Derivative P'(p) with Undefined Corner"))
        fig.add_trace(go.Scatter(x=p_grid, y=P_constrained, name="Constrained P(p)", line=dict(color="#1f77b4", width=3)), row=1, col=1)
        fig.add_vline(x=p_corner, line_dash="dot", line_color="#d95f02", annotation_text=f"Corner ${p_corner:.2f}", row=1, col=1)
        fig.add_trace(go.Scatter(x=p_grid, y=dP_left, name="P'(p) left (cap)", line=dict(color="#2ca02c", width=3)), row=2, col=1)
        fig.add_trace(go.Scatter(x=p_grid, y=dP_right, name="P'(p) right (demand)", line=dict(color="#7570b3", width=3)), row=2, col=1)
        fig.add_trace(
            go.Scatter(
                x=[p_corner, p_corner],
                y=[cap, a + b * v - 2.0 * b * p_corner],
                mode="markers",
                name="Undefined Corner",
                marker=dict(size=10, color="white", line=dict(width=2, color="#d95f02")),
            ),
            row=2,
            col=1,
        )
        fig.update_layout(height=540)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.markdown(
            "**Advanced Task (Accumulation Rate & Sensitivity):** Separate isolated campaign rate integration over $0 \le t \le 10$ days "
            "(does not overwrite the monthly ledger):  \n"
            "- Revenue rate: $r(t) = 100 + 20t$ ($/day) $\implies \int_0^{10} (100 + 20t)\,dt = \$2,000.00$  \n"
            "- Cost rate: $c(t) = 60 + 5t$ ($/day) $\implies \int_0^{10} (60 + 5t)\,dt = \$850.00$  \n"
            "- Net accumulated campaign profit: $\int_0^{10} [r(t) - c(t)]\,dt = \$1,150.00$"
        )
        t_horizon = st.slider("Integration Upper Limit T (days)", min_value=1, max_value=10, value=10)
        t_grid = np.linspace(0, t_horizon, 100)
        acc_rev = 100.0 * t_horizon + 10.0 * (t_horizon ** 2)
        acc_cost = 60.0 * t_horizon + 2.5 * (t_horizon ** 2)
        acc_net = acc_rev - acc_cost

        a1, a2, a3 = st.columns(3)
        a1.metric(f"Accumulated Revenue [0, {t_horizon}]", f"${acc_rev:,.2f}", "dollars")
        a2.metric(f"Accumulated Cost [0, {t_horizon}]", f"${acc_cost:,.2f}", "dollars")
        a3.metric(f"Net Accumulated Profit [0, {t_horizon}]", f"${acc_net:,.2f}", "dollars")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_grid, y=100 + 20 * t_grid, name="r(t) = 100 + 20t ($/day)", fill="tozeroy"))
        fig.add_trace(go.Scatter(x=t_grid, y=60 + 5 * t_grid, name="c(t) = 60 + 5t ($/day)", fill="tozeroy"))
        fig.update_layout(title=f"Accumulated Revenue vs. Cost Rates (0 <= t <= {t_horizon} days)", xaxis_title="Day t", yaxis_title="Dollars / Day")
        st.plotly_chart(fig, use_container_width=True)

        st.info("**Advanced Sensitivity & Limitation Prompt:** How do the units change from $r(t)$ ($/day) to $\int_0^{10} r(t)\,dt$ ($), and why would extrapolating this linear growth rate indefinitely violate AER-3 drone/battery capacity?")

    # Linked Price-Volume Table
    sample_prices = [20, 25, 30, 35, 40, 45, 50, 60]
    rows = []
    for sp in sample_prices:
        q_cont = max(0.0, a - b * sp)
        s_int = min(cap, math.floor(q_cont))
        rev_int = s_int * sp
        cost_int = F + v * s_int
        rows.append(
            {
                "Price ($)": sp,
                "Continuous Demand q(p)": round(q_cont, 2),
                "Feasible Integer Sales": s_int,
                "Simulated Revenue ($)": round(rev_int, 2),
                "Simulated Total Cost ($)": round(cost_int, 2),
                "Simulated Operating Profit ($)": round(rev_int - cost_int, 2),
            }
        )
    st.subheader("Linked Price-Volume Table (Continuous vs. Integer Sales)")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 4: OPERATIONS & LEDGER RUN
# ---------------------------------------------------------------------------
with tabs[3]:
    cap_info = compute_normal_capacity(params)
    st.subheader("Operations Capacity & Bottleneck Check (Normal Mode)")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Staff Capacity", f"{cap_info['staff_cap']} jobs", f"{params['staff_hours']}h / {params['hours_per_unit']}h")
    o2.metric("Equipment Slots", f"{cap_info['equip_cap']} jobs")
    o3.metric("Battery Capacity", f"{cap_info['batt_cap']} jobs", f"{params['battery_minutes_available']}m / {params['flight_minutes_per_job']}m")
    o4.metric("Effective Capacity", f"{cap_info['capacity']} jobs", f"Bottleneck: {cap_info['bottleneck']}")

    st.divider()
    st.subheader("Advance Simulation One Period (Record Transaction)")
    with st.form("advance_period_form"):
        fc1, fc2, fc3 = st.columns(3)
        run_id_in = fc1.text_input("Unique Run ID", value=f"RUN-{state['state_version']:03d}")
        sim_date_in = fc2.text_input("Period End Date (YYYY-MM-DD)", value="2027-01-31")
        req_in = fc3.number_input("Requested Inspections", min_value=0, value=int(params["D0"]), step=1)

        fc4, fc5, fc6 = st.columns(3)
        price_run = fc4.number_input("Unit Price ($)", min_value=1.0, value=float(params["base_price"]), step=1.0)
        ad_run = fc5.number_input("Approved Own-Business Ad Expense ($)", min_value=0.0, value=0.0, step=25.0)
        capex_run = fc6.number_input("Approved Equipment Capex ($)", min_value=0.0, value=0.0, step=100.0)

        submitted = st.form_submit_button("Approve & Advance Simulation Once")
        if submitted:
            ok, msg = simulate_period(
                state=state,
                sim_date=sim_date_in,
                run_id=run_id_in.strip(),
                requested=int(req_in),
                price=money(price_run),
                ad_cost=money(ad_run),
                additional_capex=money(capex_run),
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.subheader("Dated Event Ledger")
    if state["ledger"]:
        df_ledger = pd.DataFrame(state["ledger"])
        st.dataframe(df_ledger, use_container_width=True)
        st.download_button(
            "Download Ledger CSV",
            data=df_ledger.to_csv(index=False),
            file_name=f"{state['team_id']}_ledger_v{state['state_version']}.csv",
            mime="text/csv",
        )
    else:
        st.info("No transactions recorded yet. Submit a period above or run the fixture test in Tab 5.")

# ---------------------------------------------------------------------------
# TAB 5: FIXTURE & ACCEPTANCE TESTS
# ---------------------------------------------------------------------------
with tabs[4]:
    st.subheader("AER Package Acceptance Tests & Monthly Fixture Replay")
    st.warning(
        "Fixture Mode deliberately uses `capacity_override` from `sample_data/monthly_fixture.csv` to verify ledger math. "
        "Do not mix fixture runs with normal-mode runs."
    )

    if st.button("Reset & Replay 3-Month AER Fixture (2027-01 to 2027-03)"):
        tid = state["team_id"]
        lvl = state["selected_level"]
        fresh = default_state()
        fresh["team_id"] = tid
        fresh["selected_level"] = lvl
        fresh["snapshot_id"] = f"SNAP-{tid}-v1"
        fixture_rows = [
            ("FIX-2027-01", "2027-01-31", 50, 40, Decimal("0.00")),
            ("FIX-2027-02", "2027-02-28", 55, 40, Decimal("100.00")),
            ("FIX-2027-03", "2027-03-31", 45, 30, Decimal("0.00")),
        ]
        for rid, dt, req, cap_ov, ad in fixture_rows:
            simulate_period(
                state=fresh,
                sim_date=dt,
                run_id=rid,
                requested=req,
                price=Decimal("35.00"),
                ad_cost=ad,
                capacity_override=cap_ov,
            )
        st.session_state.sim_state = fresh
        st.success("Replayed 3-month fixture cleanly! Check results below against handbook expected values.")
        st.rerun()

    expected_df = pd.DataFrame(
        [
            {"Month": "2027-01", "Expected Sold": 40, "Expected Revenue": "$1,400.00", "Expected Expense": "$900.00", "Expected Profit": "$500.00", "Expected Closing Cash": "$3,500.00"},
            {"Month": "2027-02", "Expected Sold": 40, "Expected Revenue": "$1,400.00", "Expected Expense": "$1,000.00", "Expected Profit": "$400.00", "Expected Closing Cash": "$3,900.00"},
            {"Month": "2027-03", "Expected Sold": 30, "Expected Revenue": "$1,050.00", "Expected Expense": "$800.00", "Expected Profit": "$250.00", "Expected Closing Cash": "$4,150.00"},
        ]
    )
    st.markdown("**Handbook Expected Fixture Results:**")
    st.dataframe(expected_df, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 6: PLANNED MODULES
# ---------------------------------------------------------------------------
with tabs[5]:
    st.subheader("Roadmap Status (Honest Stage 1 Disclosure)")
    st.markdown(
        "- **Stage 1 (Active Now):** Inputs & Funding, AP Calculus Math Skills Panel, Capacity & Bottleneck Engine, Dated Ledger, JSON Snapshot Export/Import with Stale-Version & Team-ID Rejection, and AER Fixture Replay.\n"
        "- **Stage 2 (Planned):** Full Report Center (Income Statement, Cash Flow, Budget Variance, Balance Sheet PDF/CSV), Costed Marketing Studio with A/B Variants, and Structured AI Role Handoff Cards.\n"
        "- **Stage 3 (Planned):** Frozen-Snapshot Practice Assessment Generator & Cross-Course Evidence Artifacts.\n"
        "- **Stage 4 (Optional):** Demonstration Storefront with test checkout tokens."
    )

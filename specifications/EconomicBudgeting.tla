------------------------- MODULE EconomicBudgeting -------------------------
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS 
    Agents,
    MaxBudget

VARIABLES
    ledger_spent,
    agent_state

vars == << ledger_spent, agent_state >>

Init ==
    /\ ledger_spent = 0
    /\ agent_state = [a \in Agents |-> "idle"]

(* Action: An agent tries to perform an action that costs tokens *)
PerformAction(a, cost) ==
    /\ agent_state[a] \in {"idle", "running"}
    /\ ledger_spent + cost <= MaxBudget
    /\ ledger_spent' = ledger_spent + cost
    /\ agent_state' = [agent_state EXCEPT ![a] = "running"]

(* Action: Budget Guard kicks in when threshold is reached *)
HaltExecution(a, cost) ==
    /\ ledger_spent + cost > MaxBudget
    /\ agent_state' = [agent_state EXCEPT ![a] = "halted_budget_exceeded"]
    /\ UNCHANGED ledger_spent

Next == \E a \in Agents, cost \in {10, 50, 100}:
            \/ PerformAction(a, cost)
            \/ HaltExecution(a, cost)

\* Invariant: Ensure that the spent budget mathematically cannot exceed the MaxBudget
NoBudgetOverrun ==
    ledger_spent <= MaxBudget

Spec == Init /\ [][Next]_vars
=============================================================================

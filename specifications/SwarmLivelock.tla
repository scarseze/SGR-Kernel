----------------------- MODULE SwarmLivelock -----------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS 
    Agents,                \* Set of all agents in the swarm
    MaxTurnsPerAgent,      \* Maximum local turns an agent can take (e.g. 10)
    MaxGlobalTransfers     \* Maximum horizontal handoffs allowed in the session (e.g. 15)

VARIABLES 
    current_agent,         \* The active agent running the conversation loop
    status,                \* "RUNNING", "COMPLETED" (or "FAILED_LIMIT" if bounds exceeded)
    global_transfers,      \* Counter mapping for total transfers
    local_turns            \* Counter for the local LLM loop turns of the current agent

vars == << current_agent, status, global_transfers, local_turns >>

(* Assume some arbitrary entry agent *)
Init == 
    /\ current_agent = CHOOSE a \in Agents : TRUE
    /\ status = "RUNNING"
    /\ global_transfers = 0
    /\ local_turns = 0

(* Action: Agent successfully answers the user and ends the swarm execution *)
CompleteTask ==
    /\ status = "RUNNING"
    /\ status' = "COMPLETED"
    /\ UNCHANGED <<current_agent, global_transfers, local_turns>>

(* Action: Agent runs another LLM turn internally (e.g. Tool Call) *)
InternalTurn ==
    /\ status = "RUNNING"
    /\ local_turns < MaxTurnsPerAgent
    /\ local_turns' = local_turns + 1
    /\ UNCHANGED <<current_agent, status, global_transfers>>

(* Action: Agent decides to transfer to another agent *)
TransferToAgent ==
    /\ status = "RUNNING"
    /\ global_transfers < MaxGlobalTransfers
    /\ \E next_agent \in Agents:
          /\ current_agent' = next_agent
          /\ global_transfers' = global_transfers + 1
          /\ local_turns' = 0
          /\ UNCHANGED status

(* Enforce system limit bounds explicitly via fallback fail *)
FailOnLimit ==
    /\ status = "RUNNING"
    /\ (local_turns >= MaxTurnsPerAgent \/ global_transfers >= MaxGlobalTransfers)
    /\ status' = "FAILED_LIMIT"
    /\ UNCHANGED <<current_agent, global_transfers, local_turns>>

Terminated ==
    /\ status \in {"COMPLETED", "FAILED_LIMIT"}
    /\ UNCHANGED vars

Next == 
    \/ CompleteTask
    \/ InternalTurn
    \/ TransferToAgent
    \/ FailOnLimit
    \/ Terminated

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(* INVARIANT: Bounded Execution *)
(* The execution never exceeds the max global transfers or local turns without failure *)
BoundedExecution ==
    /\ global_transfers <= MaxGlobalTransfers
    /\ local_turns <= MaxTurnsPerAgent

(* LIVENESS: Eventual Progress (Termination) *)
(* Every execution eventually terminates, preventing infinite swarm livelock loops. *)
EventualTermination ==
    <> (status \in {"COMPLETED", "FAILED_LIMIT"})

=============================================================================

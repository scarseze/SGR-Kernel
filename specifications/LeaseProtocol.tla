--------------------------- MODULE LeaseProtocol ---------------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

(* Model parameters *)
CONSTANTS 
    Workers,     \* Set of worker identifiers
    MaxLease     \* Maximum version limit to enforce bounded model checking

VARIABLES 
    db_state,      \* State of the job in DB: "CREATED", "QUEUED", "RUNNING", "COMPLETED"
    db_lease_ver,  \* The current lease version in DB
    worker_state,  \* State of each worker: "IDLE", "WORKING", "CRASHED"
    worker_lease   \* The lease version held by each worker

vars == << db_state, db_lease_ver, worker_state, worker_lease >>

(* Initial State *)
Init == 
    /\ db_state = "CREATED"
    /\ db_lease_ver = 0
    /\ worker_state = [w \in Workers |-> "IDLE"]
    /\ worker_lease = [w \in Workers |-> 0]

(* Action: Reconciler puts a CREATED or expired task into the queue *)
Requeue ==
    /\ \/ db_state = "CREATED"
       \/ db_state = "RUNNING" \* Simulating lease timeout: the Reconciler can always reclaim a RUNNING lease
    /\ db_lease_ver < MaxLease  \* Bounding for TLC
    /\ db_state' = "QUEUED"
    /\ UNCHANGED <<db_lease_ver, worker_state, worker_lease>>

(* Action: A worker picks up a queued task (Acquire Lease via CAS) *)
AcquireLease(w) ==
    /\ db_state = "QUEUED"
    /\ worker_state[w] = "IDLE"
    /\ db_lease_ver' = db_lease_ver + 1
    /\ db_state' = "RUNNING"
    /\ worker_state' = [worker_state EXCEPT ![w] = "WORKING"]
    /\ worker_lease' = [worker_lease EXCEPT ![w] = db_lease_ver']

(* Action: A worker crashes while working *)
Crash(w) ==
    /\ worker_state[w] = "WORKING"
    /\ worker_state' = [worker_state EXCEPT ![w] = "CRASHED"]
    /\ UNCHANGED <<db_state, db_lease_ver, worker_lease>>

(* Action: A worker recovers from a crash *)
Recover(w) ==
    /\ worker_state[w] = "CRASHED"
    /\ worker_state' = [worker_state EXCEPT ![w] = "IDLE"]
    /\ UNCHANGED <<db_state, db_lease_ver, worker_lease>>

(* Action: A worker completes the task and commits if it still holds the valid lease *)
CompleteTask(w) ==
    /\ worker_state[w] = "WORKING"
    /\ IF worker_lease[w] = db_lease_ver
          THEN /\ db_state' = "COMPLETED"
               /\ worker_state' = [worker_state EXCEPT ![w] = "IDLE"]
               /\ UNCHANGED <<db_lease_ver, worker_lease>>
          ELSE /\ worker_state' = [worker_state EXCEPT ![w] = "IDLE"]
               /\ UNCHANGED <<db_state, db_lease_ver, worker_lease>>

(* Action: Terminal state stuttering to prevent deadlock *)
Terminated ==
    /\ (db_state = "COMPLETED" \/ db_lease_ver >= MaxLease)
    /\ UNCHANGED vars

(* State transitions *)
Next == 
    \/ Requeue
    \/ \E w \in Workers: AcquireLease(w)
    \/ \E w \in Workers: Crash(w)
    \/ \E w \in Workers: CompleteTask(w)
    \/ \E w \in Workers: Recover(w)
    \/ Terminated

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(* INVARIANT I1: Execution Exclusivity *)
(* It is never the case that two different workers are WORKING on the same valid lease *)
ExecutionExclusivity ==
    \A w1, w2 \in Workers :
        (w1 /= w2 /\ worker_state[w1] \in {"WORKING", "CRASHED"} /\ worker_state[w2] \in {"WORKING", "CRASHED"})
        => worker_lease[w1] /= worker_lease[w2]

(* LIVENESS: At-Least-Once Delivery *)
(* If we don't hit the bound, the job will eventually be completed *)
EventualCompletion ==
    <> (db_state = "COMPLETED" \/ db_lease_ver >= MaxLease)

=============================================================================

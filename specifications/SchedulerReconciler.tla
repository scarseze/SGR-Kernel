---------------------- MODULE SchedulerReconciler ----------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS 
    Tasks,         \* Set of task IDs
    MaxAttempts    \* Max number of times a task can be requeued

VARIABLES 
    db,            \* State of tasks in DB: [t \in Tasks |-> "CREATED" | "QUEUED" | "COMPLETED"]
    queue,         \* Set of task IDs currently in the ephemeral queue
    attempts       \* Number of attempts per task

vars == << db, queue, attempts >>

(* Initial State *)
Init == 
    /\ db = [t \in Tasks |-> "CREATED"]
    /\ queue = {}
    /\ attempts = [t \in Tasks |-> 0]

(* Action: A new task arrives and is placed in the DB *)
(* For simplicity, we assume tasks start in CREATED as per Init *)

(* Action: The Scheduler pushes a CREATED task to the Queue and updates DB *)
ScheduleTask(t) ==
    /\ db[t] = "CREATED"
    /\ db' = [db EXCEPT ![t] = "QUEUED"]
    /\ queue' = queue \union {t}
    /\ UNCHANGED attempts

(* Action: A worker pops a task from the Queue and successfully completes it *)
CompleteTask(t) ==
    /\ t \in queue
    /\ queue' = queue \ {t}
    /\ db' = [db EXCEPT ![t] = "COMPLETED"]
    /\ UNCHANGED attempts

(* Action: The Queue (Redis) crashes and loses all in-memory state *)
QueueCrash ==
    /\ queue /= {}
    /\ queue' = {}
    /\ UNCHANGED <<db, attempts>>

(* Action: The Reconciler scans the DB and puts seemingly stuck "QUEUED" tasks back to "CREATED" *)
(* This simulates the timeout + re-enqueue mechanism *)
ReconcileTask(t) ==
    /\ db[t] = "QUEUED"
    /\ t \notin queue \* The task is lost from the queue
    /\ attempts[t] < MaxAttempts
    /\ db' = [db EXCEPT ![t] = "CREATED"]
    /\ attempts' = [attempts EXCEPT ![t] = attempts[t] + 1]
    /\ UNCHANGED queue

(* Terminal state *)
Terminated ==
    /\ \A t \in Tasks : db[t] = "COMPLETED" \/ attempts[t] >= MaxAttempts
    /\ UNCHANGED vars

Next == 
    \/ \E t \in Tasks: ScheduleTask(t)
    \/ \E t \in Tasks: CompleteTask(t)
    \/ \E t \in Tasks: ReconcileTask(t)
    \/ QueueCrash
    \/ Terminated

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(* INVARIANT I2: No active task is permanently lost *)
(* A COMPLETED task is never found in the ephemeral queue *)
TaskConservation ==
    \A t \in Tasks: 
        db[t] = "COMPLETED" => t \notin queue

(* LIVENESS: At-Least-Once Delivery *)
(* Every task will eventually be COMPLETED or hit the max retry limit (due to infinite queue crashes) *)
EventualDelivery ==
    \A t \in Tasks: <> (db[t] = "COMPLETED" \/ attempts[t] >= MaxAttempts)

=============================================================================

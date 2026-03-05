---- MODULE LeaseProtocol_TTrace_1772735047 ----
EXTENDS Sequences, TLCExt, LeaseProtocol, Toolbox, Naturals, TLC, LeaseProtocol_TEConstants

_expression ==
    LET LeaseProtocol_TEExpression == INSTANCE LeaseProtocol_TEExpression
    IN LeaseProtocol_TEExpression!expression
----

_trace ==
    LET LeaseProtocol_TETrace == INSTANCE LeaseProtocol_TETrace
    IN LeaseProtocol_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        db_lease_ver = (5)
        /\
        worker_state = ((w1 :> "IDLE" @@ w2 :> "IDLE" @@ w3 :> "IDLE"))
        /\
        worker_lease = ((w1 :> 4 @@ w2 :> 5 @@ w3 :> 3))
        /\
        db_state = ("RUNNING")
    )
----

_init ==
    /\ db_lease_ver = _TETrace[1].db_lease_ver
    /\ worker_lease = _TETrace[1].worker_lease
    /\ worker_state = _TETrace[1].worker_state
    /\ db_state = _TETrace[1].db_state
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ db_lease_ver  = _TETrace[i].db_lease_ver
        /\ db_lease_ver' = _TETrace[j].db_lease_ver
        /\ worker_lease  = _TETrace[i].worker_lease
        /\ worker_lease' = _TETrace[j].worker_lease
        /\ worker_state  = _TETrace[i].worker_state
        /\ worker_state' = _TETrace[j].worker_state
        /\ db_state  = _TETrace[i].db_state
        /\ db_state' = _TETrace[j].db_state

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("LeaseProtocol_TTrace_1772735047.json", _TETrace)

=============================================================================

 Note that you can extract this module `LeaseProtocol_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `LeaseProtocol_TEExpression.tla` file takes precedence 
  over the module `LeaseProtocol_TEExpression` below).

---- MODULE LeaseProtocol_TEExpression ----
EXTENDS Sequences, TLCExt, LeaseProtocol, Toolbox, Naturals, TLC, LeaseProtocol_TEConstants

expression == 
    [
        \* To hide variables of the `LeaseProtocol` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        db_lease_ver |-> db_lease_ver
        ,worker_lease |-> worker_lease
        ,worker_state |-> worker_state
        ,db_state |-> db_state
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_db_lease_verUnchanged |-> db_lease_ver = db_lease_ver'
        
        \* Format the `db_lease_ver` variable as Json value.
        \* ,_db_lease_verJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(db_lease_ver)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_db_lease_verModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].db_lease_ver # _TETrace[s-1].db_lease_ver
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE LeaseProtocol_TETrace ----
\*EXTENDS IOUtils, LeaseProtocol, TLC, LeaseProtocol_TEConstants
\*
\*trace == IODeserialize("LeaseProtocol_TTrace_1772735047.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE LeaseProtocol_TETrace ----
EXTENDS LeaseProtocol, TLC, LeaseProtocol_TEConstants

trace == 
    <<
    ([db_lease_ver |-> 0,worker_state |-> (w1 :> "IDLE" @@ w2 :> "IDLE" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 0 @@ w2 :> 0 @@ w3 :> 0),db_state |-> "CREATED"]),
    ([db_lease_ver |-> 0,worker_state |-> (w1 :> "IDLE" @@ w2 :> "IDLE" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 0 @@ w2 :> 0 @@ w3 :> 0),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 1,worker_state |-> (w1 :> "WORKING" @@ w2 :> "IDLE" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 1 @@ w2 :> 0 @@ w3 :> 0),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 1,worker_state |-> (w1 :> "WORKING" @@ w2 :> "IDLE" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 1 @@ w2 :> 0 @@ w3 :> 0),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 2,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 1 @@ w2 :> 2 @@ w3 :> 0),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 2,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 1 @@ w2 :> 2 @@ w3 :> 0),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 3,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 1 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 3,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 1 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 3,worker_state |-> (w1 :> "IDLE" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 1 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 4,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 4,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 4,worker_state |-> (w1 :> "WORKING" @@ w2 :> "IDLE" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 2 @@ w3 :> 3),db_state |-> "QUEUED"]),
    ([db_lease_ver |-> 5,worker_state |-> (w1 :> "WORKING" @@ w2 :> "WORKING" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 5 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 5,worker_state |-> (w1 :> "WORKING" @@ w2 :> "CRASHED" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 5 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 5,worker_state |-> (w1 :> "IDLE" @@ w2 :> "CRASHED" @@ w3 :> "WORKING"),worker_lease |-> (w1 :> 4 @@ w2 :> 5 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 5,worker_state |-> (w1 :> "IDLE" @@ w2 :> "CRASHED" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 4 @@ w2 :> 5 @@ w3 :> 3),db_state |-> "RUNNING"]),
    ([db_lease_ver |-> 5,worker_state |-> (w1 :> "IDLE" @@ w2 :> "IDLE" @@ w3 :> "IDLE"),worker_lease |-> (w1 :> 4 @@ w2 :> 5 @@ w3 :> 3),db_state |-> "RUNNING"])
    >>
----


=============================================================================

---- MODULE LeaseProtocol_TEConstants ----
EXTENDS LeaseProtocol

CONSTANTS w1, w2, w3

=============================================================================

---- CONFIG LeaseProtocol_TTrace_1772735047 ----
CONSTANTS
    Workers = { w1 , w2 , w3 }
    MaxLease = 5
    w3 = w3
    w2 = w2
    w1 = w1

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Thu Mar 05 21:24:08 MSK 2026
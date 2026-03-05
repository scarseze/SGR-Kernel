---- MODULE S3CommitProtocol_TTrace_1772735193 ----
EXTENDS S3CommitProtocol_TEConstants, Sequences, TLCExt, Toolbox, S3CommitProtocol, Naturals, TLC

_expression ==
    LET S3CommitProtocol_TEExpression == INSTANCE S3CommitProtocol_TEExpression
    IN S3CommitProtocol_TEExpression!expression
----

_trace ==
    LET S3CommitProtocol_TETrace == INSTANCE S3CommitProtocol_TETrace
    IN S3CommitProtocol_TETrace!trace
----

_prop ==
    ~(([]<>(
            s3_files = ({<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j1, 2, "data.bin">>, <<j2, 1, "data.bin">>, <<j2, 1, "_SUCCESS">>})
            /\
            consumer_reads = ((j1 :> "NONE" @@ j2 :> "VALID_DATA_READ"))
    ))/\([]<>(
            s3_files = ({<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j2, 1, "data.bin">>, <<j2, 1, "_SUCCESS">>})
            /\
            consumer_reads = ((j1 :> "NONE" @@ j2 :> "VALID_DATA_READ"))
    )))
----

_init ==
    /\ consumer_reads = _TETrace[1].consumer_reads
    /\ s3_files = _TETrace[1].s3_files
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
           \/ /\ i = _TTraceLassoEnd
              /\ j = _TTraceLassoStart
        /\ consumer_reads  = _TETrace[i].consumer_reads
        /\ consumer_reads' = _TETrace[j].consumer_reads
        /\ s3_files  = _TETrace[i].s3_files
        /\ s3_files' = _TETrace[j].s3_files

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("S3CommitProtocol_TTrace_1772735193.json", _TETrace)


_view ==
    <<consumer_reads, s3_files, IF TLCGet("level") = _TTraceLassoEnd + 1 THEN _TTraceLassoStart ELSE TLCGet("level")>>
=============================================================================

 Note that you can extract this module `S3CommitProtocol_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `S3CommitProtocol_TEExpression.tla` file takes precedence 
  over the module `S3CommitProtocol_TEExpression` below).

---- MODULE S3CommitProtocol_TEExpression ----
EXTENDS S3CommitProtocol_TEConstants, Sequences, TLCExt, Toolbox, S3CommitProtocol, Naturals, TLC

expression == 
    [
        \* To hide variables of the `S3CommitProtocol` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        consumer_reads |-> consumer_reads
        ,s3_files |-> s3_files
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_consumer_readsUnchanged |-> consumer_reads = consumer_reads'
        
        \* Format the `consumer_reads` variable as Json value.
        \* ,_consumer_readsJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(consumer_reads)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_consumer_readsModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].consumer_reads # _TETrace[s-1].consumer_reads
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE S3CommitProtocol_TETrace ----
\*EXTENDS S3CommitProtocol_TEConstants, IOUtils, S3CommitProtocol, TLC
\*
\*trace == IODeserialize("S3CommitProtocol_TTrace_1772735193.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE S3CommitProtocol_TETrace ----
EXTENDS S3CommitProtocol_TEConstants, S3CommitProtocol, TLC

trace == 
    <<
    ([s3_files |-> {},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "NONE")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "NONE")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "NONE")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j2, 1, "data.bin">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "NONE")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j2, 1, "data.bin">>, <<j2, 1, "_SUCCESS">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "NONE")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j2, 1, "data.bin">>, <<j2, 1, "_SUCCESS">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "VALID_DATA_READ")]),
    ([s3_files |-> {<<j1, 1, "data.bin">>, <<j1, 1, "_SUCCESS">>, <<j1, 2, "data.bin">>, <<j2, 1, "data.bin">>, <<j2, 1, "_SUCCESS">>},consumer_reads |-> (j1 :> "NONE" @@ j2 :> "VALID_DATA_READ")])
    >>
----


=============================================================================

---- MODULE S3CommitProtocol_TEConstants ----
EXTENDS S3CommitProtocol

CONSTANTS j1, j2, _TTraceLassoStart, _TTraceLassoEnd

=============================================================================

---- CONFIG S3CommitProtocol_TTrace_1772735193 ----
CONSTANTS
    Jobs = { j1 , j2 }
    MaxAttempts = 2
    j2 = j2
    j1 = j1
_TTraceLassoStart = 6
_TTraceLassoEnd = 7

PROPERTY
    _prop

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

VIEW
    _view

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Thu Mar 05 21:26:34 MSK 2026
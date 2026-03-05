----------------------- MODULE S3CommitProtocol -----------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS 
    Jobs,          \* Set of job IDs
    MaxAttempts    \* Max version attempts allowed to bound model checking

VARIABLES 
    s3_files,      \* Set of strings representing files currently in S3
    consumer_reads \* Set of string tuples representing what each job's consumer has successfully read

VAR_TUPLE == << s3_files, consumer_reads >>

(* Valid file paths in our model: *)
(* 1. "/job/v_n/data.bin" - The actual payload *)
(* 2. "/job/_SUCCESS" - The commit marker pointing to a specific version *)

(* Initial State *)
Init == 
    /\ s3_files = {}
    /\ consumer_reads = [j \in Jobs |-> "NONE"]

(* Actions *)

(* Action: A worker writes the payload for an attempt *)
WritePayload(j, attempt) ==
    /\ attempt \in 1..MaxAttempts
    /\ s3_files' = s3_files \union { <<j, attempt, "data.bin">> }
    /\ UNCHANGED consumer_reads

(* Action: A worker writes the commit marker pointing to its attempt ALONG WITH checksum *)
(* In real life, atomicity means _SUCCESS appears instantly. In S3, it's a PUT object. *)
WriteCommitMarker(j, attempt) ==
    /\ <<j, attempt, "data.bin">> \in s3_files
    \* Only one _SUCCESS marker allowed per job (CAS or overwrite semantics)
    \* S3 PUT is a destructive overwrite. If multiple workers write, the last one wins.
    /\ s3_files' = {f \in s3_files: f[3] /= "_SUCCESS" \/ f[1] /= j} \union { <<j, attempt, "_SUCCESS">> }
    /\ UNCHANGED consumer_reads

(* Action: A consumer tries to read the job output *)
(* It strictly checks for the _SUCCESS marker FIRST, then reads the data it points to. *)
ConsumerRead(j, attempt) ==
    /\ consumer_reads[j] = "NONE"
    /\ <<j, attempt, "_SUCCESS">> \in s3_files
    /\ <<j, attempt, "data.bin">> \in s3_files
    /\ consumer_reads' = [consumer_reads EXCEPT ![j] = "VALID_DATA_READ"]
    /\ UNCHANGED s3_files

(* Action: A consumer carelessly tries to read ANY data.bin it finds (Anti-pattern) *)
(* In our protocol, this is what we prevent by enforcing the _SUCCESS marker dependency. *)
BadConsumerRead(j, attempt) ==
    /\ consumer_reads[j] = "NONE"
    /\ <<j, attempt, "data.bin">> \in s3_files
    \* Doesn't wait for _SUCCESS
    /\ consumer_reads' = [consumer_reads EXCEPT ![j] = "INVALID_PARTIAL_READ"]
    /\ UNCHANGED s3_files

(* Action: Background GC cleans up old versions that are NOT pointed to by the current _SUCCESS marker *)
GarbageCollect ==
    \E j \in Jobs, attempt \in 1..MaxAttempts :
        /\ <<j, attempt, "data.bin">> \in s3_files
        /\ <<j, attempt, "_SUCCESS">> \notin s3_files
        /\ s3_files' = s3_files \ { <<j, attempt, "data.bin">> }
        /\ UNCHANGED consumer_reads

(* Terminal state stuttering *)
Terminated ==
    /\ \A j \in Jobs: consumer_reads[j] \in {"VALID_DATA_READ", "INVALID_PARTIAL_READ"}
    /\ UNCHANGED VAR_TUPLE

Next == 
    \/ \E j \in Jobs, a \in 1..MaxAttempts: WritePayload(j, a)
    \/ \E j \in Jobs, a \in 1..MaxAttempts: WriteCommitMarker(j, a)
    \/ \E j \in Jobs, a \in 1..MaxAttempts: ConsumerRead(j, a)
    \* NEGATIVE PROOF DOCUMENTATION: 
    \* If we uncomment the following line, TLC immediately finds a violation of AtomicVisibility:
    \* State 1: <Initial predicate>
    \* State 2: WritePayload(j1,1) -> data.bin written
    \* State 3: BadConsumerRead(j1,1) -> Reads data.bin before _SUCCESS, resulting in INVALID_PARTIAL_READ
    \* \/ \E j \in Jobs, a \in 1..MaxAttempts: BadConsumerRead(j, a)
    \/ GarbageCollect
    \/ Terminated

Spec == Init /\ [][Next]_VAR_TUPLE /\ WF_VAR_TUPLE(Next)

(* INVARIANT I4: Atomic Visibility / No Partial Reads *)
(* A consumer NEVER reads partial or uncommitted data *)
AtomicVisibility ==
    \A j \in Jobs: consumer_reads[j] /= "INVALID_PARTIAL_READ"



=============================================================================

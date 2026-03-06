----------------------- MODULE ModelHandoff -----------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS 
    Models,          \* Set of available model IDs (e.g., {"primary", "fallback", "secure_local"})
    MaxContextSizes  \* Function mapping Models -> Nat (their max context window)

VARIABLES 
    active_model,    \* The currently active model routing the request
    history_tokens,  \* The current assumed token length of the conversation history
    model_status     \* Function mapping Models -> {"up", "down"}

VAR_TUPLE == << active_model, history_tokens, model_status >>

\* Assume we always have at least one fallback that is "up"
AssumeFallbackExists == \E m \in Models: model_status[m] = "up"

Init == 
    /\ model_status = [m \in Models |-> "up"]
    /\ active_model \in Models
    /\ history_tokens = 0

\* Action: A node marks a model as down (e.g., API timeout)
MarkModelDown(m) ==
    /\ model_status[m] = "up"
    \* Don't allow marking the LAST model down, to keep the state space finite and realistic
    /\ Cardinality({mdl \in Models: model_status[mdl] = "up"}) > 1
    /\ model_status' = [model_status EXCEPT ![m] = "down"]
    /\ UNCHANGED <<active_model, history_tokens>>

\* Action: The ModelRouter swaps the active model
SwapModel ==
    /\ model_status[active_model] = "down"
    /\ \E new_m \in Models: 
        /\ model_status[new_m] = "up"
        /\ active_model' = new_m
        \* Context Dehydration: History must be shrunk if it exceeds the new model's max context
        /\ history_tokens' = IF history_tokens > MaxContextSizes[new_m] 
                             THEN MaxContextSizes[new_m] 
                             ELSE history_tokens
    /\ UNCHANGED <<model_status>>

\* Action: The conversation progresses naturally, increasing history tokens
ProgressConversation ==
    /\ model_status[active_model] = "up"
    /\ history_tokens' = history_tokens + 1000
    \* Dehydrate aggressively 
    /\ history_tokens' <= MaxContextSizes[active_model]
    /\ UNCHANGED <<active_model, model_status>>

Next ==
    \/ \E m \in Models: MarkModelDown(m)
    \/ SwapModel
    \/ ProgressConversation

Spec == Init /\ [][Next]_VAR_TUPLE /\ WF_VAR_TUPLE(Next)

\* -------------------------------------------------------------------------
\* INVARIANTS
\* -------------------------------------------------------------------------

\* INVARIANT: SeamlessHandoff
\* Whenever a model is active and "up", the current conversation history 
\* MUST NOT exceed that model's maximum allowed context size.
SeamlessHandoff ==
    model_status[active_model] = "up" => history_tokens <= MaxContextSizes[active_model]

=============================================================================

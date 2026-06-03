"""Generation primitives — features, contracts, and model registry for multi-modal generation.

This package is intentionally import-light.  Contract constants defined here
can be imported by executors and SDK code without pulling in backend
implementations or executor modules.
"""

#: Dictionary key used to store/retrieve a ``GenerationResult`` within an
#: executor's shared payload dict (e.g. in-process ``ExecutorRunRequest.out``
#: dictionaries or executor return values).  Defined here so that executors
#: and facade code can agree on the key without importing backend modules.
GENERATION_RESULT_KEY = "generation_result"

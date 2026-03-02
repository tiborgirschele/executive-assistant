from __future__ import annotations

REPAIR_RECIPES: dict[str, dict[str, object]] = {
    "renderer_template_swap": {
        "preconditions": ["known renderer config drift", "known-good template id available"],
        "typed_actions": ["read_signed_known_good_template_id", "validate_template_id", "retry_render_step"],
        "max_attempts": 1,
        "max_duration_ms": 4000,
        "idempotent": True,
        "breaker_side_effects": ["open optional-skill breaker after repeated deterministic failure"],
    },
    "renderer_text_only": {
        "preconditions": ["renderer unavailable or unsafe"],
        "typed_actions": ["force_plain_text_output", "suppress_render_step"],
        "max_attempts": 1,
        "max_duration_ms": 500,
        "idempotent": True,
        "breaker_side_effects": ["leave simplified message final for current session"],
    },
    "breaker_open_optional_skill": {
        "preconditions": ["deterministic optional-skill failure repeats"],
        "typed_actions": ["open_breaker_ttl", "skip_optional_skill_on_future_runs"],
        "max_attempts": 1,
        "max_duration_ms": 100,
        "idempotent": True,
        "breaker_side_effects": ["future runs skip broken optional skill until TTL expires"],
    },
}

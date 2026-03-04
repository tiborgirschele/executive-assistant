
from app.render_guard import classify_markupgo_error, known_good_template_ids

def test_render_guard_classifies_invalid_template():
    assert classify_markupgo_error("MarkupGo API HTTP 400 invalid template id") == "invalid_template_id"

def test_known_good_template_ids_is_a_list():
    ids = known_good_template_ids()
    assert isinstance(ids, list)

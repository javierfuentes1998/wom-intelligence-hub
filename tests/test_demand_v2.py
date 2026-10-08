from app.demand import contextual_state
def test_insufficient_history(): assert contextual_state(5,[4]*7)["state"]=="insufficient_data"
def test_red(): assert contextual_state(5,[10]*8)["state"]=="muy_mal"
def test_yellow(): assert contextual_state(8,[10]*8)["state"]=="regular"
def test_green(): assert contextual_state(10,[10]*8)["state"]=="bien"
def test_blue(): assert contextual_state(13,[10]*8)["state"]=="sobresaliente"
def test_context_means_monday_not_compared_to_friday():
    assert contextual_state(5,[5]*8)["state"]=="bien"

from app.services.leak import check_leak, content_words, hint_shape_ok

RUBRIC = [
    "A LEFT JOIN keeps every row from the left table",
    "Unmatched right-side columns are filled with NULL",
    "The ON clause decides which rows are paired together",
]
QUESTION = "Explain what a LEFT JOIN does."


def test_content_words_drops_stopwords_and_short_words():
    assert content_words("The cat is on the mat") == {"cat", "mat"}


def test_verbatim_key_point_leaks():
    hint = "Remember: a LEFT JOIN keeps every row from the left table."
    result = check_leak(hint, RUBRIC)
    assert result.leaked and "verbatim" in result.reason


def test_paraphrase_covering_most_of_a_point_leaks():
    hint = "Think about how every left table row is kept, with NULL filling unmatched columns."
    assert check_leak(hint, RUBRIC, exclude=QUESTION).leaked


def test_covering_much_of_whole_rubric_leaks_even_if_no_single_point_does():
    hint = "left table rows kept, unmatched columns NULL, ON clause decides"
    result = check_leak(hint, RUBRIC, exclude=QUESTION, point_threshold=0.99)
    assert result.leaked and "whole rubric" in result.reason


def test_reflective_question_does_not_leak():
    hint = "What happens to a row on one side when nothing on the other side matches it?"
    assert not check_leak(hint, RUBRIC, exclude=QUESTION).leaked


def test_repeating_the_question_is_not_a_leak():
    hint = "What does a LEFT JOIN do to the rows of the left table?"
    assert not check_leak(hint, ["A LEFT JOIN does rows left table"], exclude=hint).leaked


def test_scaffold_with_blanks_does_not_leak():
    hint = "Fill in: a LEFT JOIN returns all rows from ____, and where there is no match it gives ____."
    assert not check_leak(hint, RUBRIC, exclude=QUESTION).leaked


def test_empty_rubric_never_leaks():
    assert not check_leak("anything at all", []).leaked


def test_hint_shape():
    assert hint_shape_ok("What do you think?")
    assert hint_shape_ok("Fill in the blanks: ____.")
    assert not hint_shape_ok("")
    assert not hint_shape_ok("Why? And how?")
    assert not hint_shape_ok("x" * 800)

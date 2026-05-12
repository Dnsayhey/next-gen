"""errors.py unit tests"""

from nextgen.core.errors import describe_exception


class BlankMessageError(Exception):
    def __str__(self):
        return ""


class WhitespaceMessageError(Exception):
    def __str__(self):
        return " \n\t "


def test_describe_exception_uses_message_when_present():
    assert describe_exception(ValueError("bad input")) == "bad input"


def test_describe_exception_strips_surrounding_whitespace():
    assert describe_exception(ValueError("  bad input\n")) == "bad input"


def test_describe_exception_falls_back_to_class_name_for_blank_message():
    assert describe_exception(BlankMessageError()) == "BlankMessageError"


def test_describe_exception_falls_back_to_class_name_for_whitespace_message():
    assert describe_exception(WhitespaceMessageError()) == "WhitespaceMessageError"

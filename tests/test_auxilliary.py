"""Tests for hassfeld.auxilliary — pure utility functions."""

import pytest
from hassfeld.auxilliary import lists_have_same_values, str_to_bool


class TestStrToBool:
    """Tests for str_to_bool — string-to-bool conversion."""

    def test_true_values(self):
        for val in ["True", "true", "TRUE", "1", "t", "T", "y", "Y", "yes", "YES"]:
            assert str_to_bool(val) is True, f"'{val}' should be True"

    def test_false_values(self):
        for val in ["False", "false", "0", "f", "n", "no", "", "anything_else"]:
            assert str_to_bool(val) is False, f"'{val}' should be False"

    def test_empty_string(self):
        assert str_to_bool("") is False


class TestListsHaveSameValues:
    """Tests for lists_have_same_values — order-independent list comparison."""

    def test_identical_lists(self):
        assert lists_have_same_values(["a", "b"], ["a", "b"]) is True

    def test_same_values_different_order(self):
        assert lists_have_same_values(["b", "a"], ["a", "b"]) is True

    def test_different_values(self):
        assert lists_have_same_values(["a", "b"], ["a", "c"]) is False

    def test_different_lengths(self):
        assert lists_have_same_values(["a"], ["a", "b"]) is False

    def test_empty_lists(self):
        assert lists_have_same_values([], []) is True

    def test_one_empty_one_not(self):
        assert lists_have_same_values(["a"], []) is False

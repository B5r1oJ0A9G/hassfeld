"""Functions to help dealining with data"""


def str_to_bool(string):
    """Convert string to bolean"""
    return string.lower() in ["true", "1", "t", "y", "yes"]


def lists_have_same_values(lst1, lst2):
    """Compare two zones disregarding order"""
    return sorted(lst1) == sorted(lst2)

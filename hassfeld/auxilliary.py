"""Functions to help dealining with data"""

def str_to_bool(s):
    return s.lower() in ['true', '1', 't', 'y', 'yes' ]

def lists_have_same_values(l1, l2):
    """Compare two zones disregarding order"""
    return sorted(l1) == sorted(l2)

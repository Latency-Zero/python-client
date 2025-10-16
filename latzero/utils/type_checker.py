import pickle

def is_pickleable(obj):
    """Check if an object can be pickled."""
    try:
        pickle.dumps(obj)
        return True
    except Exception:
        return False

def preserve_type(obj):
    """Returns the object as is, since pickle preserves types."""
    return obj

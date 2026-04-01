"""Stub augmenters package.

Provide a `get_methods()` function that returns a list of available
augmentation method descriptors: (id, name, description).

When a real package is available, replace this module.
"""
from typing import List, Tuple


def get_methods(n: int = 12) -> List[Tuple[str, str, str]]:
    """Return a list of placeholder augmentation methods.

    Each item is a tuple: (id, display_name, description).
    """
    methods = []
    for i in range(1, n + 1):
        mid = f"method_{i}"
        name = f"Method {i}"
        descr = f"Placeholder augmentation method {i}"
        methods.append((mid, name, descr))
    return methods


def example_augmentation(image):
    """Example augmentation function signature.

    Real augmentations should accept an image (PIL / numpy) and return
    an augmented image. This stub simply returns the input.
    """
    return image

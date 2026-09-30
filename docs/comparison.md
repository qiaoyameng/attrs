# Comparison

By default, two instances of *attrs* classes are equal if they have the same type and all their fields are equal.
For that, *attrs* writes `__eq__` and `__ne__` methods for you.

Additionally, if you pass `order=True`, *attrs* will also create a complete set of ordering methods: `__le__`, `__lt__`, `__ge__`, and `__gt__`.

For equality, *attrs* will generate a statement comparing the types of both instances,
and then comparing each attribute in turn using `==`.

For order, *attrs* will:

- Check if the types of the instances you're comparing are equal,
- if so, create a tuple of all field values for each instance,
- and finally perform the desired comparison operation on those tuples.

(custom-comparison)=

## Customization

As with other features, you can exclude fields from being involved in comparison operations:

```{doctest}
>>> from attrs import define, field
>>> @define
... class C:
...     x: int
...     y: int = field(eq=False)

>>> C(1, 2) == C(1, 3)
True
```

Additionally you can also pass a *callable* instead of a bool to both *eq* and *order*.
It is then used as a key function like you may know from {func}`sorted`:

```{doctest}
>>> @define
... class S:
...     x: str = field(eq=str.lower)

>>> S("foo") == S("FOO")
True

>>> @define(order=True)
... class C:
...     x: str = field(order=int)

>>> C("10") > C("2")
True
```

This is especially useful when you have fields with objects that have atypical comparison properties.
Common examples of such objects are [NumPy arrays](https://github.com/python-attrs/attrs/issues/435).

To save you unnecessary boilerplate, *attrs* comes with the {func}`attrs.cmp_using` helper to create such functions.
For NumPy arrays it would look like this:

```python
import numpy


@define
class C:
    an_array = field(eq=attrs.cmp_using(eq=numpy.array_equal))
```

:::{warning}
Please note that *eq* and *order* are set *independently*, because *order* is `False` by default in {func}`~attrs.define` (but not in {func}`attr.s`).
You can set both at once by using the *cmp* argument that we've undeprecated just for this use-case.
:::

(cycle-safe-eq)=

## Cycle-Safe Equality

By default, the generated ``__eq__`` compares fields recursively, so instances
that contain reference cycles -- for example, the nodes of a doubly-linked
list -- can't be compared: the recursion never terminates and raises a
`RecursionError`.

Passing ``cycle_safe_eq=True`` to {func}`attrs.define` (or {func}`attr.s`)
opts into a cycle-safe ``__eq__``:

```{doctest}
>>> from attrs import define
>>> @define(cycle_safe_eq=True)
... class Node:
...     value: int
...     prev: "Node | None" = None
...     next: "Node | None" = None

>>> def make_ring(values):
...     nodes = [Node(v) for v in values]
...     for i, node in enumerate(nodes):
...         node.prev = nodes[(i - 1) % len(nodes)]
...         node.next = nodes[(i + 1) % len(nodes)]
...     return nodes

>>> make_ring([1, 2, 3]) == make_ring([1, 2, 3])
True
>>> make_ring([1, 2, 3]) == make_ring([1, 2, 4])
False
```

While comparing two instances, *attrs* remembers the pair of objects that are
currently being compared (keyed by *both* objects' identities, so the same
left-hand object compared against a different right-hand object is still a
new comparison). If the same pair is encountered again, the recursion stops
and that pair is considered equal.

The tracking state is kept per thread, is discarded as soon as the comparison
returns -- even if a field's ``__eq__`` raises an exception -- and never
leaks between threads. Field-level customization keeps working as usual:
fields with ``eq=False`` are ignored, *eq* key functions are applied, and
comparing against a different type still returns `NotImplemented`.

:::{warning}
Cycle-safe equality does **not** make cyclic instances hashable.
``__hash__`` is only generated under the usual conditions (see `hashing`):
for example, for frozen classes with ``eq=True``, or when explicitly
requested using *unsafe_hash*. Even then, the generated ``__hash__`` hashes
the same fields that ``__eq__`` compares, so hashing an instance whose
hashed fields form a cycle recurses forever, just like before. If you need
hashing on a cyclic class, exclude the cyclic fields from the hash (for
example, with ``field(hash=False)``) or write your own ``__hash__``.
:::

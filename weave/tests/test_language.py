# Tests interactions between language features.

import typing
import weave
from weave.language_features.tagging import tagged_value_type
from weave import box
from ..language_features.tagging import make_tag_getter_op, tag_store, tagged_value_type


def test_none():
    node = weave.save(None, "null")
    x = node + 1
    assert x.type == weave.types.NoneType()
    assert weave.use(x) == None


def test_list_none():
    node = weave.save([None, None], "null")
    x = node + 1
    assert x.type == weave.types.List(weave.types.NoneType())
    assert weave.use(x) == [None, None]


@weave.op(
    output_type=lambda input_types: tagged_value_type.TaggedValueType(
        weave.types.TypedDict({"a_tag": weave.types.Int()}),
        input_types["x"],
    )
)
def _test_op_tag_input(x: typing.Any, tag_val: int):
    x = box.box(x)
    tag_store.add_tags(x, {"a_tag": tag_val})
    return x


get_a_tag = make_tag_getter_op.make_tag_getter_op(
    "a_tag", weave.types.Int(), op_name="tag-a_tag"
)


def test_tagged_none():
    node = weave.save(None, "null")
    tagged_node = _test_op_tag_input(node, 1)
    assert tagged_node.type == tagged_value_type.TaggedValueType(
        weave.types.TypedDict({"a_tag": weave.types.Int()}), weave.types.NoneType()
    )
    assert weave.use(get_a_tag(tagged_node)) == 1


def test_pick_none():
    node = weave.save(None)
    assert node.type == weave.types.NoneType()
    assert weave.use(node["a"]) == None


def test_optional():
    node = weave.save([1, None])
    assert node[0].type == weave.types.optional(weave.types.Int())
    assert weave.use(node[0]) == 1
    assert node[1].type == weave.types.optional(weave.types.Int())
    assert weave.use(node[1]) == None


def test_out_of_bounds_tag_access():
    node = weave.save([1, 2])
    tagged = node._test_op_tag_input(1)
    assert weave.use(get_a_tag(tagged[0])) == 1
    assert weave.use(get_a_tag(tagged[2])) == None
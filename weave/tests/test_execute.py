from .. import api
from .. import weave_types as types
from .. import weave_internal
from .. import ops
from .. import execute
import shutil

execute_test_count_op_run_count = 0


@api.op(input_type={"x": types.Any()}, output_type=types.Number())
def execute_test_count_op(x):
    global execute_test_count_op_run_count
    execute_test_count_op_run_count += 1
    return len(x)


def test_local_file_pure_cached(cereal_csv):
    # local_path() is impure, but the operations thereafter are pure
    # this test confirms that pure ops that come after impure ops hit cache
    global execute_test_count_op_run_count
    execute_test_count_op_run_count = 0
    # We should only execute execute_test_count_op once.
    count1 = api.use(execute_test_count_op(ops.local_path(cereal_csv).readcsv()))
    count2 = api.use(execute_test_count_op(ops.local_path(cereal_csv).readcsv()))
    assert count1 == count2
    assert execute_test_count_op_run_count == 1


def test_execute_no_cache():
    nine = weave_internal.make_const_node(types.Number(), 9)
    res = execute.execute_nodes([nine + 3], no_cache=True)
    assert res == [12]
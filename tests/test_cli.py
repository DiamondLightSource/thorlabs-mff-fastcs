from fastcs.launch import get_controller_schema
from ruamel.yaml import YAML

from thorlabs_mff_fastcs.controllers import ThorlabsMFF


# Add test for schema changes (assess version changes)
def test_schema(data):
    ref_schema = YAML(typ="safe").load(data / "schema.json")
    target_schema = get_controller_schema(ThorlabsMFF)
    assert target_schema == ref_schema

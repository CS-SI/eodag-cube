import logging

from eodag_cube import eodag_cube

LOGGER = logging.getLogger(__name__)


def test_hello_world():
    output = eodag_cube.hello_world()
    LOGGER.info(output)
    assert output == "hello world!"

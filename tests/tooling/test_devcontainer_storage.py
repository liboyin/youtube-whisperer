"""Check statically that the dev container's Compose layers keep host data out of development runs.

The dev container has no Docker daemon, so these tests read the Compose files instead of rendering
them. They protect DESIGN decision D54: the default dev container replaces every production mount
list, and only the opt-in real-data layer brings the real media library back.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ROOT / 'docker-compose.cpu.yaml'
GPU = ROOT / 'docker-compose.yaml'
DEV = ROOT / '.devcontainer' / 'docker-compose.devcontainer.yaml'
REAL_DATA = ROOT / '.devcontainer' / 'real-data' / 'docker-compose.real-data.yaml'
DEV_PROJECT = 'youtube-whisperer-dev'
ASSETS_TARGET = '/workspaces/youtube-whisperer/assets'
PROFILE_TARGET = '/home/ubuntu/snap/firefox/common/.mozilla/firefox'


@dataclass(frozen=True)
class Tagged:
    """A Compose merge directive such as ``!override`` and the value that it applies to."""

    tag: str
    value: object


class ComposeLoader(yaml.SafeLoader):
    """A safe loader that keeps Compose's merge tags instead of rejecting them."""


def _construct_tagged(loader, node):
    """Wrap a tagged node's value so that a test can see which merge directive applies."""
    if isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node, deep=True)
    else:
        value = loader.construct_scalar(node)
    return Tagged(node.tag, value)


for _tag in ('!override', '!reset'):
    ComposeLoader.add_constructor(_tag, _construct_tagged)


def load(path):
    """Return a Compose file's content, with merge tags preserved as ``Tagged`` values."""
    return yaml.load(path.read_text(encoding='utf-8'), Loader=ComposeLoader)


def mounted_services():
    """Return the production services that mount any storage, by name."""
    services = load(PRODUCTION)['services']
    return {name for name, service in services.items() if service.get('volumes')}


def split_mount(mount):
    """Return the source and the target of a short-syntax mount.

    A source can be an interpolation such as ``${ASSETS_DIR:?message}``, whose own colon is not a
    separator.
    """
    if mount.startswith('${'):
        end = mount.index('}') + 1
        mount_source, rest = mount[:end], mount[end + 1:]
    else:
        mount_source, _, rest = mount.partition(':')
    return mount_source, rest.split(':')[0]


def source(mount):
    """Return the host side of a short-syntax mount."""
    return split_mount(mount)[0]


def test_compose_loader_preserves_merge_tags():
    """The loader keeps the directive, so a missing ``!override`` cannot pass as a plain list."""
    loaded = yaml.load('a: !override [x]\nb: [y]\nc: !reset null\n', Loader=ComposeLoader)
    assert loaded == {'a': Tagged('!override', ['x']), 'b': ['y'], 'c': Tagged('!reset', 'null')}


def test_production_defines_mounting_services():
    """The parametrized checks cover every production service: the API, the three workers and Redis."""
    assert mounted_services() == {'app', 'youtube_worker', 'whisper_worker', 'azure_worker', 'redis'}


@pytest.mark.parametrize('name', sorted(mounted_services()))
def test_dev_override_replaces_each_production_mount_list(name):
    """No production mount, including a host path set in .env, survives into the dev container."""
    dev = load(DEV)
    volumes = dev['services'][name]['volumes']
    assert isinstance(volumes, Tagged) and volumes.tag == '!override'
    for mount in volumes.value:
        assert source(mount).startswith('dev_'), mount
        assert source(mount) in dev['volumes'], mount


def test_dev_override_publishes_no_port_and_fixes_no_container_name():
    """The dev stack can run beside the production stack on one Docker daemon."""
    production = load(PRODUCTION)['services']
    dev = load(DEV)['services']
    assert dev['app']['ports'] == Tagged('!reset', [])
    for name, service in production.items():
        if 'container_name' in service:
            assert dev[name]['container_name'] == Tagged('!reset', 'null'), name


def test_dev_project_is_separate_and_production_keeps_its_default_project():
    """Dev volumes never alias the production queue, which stays in the directory-named project."""
    assert load(DEV)['name'] == DEV_PROJECT
    assert 'name' not in load(PRODUCTION)
    assert 'name' not in load(GPU)


def test_real_data_layer_requires_the_real_library_for_every_application_service():
    """The real-data layer fails without ASSETS_DIR instead of falling back to throwaway storage."""
    services = load(REAL_DATA)['services']
    assert set(services) == mounted_services() - {'redis'}
    for name, service in services.items():
        by_target = {split_mount(mount)[1]: mount for mount in service['volumes']}
        assert source(by_target[ASSETS_TARGET]).startswith('${ASSETS_DIR:?'), name
        assert by_target[PROFILE_TARGET].endswith(':ro'), name
        assert service['environment']['WHISPERER_REAL_DATA'] == '1', name


def test_real_data_layer_keeps_the_development_queue():
    """Opening the real-data configuration never attaches the development stack to the production queue."""
    assert 'redis' not in load(REAL_DATA)['services']

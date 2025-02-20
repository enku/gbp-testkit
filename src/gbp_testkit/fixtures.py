"""Fixtures"""

# pylint: disable=missing-docstring,cyclic-import
import datetime as dt
import importlib.metadata
import io
import itertools
import os
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any
from unittest import mock

import gentoo_build_publisher
import rich.console
from cryptography.fernet import Fernet
from django.test.client import Client
from gbpcli.gbp import GBP
from gbpcli.theme import DEFAULT_THEME
from gbpcli.types import Console
from gentoo_build_publisher.build_publisher import BuildPublisher
from gentoo_build_publisher.cli import apikey
from gentoo_build_publisher.jenkins import Jenkins
from gentoo_build_publisher.models import BuildLog, BuildModel
from gentoo_build_publisher.records import BuildRecord, RecordDB
from gentoo_build_publisher.settings import Settings
from gentoo_build_publisher.storage import Storage
from gentoo_build_publisher.types import ApiKey, Build
from gentoo_build_publisher.utils import time
from rich.theme import Theme
from unittest_fixtures import FixtureContext, Fixtures, fixture

from .factories import BuildFactory, BuildModelFactory, BuildPublisherFactory
from .helpers import MockJenkins, create_user_auth, test_gbp

COUNTER = 0
now = partial(dt.datetime.now, tz=dt.UTC)


@fixture()
def tmpdir(_options: None, _fixtures: Fixtures) -> FixtureContext[Path]:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@fixture("tmpdir")
def environ(
    options: dict[str, Any] | None, fixtures: Fixtures
) -> FixtureContext[dict[str, str]]:
    options = options or {}
    clear: bool = options.pop("environ_clear", False)

    mock_environ = {
        "BUILD_PUBLISHER_API_KEY_ENABLE": "no",
        "BUILD_PUBLISHER_API_KEY_KEY": Fernet.generate_key().decode("ascii"),
        "BUILD_PUBLISHER_JENKINS_BASE_URL": "https://jenkins.invalid/",
        "BUILD_PUBLISHER_RECORDS_BACKEND": "memory",
        "BUILD_PUBLISHER_STORAGE_PATH": str(fixtures.tmpdir / "root"),
        "BUILD_PUBLISHER_WORKER_BACKEND": "sync",
        "BUILD_PUBLISHER_WORKER_THREAD_WAIT": "yes",
        **options,
    }
    with mock.patch.dict(os.environ, mock_environ, clear=clear):
        yield mock_environ


@fixture("environ")
def settings(_options: None, _fixtures: Fixtures) -> Settings:
    return Settings.from_environ()


@fixture("environ")
def publisher(_o: None, _f: Fixtures) -> FixtureContext[BuildPublisher]:
    bp: BuildPublisher = BuildPublisherFactory()

    @contextmanager
    def pp(name: str) -> FixtureContext[None]:
        with mock.patch.object(
            gentoo_build_publisher.publisher, name, getattr(bp, name)
        ):
            yield

    with pp("jenkins"), pp("repo"), pp("storage"):
        yield bp


@fixture("publisher")
def gbp(options: dict[str, Any] | None, _fixtures: Fixtures) -> GBP:
    options = options or {}
    user = options.get("user", "test_user")

    return test_gbp(
        "http://gbp.invalid/", auth={"user": user, "api_key": create_user_auth(user)}
    )


@fixture()
def console(_options: None, _fixtures: Fixtures) -> FixtureContext[Console]:
    out = io.StringIO()
    err = io.StringIO()
    theme = Theme(DEFAULT_THEME)

    c = Console(
        out=rich.console.Console(
            file=out, width=88, theme=theme, highlight=False, record=True
        ),
        err=rich.console.Console(file=err, width=88, record=True),
    )
    yield c

    if "SAVE_VIRTUAL_CONSOLE" in os.environ:
        global COUNTER  # pylint: disable=global-statement

        COUNTER += 1
        filename = f"{COUNTER}.svg"
        c.out.save_svg(filename, title="Gentoo Build Publisher")


@fixture("publisher")
def api_keys(options: dict[str, Any] | None, fixtures: Fixtures) -> list[ApiKey]:
    options = options or {}
    names = options.get("api_key_names", ["test_api_key"])
    keys: list[ApiKey] = []

    for name in names:
        api_key = ApiKey(
            name=name, key=apikey.create_api_key(), created=time.localtime()
        )
        fixtures.publisher.repo.api_keys.save(api_key)
        keys.append(api_key)

    return keys


@fixture()
def records_db(options: dict[str, Any], _fixtures: Fixtures) -> RecordDB:
    [module] = importlib.metadata.entry_points(
        group="gentoo_build_publisher.records", name=options["records_backend"]
    )

    db: RecordDB = module.load().RecordDB()
    return db


@fixture()
def build_model(options: dict[str, Any] | None, _fixtures: Fixtures) -> BuildModel:
    options = options or {}
    built: dt.datetime = options.get("built") or now()
    submitted: dt.datetime = options.get("submitted") or now()
    completed: dt.datetime = options.get("completed") or now()

    bm: BuildModel = BuildModelFactory.create(
        submitted=submitted, completed=completed, built=built
    )
    return bm


@fixture("records_db", "build_model")
def record(options: dict[str, Any] | None, fixtures: Fixtures) -> BuildRecord:
    options = options or {}
    bm: BuildModel = fixtures.build_model
    db: RecordDB = fixtures.records_db

    if logs := options.get("logs"):
        BuildLog.objects.create(build_model=bm, logs=logs)

    return db.get(Build.from_id(str(fixtures.build_model)))


@fixture()
def clock(options: dt.datetime | None, _fixtures: Fixtures) -> dt.datetime:
    if options:
        return options
    return now()


@fixture("publisher")
def client(_options: None, _fixtures: Fixtures) -> Client:
    return Client()


@fixture()
def build(_options: None, _fixtures: Fixtures) -> Build:
    return BuildFactory()


@fixture()
def builds(
    options: dict[str, Any] | None, _fixtures: Fixtures
) -> dict[str, list[Build]] | list[Build]:
    options = options or {}
    machines = options.get("machines", ["babette"])
    end_date = options.get("end_time", now())
    num_days = options.get("num_days", 1)
    per_day = options.get("per_day", 1)
    builds_map = BuildFactory.buncha_builds(machines, end_date, num_days, per_day)

    if len(machines) == 1:
        return builds_map[machines[0]]
    return builds_map


@fixture("builds", "publisher")
def pulled_builds(_options: None, fixtures: Fixtures) -> None:
    if isinstance(fixtures.builds, dict):
        builds_ = list(itertools.chain(*fixtures.builds.values()))
    else:
        builds_ = fixtures.builds

    for build_ in builds_:
        fixtures.publisher.pull(build_)


@fixture("tmpdir")
def storage(_options: None, fixtures: Fixtures) -> Storage:
    root = fixtures.tmpdir / "root"
    return Storage(root)


@fixture("tmpdir", "settings")
def jenkins(_options: None, fixtures: Fixtures) -> Jenkins:
    root = fixtures.tmpdir / "root"
    fixed_settings = replace(fixtures.settings, STORAGE_PATH=root)

    return MockJenkins.from_settings(fixed_settings)

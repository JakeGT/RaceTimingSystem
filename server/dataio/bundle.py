# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Event bundles: one event, everything in it, in a zip (ADR 0002).

    manifest.json                  format, schema version, the event, sha256 of every file
    data/<app>.<model>.jsonl       one row per line, in the order they must be inserted
    media/crops/<event>/<id>.jpg   observation crop images

A bundle moves an event between servers: cloud to venue laptop and back (event mode),
or from one self-hosted install to another. Importing makes the event on this server
exactly match the bundle, so importing the same bundle twice changes nothing.

What doesn't travel: pairing codes and device tokens (phones pair again), staff
accounts (the audit log keeps who did what as text) and stored results, which are
rebuilt from the reads on import. Bundles hold runners' personal details, so treat
them like a database backup.
"""

import hashlib
import json
import re
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time
from importlib.metadata import PackageNotFoundError, version
from typing import IO, Any
from uuid import UUID, uuid7

from django.core import serializers
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.serializers.base import DeserializationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, connection, models, transaction
from django.utils import timezone

from accounts.models import Organisation, User
from common.secrets import hash_secret
from events.models import CategoryRule, CategoryScheme, Entry, Event, Race, Split, TimingPoint, Wave
from results.models import RaceResults, Result
from results.services import rebuild_event
from timing.fusion import fuse_pending
from timing.models import (
    Adjustment,
    Device,
    Heartbeat,
    Observation,
    PairingCode,
    Read,
    crop_upload_path,
)
from timing.secrets import new_device_token

FORMAT = "race-timing-event-bundle"
SCHEMA_VERSION = 1
MAX_CROP_BYTES = 512 * 1024
MAX_DATA_BYTES = 1024**3  # per data file, uncompressed

# Insert order: every row's foreign keys point at rows in earlier files (or the same
# file, for nothing at present). Deleting goes in reverse.
MODELS: tuple[type[models.Model], ...] = (
    CategoryScheme,
    CategoryRule,
    Event,
    TimingPoint,
    Race,
    Wave,
    Split,
    Entry,
    Device,
    Heartbeat,
    Read,
    Observation,
    Adjustment,
)
# Never exported: secrets, and fields the importing server fills in itself.
EXCLUDED_FIELDS: dict[type[models.Model], set[str]] = {Device: {"token_hash"}}
_CROP_PATH = re.compile(r"^media/crops/[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$")


class BundleError(ValueError):
    """The bundle can't be imported; the message says why, for showing to staff."""


def label(model: type[models.Model]) -> str:
    return model._meta.label_lower


def data_path(model: type[models.Model]) -> str:
    return f"data/{label(model)}.jsonl"


def _generator() -> str:
    try:
        return f"racetiming-server {version('racetiming-server')}"
    except PackageNotFoundError:
        return "racetiming-server"


class _Encoder(DjangoJSONEncoder):
    """Keeps microseconds on times (Django's encoder cuts them to milliseconds)."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, time)):
            return o.isoformat()
        return super().default(o)


def _dumps(value: Any) -> str:
    return json.dumps(value, cls=_Encoder, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------- export


def _querysets(event: Event) -> Iterable[tuple[type[models.Model], models.QuerySet[Any]]]:
    schemes = CategoryScheme.objects.filter(races__event=event).distinct()
    for model in MODELS:
        if model is CategoryScheme:
            qs: models.QuerySet[Any] = schemes
        elif model is CategoryRule:
            qs = CategoryRule.objects.filter(scheme__in=schemes)
        elif model is Event:
            qs = Event.objects.filter(pk=event.pk)
        else:
            qs = model._default_manager.filter(event=event)
        yield model, qs.order_by("pk")


def _fields(model: type[models.Model]) -> list[str]:
    skip = EXCLUDED_FIELDS.get(model, set())
    return [
        f.name
        for f in model._meta.local_concrete_fields
        if not f.primary_key and f.name not in skip
    ]


def export_bundle(event: Event, out: IO[bytes]) -> dict[str, Any]:
    """Write the event's bundle to `out` (a file or buffer). Returns the manifest."""
    files: dict[str, dict[str, Any]] = {}

    def add(zf: zipfile.ZipFile, path: str, data: bytes, rows: int | None = None) -> None:
        zf.writestr(path, data)
        files[path] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        if rows is not None:
            files[path]["rows"] = rows

    crops: list[str] = []
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for model, qs in _querysets(event):
            rows = serializers.serialize("python", qs, fields=_fields(model))
            data = "".join(_dumps(row) + "\n" for row in rows).encode()
            add(zf, data_path(model), data, rows=len(rows))
            if model is Observation:
                crops = [row["fields"]["crop"] for row in rows if row["fields"]["crop"]]
        for name in crops:
            if not default_storage.exists(name):
                continue  # the row says there's a crop, but the file's gone
            with default_storage.open(name, "rb") as f:
                add(zf, f"media/{name}", f.read())
        manifest = {
            "format": FORMAT,
            "schema_version": SCHEMA_VERSION,
            "generator": _generator(),
            "exported_at": timezone.now().isoformat(),
            "event": {
                "id": str(event.pk),
                "name": event.name,
                "slug": event.slug,
                "start_date": event.start_date.isoformat(),
                "organisation": {
                    "name": event.organisation.name,
                    "slug": event.organisation.slug,
                },
            },
            "files": files,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def bundle_filename(event: Event) -> str:
    return f"{event.slug}-{event.start_date:%Y-%m-%d}.bundle.zip"


# ---------------------------------------------------------------------------- import


@dataclass
class BundleReport:
    event: Event
    replaced: bool
    rows: dict[str, int] = field(default_factory=dict)
    crops: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        verb = "Replaced" if self.replaced else "Imported"
        counts = ", ".join(f"{n} {name.split('.')[-1]}" for name, n in self.rows.items() if n)
        return f"{verb} {self.event}: {counts}, {self.crops} crop images."


def read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except KeyError:
        raise BundleError("This zip has no manifest.json, so it isn't an event bundle.") from None
    except ValueError:
        raise BundleError("The bundle's manifest.json isn't valid JSON.") from None
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BundleError("This zip isn't an event bundle.")
    schema = manifest.get("schema_version")
    if not isinstance(schema, int):
        raise BundleError("The bundle doesn't say which schema version it uses.")
    if schema > SCHEMA_VERSION:
        raise BundleError(
            f"This bundle uses schema version {schema}, made by a newer version of the "
            f"server (this one reads up to {SCHEMA_VERSION}). Update this server first."
        )
    if schema < SCHEMA_VERSION:
        raise BundleError(f"Schema version {schema} bundles aren't supported any more.")
    if not isinstance(manifest.get("files"), dict) or not isinstance(manifest.get("event"), dict):
        raise BundleError("The bundle's manifest is incomplete.")
    return manifest


def _verified_files(zf: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, bytes]:
    """Every file the manifest lists, checked against its size and checksum."""
    listed: dict[str, Any] = manifest["files"]
    expected_data = {data_path(m) for m in MODELS}
    present = {info.filename: info for info in zf.infolist() if not info.is_dir()}
    if unexpected := set(present) - set(listed) - {"manifest.json"}:
        raise BundleError(f"The bundle has files its manifest doesn't list: {sorted(unexpected)}")
    if missing := expected_data - set(listed):
        raise BundleError(f"The bundle is missing {sorted(missing)}.")
    contents: dict[str, bytes] = {}
    for path, meta in listed.items():
        is_data = path in expected_data
        if not is_data and not _CROP_PATH.match(path):
            raise BundleError(f"The bundle lists an unexpected file: {path!r}.")
        info = present.get(path)
        if info is None:
            raise BundleError(f"The bundle's manifest lists {path}, but it isn't in the zip.")
        limit = MAX_DATA_BYTES if is_data else MAX_CROP_BYTES
        if info.file_size > limit or not isinstance(meta, dict):
            raise BundleError(f"{path} is too big.")
        data = zf.read(info)
        if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
            raise BundleError(f"{path} doesn't match its checksum: the bundle is damaged.")
        contents[path] = data
    return contents


def _rows(model: type[models.Model], data: bytes) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(data.decode().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise BundleError(f"{data_path(model)} line {number} isn't valid JSON.") from None
        if (
            not isinstance(row, dict)
            or row.get("model") != label(model)
            or not isinstance(row.get("fields"), dict)
        ):
            raise BundleError(f"{data_path(model)} line {number} isn't a {label(model)} row.")
        rows.append(row)
    return rows


def _build(model: type[models.Model], rows: Sequence[dict[str, Any]]) -> list[Any]:
    """Model instances from rows. Values are converted and type-checked by Django's own
    deserializer; no queries are run."""
    try:
        return [
            obj.object
            for obj in serializers.deserialize(
                "python",
                [{"model": label(model), "pk": r.get("pk"), "fields": r["fields"]} for r in rows],
                handle_forward_references=False,
            )
        ]
    except (DeserializationError, FieldDoesNotExist, ValidationError, ValueError) as e:
        raise BundleError(f"{data_path(model)} has a bad row: {e}") from None


def import_bundle(
    source: IO[bytes] | str,
    organisation: Organisation,
    *,
    replace: bool = False,
    slug: str | None = None,
) -> BundleReport:
    """Import a bundle into `organisation`. If the event is already on this server,
    `replace` must be set, and the event is made to match the bundle exactly."""
    try:
        with zipfile.ZipFile(source) as zf:
            manifest = read_manifest(zf)
            contents = _verified_files(zf, manifest)
    except zipfile.BadZipFile:
        raise BundleError("That file isn't a zip, so it isn't an event bundle.") from None

    objects = {m: _build(m, _rows(m, contents[data_path(m)])) for m in MODELS}
    events = objects[Event]
    try:
        event_id = UUID(str(manifest["event"].get("id")))
    except ValueError:
        raise BundleError("The manifest's event id isn't a UUID.") from None
    if len(events) != 1 or events[0].pk != event_id:
        raise BundleError("The bundle's event rows don't match its manifest.")
    incoming: Event = events[0]

    try:
        with transaction.atomic():
            report = _import(objects, contents, incoming, organisation, replace, slug)
            fuse_pending(report.event)
            rebuild_event(report.event)
    except IntegrityError as e:
        raise BundleError(f"The bundle's data doesn't fit together: {e}") from None
    return report


def _import(
    objects: dict[type[models.Model], list[Any]],
    contents: dict[str, bytes],
    incoming: Event,
    organisation: Organisation,
    replace: bool,
    slug: str | None,
) -> BundleReport:
    existing = Event.objects.select_for_update().filter(pk=incoming.pk).first()
    if existing is not None:
        if existing.organisation_id != organisation.pk:
            raise BundleError(
                f"This event is already on this server, in {existing.organisation}. "
                "Import it there."
            )
        if not replace:
            raise BundleError(
                "This event is already on this server. Replace it to make it match the bundle."
            )
    incoming.organisation = organisation
    incoming.slug = slug or incoming.slug
    clash = Event.objects.filter(organisation=organisation, slug=incoming.slug)
    if clash.exclude(pk=incoming.pk).exists():
        raise BundleError(
            f"{organisation} already has an event at /{incoming.slug}. Pick another slug."
        )
    report = BundleReport(event=incoming, replaced=existing is not None)

    _validate(Event, [incoming])
    if existing is not None:
        _clear(existing)
    _remap_schemes(objects, organisation, incoming, report)
    incoming.save_base(raw=True)

    ids: dict[type[models.Model], set[Any]] = {m: {o.pk for o in objects[m]} for m in MODELS}
    users = _known_users(objects[Adjustment])
    for model in MODELS:
        if model in (CategoryScheme, CategoryRule, Event):
            continue
        rows = objects[model]
        _check_keys(model, rows, ids, organisation, users)
        if model is Device:
            for device in rows:  # tokens never travel: these phones pair again
                device.token_hash = hash_secret(new_device_token())
        if model is Observation:
            report.crops = _restore_crops(rows, contents, report)
        taken = model._default_manager.filter(pk__in=ids[model]).values_list("pk", flat=True)
        if clash_ids := list(taken[:1]):
            raise BundleError(
                f"A {label(model)} in the bundle ({clash_ids[0]}) belongs to another event here."
            )
        _insert(model, rows)
    report.rows = {label(m): len(objects[m]) for m in MODELS}
    return report


def _clear(event: Event) -> None:
    """Delete everything in the event (but not the event row), children first."""
    for model in (
        Adjustment,
        Observation,
        Read,
        Heartbeat,
        PairingCode,
        Device,
        Result,
        RaceResults,
        Entry,
        Split,
        Wave,
        Race,
        TimingPoint,
    ):
        model._default_manager.filter(event=event).delete()


def _remap_schemes(
    objects: dict[type[models.Model], list[Any]],
    organisation: Organisation,
    event: Event,
    report: BundleReport,
) -> None:
    """Category schemes belong to the organisation, not the event, so an import never
    changes one that's already here. New ones are added; a name clash gets a suffix."""
    mapping: dict[UUID, UUID] = {}
    keep_rules: set[UUID] = set()
    here = {
        s.pk: s
        for s in CategoryScheme.objects.filter(pk__in=[s.pk for s in objects[CategoryScheme]])
    }
    names = set(
        CategoryScheme.objects.filter(organisation=organisation).values_list("name", flat=True)
    )
    for scheme in objects[CategoryScheme]:
        found = here.get(scheme.pk)
        if found is not None and found.organisation_id == organisation.pk:
            mapping[scheme.pk] = scheme.pk
            continue
        old = scheme.pk
        if found is not None:  # another organisation's scheme: copy it under a new id
            scheme.pk = uuid7()
        mapping[old] = scheme.pk
        keep_rules.add(old)
        scheme.organisation = organisation
        if scheme.name in names:
            new_name = f"{scheme.name} ({event.name})"[:150]
            report.warnings.append(
                f"{organisation} already has a category scheme called {scheme.name!r}; "
                f"the bundle's one was added as {new_name!r}."
            )
            scheme.name = new_name
        names.add(scheme.name)
        _validate(CategoryScheme, [scheme])
        scheme.save_base(raw=True, force_insert=True)
    rules = [r for r in objects[CategoryRule] if r.scheme_id in keep_rules]
    for rule in rules:
        if rule.scheme_id != mapping[rule.scheme_id]:
            rule.pk = uuid7()
        rule.scheme_id = mapping[rule.scheme_id]
    for rule in objects[CategoryRule]:
        if rule.scheme_id not in mapping.values():
            raise BundleError(
                "A category rule in the bundle belongs to a scheme it doesn't include."
            )
    _insert(CategoryRule, rules)
    for race in objects[Race]:
        if race.category_scheme_id is not None:
            if race.category_scheme_id not in mapping:
                raise BundleError(
                    f"Race {race.name!r} uses a category scheme the bundle doesn't include."
                )
            race.category_scheme_id = mapping[race.category_scheme_id]
    objects[CategoryRule] = rules


def _known_users(adjustments: Sequence[Adjustment]) -> set[Any]:
    ids = {a.actor_id for a in adjustments if a.actor_id is not None}
    return set(User.objects.filter(pk__in=ids).values_list("pk", flat=True))


def _check_keys(
    model: type[models.Model],
    rows: Sequence[Any],
    ids: dict[type[models.Model], set[Any]],
    organisation: Organisation,
    users: set[Any],
) -> None:
    """Every foreign key must point inside the bundle, so a bundle can only ever write
    to its own event."""
    for f in model._meta.concrete_fields:
        if not f.is_relation:
            continue
        target = f.related_model
        for obj in rows:
            value = getattr(obj, f.attname)
            if value is None:
                continue
            if target is User:
                if value not in users:  # staff accounts don't travel; the label stays
                    setattr(obj, f.attname, None)
            elif target not in ids:
                raise BundleError(f"{label(model)} has an unexpected link to {target}.")
            elif value not in ids[target]:
                raise BundleError(
                    f"A {label(model)} in the bundle ({obj.pk}) points at a "
                    f"{label(target)} that isn't in it."
                )


def _restore_crops(
    observations: Sequence[Observation], contents: dict[str, bytes], report: BundleReport
) -> int:
    restored = 0
    for obs in observations:
        if not obs.crop:
            continue
        name = crop_upload_path(obs, "")
        data = contents.get(f"media/{obs.crop.name}")
        if obs.crop.name != name or data is None:
            report.warnings.append(f"Observation {obs.pk}'s crop image is missing; dropped it.")
            obs.crop = ""
            continue
        if default_storage.exists(name):
            default_storage.delete(name)
        default_storage.save(name, ContentFile(data))
        restored += 1
    return restored


def _validate(model: type[models.Model], rows: Sequence[Any]) -> None:
    """Field-level checks (lengths, choices, formats like bibs and slugs). Foreign keys
    are checked by `_check_keys` instead, without a query per row."""
    links = [f.name for f in model._meta.concrete_fields if f.is_relation]
    for obj in rows:
        try:
            obj.clean_fields(exclude=links)
        except ValidationError as e:
            problems = "; ".join(f"{k}: {' '.join(v)}" for k, v in e.message_dict.items())
            raise BundleError(
                f"A {label(model)} in the bundle ({obj.pk}) is invalid: {problems}"
            ) from None


def _insert(model: type[models.Model], rows: Sequence[Any]) -> None:
    """Insert rows as they are, keeping their timestamps. `_insert(raw=True)` is what
    Model.save_base(raw=True) (loaddata) uses; bulk_create would reset auto_now fields."""
    if not rows:
        return
    _validate(model, rows)
    fields = list(model._meta.local_concrete_fields)
    size = connection.ops.bulk_batch_size(fields, rows) or len(rows)
    manager: Any = model._base_manager
    for start in range(0, len(rows), size):
        manager._insert(rows[start : start + size], fields=fields, raw=True)

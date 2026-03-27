import json
from datetime import date
from urllib.error import HTTPError, URLError


class BaseStatsAdapter:
    unknown_error_message = "Noma'lum xatolik"
    log_unknown_error = False
    logger = None

    snapshot_model = None
    stat_model = None

    def get_url(self):
        raise NotImplementedError

    def fetch_payload(self, url):
        raise NotImplementedError

    def iter_items(self, payload):
        raise NotImplementedError

    def resolve_alias(self, area_name):
        raise NotImplementedError

    def resolve_area_name(self, item):
        raise NotImplementedError

    def resolve_external_id(self, item):
        for key in ("id", "pk", "uuid", "code"):
            value = item.get(key)
            if value is not None:
                return str(value)
        parent = item.get("parent")
        if isinstance(parent, dict) and parent.get("id"):
            return str(parent.get("id"))
        return None

    def metric_exclude_keys(self):
        return {"id", "pk", "uuid", "code", "name", "title", "mahalla", "parent", "parent_name"}

    def extract_metrics(self, item):
        metrics = {}
        excluded = self.metric_exclude_keys()
        for key, value in item.items():
            if key in excluded:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                metrics[key] = value
        return metrics

    def build_stat_instance(self, snapshot, alias, item, area_name, area_external_id, metrics):
        raise NotImplementedError

    def build_snapshot(self, payload, source_url):
        snapshot = self.snapshot_model.objects.create(
            snapshot_date=date.today(),
            source_url=source_url,
            raw_payload=payload,
        )

        bulk = []
        for item in self.iter_items(payload):
            if not isinstance(item, dict):
                continue

            area_name = self.resolve_area_name(item)
            alias = self.resolve_alias(area_name)
            area_external_id = self.resolve_external_id(item)
            metrics = self.extract_metrics(item)
            bulk.append(
                self.build_stat_instance(
                    snapshot=snapshot,
                    alias=alias,
                    item=item,
                    area_name=area_name,
                    area_external_id=area_external_id,
                    metrics=metrics,
                )
            )

        if bulk:
            self.stat_model.objects.bulk_create(bulk)

        return snapshot

    def fetch_and_store(self):
        url = self.get_url()
        try:
            payload = self.fetch_payload(url)
        except HTTPError as exc:
            return None, f"HTTP xatolik: {exc.code}"
        except URLError as exc:
            return None, f"Ulanish xatoligi: {exc.reason}"
        except json.JSONDecodeError:
            return None, "JSON o'qib bo'lmadi"
        except Exception:
            if self.log_unknown_error and self.logger:
                self.logger.exception("Stats adapter kutilmagan xatolik")
            return None, self.unknown_error_message

        snapshot = self.build_snapshot(payload, source_url=url)
        return snapshot, None

    @staticmethod
    def resolve_alias_record(alias_model, *, api_name, api_norm):
        alias, created = alias_model.objects.get_or_create(
            api_norm=api_norm,
            defaults={"api_name": api_name},
        )
        if not created and alias.api_name != api_name:
            alias.api_name = api_name
            alias.save(update_fields=["api_name", "last_seen"])
        return alias


def pick_metric(metrics, keys):
    for key in keys:
        if key in metrics and metrics[key] is not None:
            return metrics[key]
    return None

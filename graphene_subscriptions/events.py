import json
import importlib
from django.db import models
from django.core.serializers import serialize, deserialize
from django.core.serializers.base import DeserializationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from graphene_subscriptions.serialize import serialize_value, deserialize_value

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"


def trigger_subscription(group, value):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "subscription.triggered",
            "value": serialize_value(value),
            "group": group
        }
    )


class SubscriptionEvent:
    def __init__(self, operation=None, instance=None, group=None):
        self.operation = operation
        self.instance = instance
        self.group = group if group is not None else "subscriptions"

    def send(self):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            self.group, {"type": "signal.fired", "event": self.to_dict()}
        )

    def to_dict(self):
        return {
            "operation": self.operation,
            "instance": self.instance,
            "__class__": (self.__module__, self.__class__.__name__),
        }

    @staticmethod
    def from_dict(_dict):
        module_name, class_name = _dict.get("__class__")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)

        return cls(operation=_dict.get("operation"), instance=_dict.get("instance"))


class ModelSubscriptionEvent(SubscriptionEvent):
    def __init__(self, operation=None, instance=None, group=None):
        super(ModelSubscriptionEvent, self).__init__(operation, instance, group)

        if type(self.instance) == str:
            # deserialize django object
            self.instance = list(deserialize("json", self.instance))[0].object

        if not isinstance(self.instance, models.Model):
            raise ValueError(
                "ModelSubscriptionEvent instance value must be a Django model"
            )

    def to_dict(self):
        _dict = super(ModelSubscriptionEvent, self).to_dict()

        _dict["instance"] = serialize("json", [self.instance])

        return _dict

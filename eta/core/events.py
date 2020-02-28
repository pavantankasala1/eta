'''
Core tools and data structures for working with events in images and videos.

Copyright 2017-2020, Voxel51, Inc.
voxel51.com

Brian Moore, brian@voxel51.com
Jason Corso, jason@voxel51.com
'''
# pragma pylint: disable=redefined-builtin
# pragma pylint: disable=unused-wildcard-import
# pragma pylint: disable=wildcard-import
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import *
from future.utils import iteritems
# pragma pylint: enable=redefined-builtin
# pragma pylint: enable=unused-wildcard-import
# pragma pylint: enable=wildcard-import

from copy import deepcopy

import eta.core.data as etad
import eta.core.frameutils as etaf
import eta.core.geometry as etag
import eta.core.labels as etal
import eta.core.objects as etao
import eta.core.serial as etas
import eta.core.utils as etau


class DetectedEvent(etal.Labels, etag.HasBoundingBox):
    '''A detected event in an image or frame of a video.

    Attributes:
        type: the fully-qualified class name of the event
        label: (optional) event label
        bounding_box: (optional) a BoundingBox around the event
        mask: (optional) a mask for the event within its bounding box
        confidence: (optional) the label confidence, in [0, 1]
        top_k_probs: (optional) dictionary mapping labels to probabilities
        index: (optional) an index assigned to the event
        frame_number: (optional) the frame number in which the event was
            detected
        attrs: (optional) an AttributeContainer describing attributes of the
            frame
        objects: (optional) a DetectedObjectContainer describing detected
            objects in the frame
    '''

    def __init__(
            self, label=None, bounding_box=None, mask=None, confidence=None,
            top_k_probs=None, index=None, frame_number=None, attrs=None,
            objects=None):
        '''Creates a DetectedEvent instance.

        Args:
            label: (optional) event label
            bounding_box: (optional) a BoundingBox around the event
            mask: (optional) a numpy array describing the mask for the event
                within its bounding box
            confidence: (optional) the label confidence, in [0, 1]
            top_k_probs: (optional) dictionary mapping labels to probabilities
            index: (optional) an index assigned to the event
            frame_number: (optional) the frame number in which this event was
                detected
            attrs: (optional) an AttributeContainer of attributes for the frame
            objects: (optional) a DetectedObjectContainer of detected objects
                for the frame
        '''
        self.type = etau.get_class_name(self)
        self.label = label
        self.bounding_box = bounding_box
        self.mask = mask
        self.confidence = confidence
        self.top_k_probs = top_k_probs
        self.index = index
        self.frame_number = frame_number
        self.attrs = attrs or etad.AttributeContainer()
        self.objects = objects or etao.DetectedObjectContainer()

    @property
    def is_empty(self):
        '''Whether this event has no labels of any kind.'''
        return not (
            self.has_label or self.has_bounding_box or self.has_mask
            or self.has_attributes or self.has_objects)

    @property
    def has_label(self):
        '''Whether this event has a label.'''
        return self.label is not None

    @property
    def has_bounding_box(self):
        '''Whether this event has a bounding box.'''
        return self.bounding_box is not None

    @property
    def has_mask(self):
        '''Whether this event has a segmentation mask.'''
        return self.mask is not None

    @property
    def has_confidence(self):
        '''Whether this event has a confidence.'''
        return self.confidence is not None

    @property
    def has_top_k_probs(self):
        '''Whether this event has top-k probabilities.'''
        return self.top_k_probs is not None

    @property
    def has_index(self):
        '''Whether this event has an index.'''
        return self.index is not None

    @property
    def has_frame_number(self):
        '''Whether this event has a frame number.'''
        return self.frame_number is not None

    @property
    def has_attributes(self):
        '''Whether this event has attributes.'''
        return bool(self.attrs)

    @property
    def has_objects(self):
        '''Whether this event has at least one object.'''
        return bool(self.objects)

    @classmethod
    def get_schema_cls(cls):
        '''Gets the schema class for `DetectedEvent`s.

        Returns:
            the LabelsSchema class
        '''
        return EventSchema

    def iter_attributes(self):
        '''Returns an iterator over the attributes of the event.

        Returns:
            an iterator over `Attribute`s
        '''
        return iter(self.attrs)

    def iter_objects(self):
        '''Returns an iterator over the objects in the event.

        Returns:
            an iterator over `DetectedObject`s
        '''
        return iter(self.objects)

    def get_bounding_box(self):
        '''Returns the BoundingBox for the event.

        Returns:
             a BoundingBox
        '''
        return self.bounding_box

    def add_attribute(self, attr):
        '''Adds the attribute to the event.

        Args:
            attr: an Attribute
        '''
        self.attrs.add(attr)

    def add_attributes(self, attrs):
        '''Adds the attributes to the event.

        Args:
            attrs: an AttributeContainer
        '''
        self.attrs.add_container(attrs)

    def add_object(self, obj):
        '''Adds the object to the event.

        Args:
            obj: a DetectedObject
        '''
        self.objects.add(obj)

    def add_objects(self, objs):
        '''Adds the objects to the event.

        Args:
            objs: a DetectedObjectContainer
        '''
        self.objects.add_container(objs)

    def clear_attributes(self):
        '''Removes all frame-level attributes from the event.'''
        self.attrs = etad.AttributeContainer()

    def clear_objects(self):
        '''Removes all objects from the event.'''
        self.objects = etao.DetectedObjectContainer()

    def clear_object_attributes(self):
        '''Removes all object-level attributes from the event.'''
        for obj in self.objects:
            obj.clear_attributes()

    def filter_by_schema(self, schema, allow_none_label=False):
        '''Filters the event by the given schema.

        The `label` of the DetectedEvent must match the provided schema. Or,
        it can be `None` when `allow_none_label == True`.

        Args:
            schema: an EventSchema
            allow_none_label: whether to allow the event label to be `None`.
                By default, this is False

        Raises:
            LabelsSchemaError: if the event label does not match the schema
        '''
        if self.label is None:
            if not allow_none_label:
                raise EventSchemaError(
                    "None event label is not allowed by the schema")
        elif self.label != schema.get_label():
            raise EventSchemaError(
                "Label '%s' does not match event schema" % self.label)

        self.attrs.filter_by_schema(schema.frames)
        self.objects.filter_by_schema(schema.objects)

    def remove_objects_without_attrs(self, labels=None):
        '''Removes objects from the event that do not have attributes.

        Args:
            labels: an optional list of object `label` strings to which to
                restrict attention when filtering. By default, all objects are
                processed
        '''
        self.objects.remove_objects_without_attrs(labels=labels)

    def attributes(self):
        '''Returns the list of class attributes that will be serialized.

        Returns:
            a list of attribute names
        '''
        _attrs = ["type"]
        _noneable_attrs = [
            "label", "bounding_box", "mask", "confidence", "top_k_probs",
            "index", "frame_number"]
        _attrs.extend(
            [a for a in _noneable_attrs if getattr(self, a) is not None])
        if self.attrs:
            _attrs.append("attrs")
        if self.objects:
            _attrs.append("objects")

        return _attrs

    @classmethod
    def from_dict(cls, d):
        '''Constructs a DetectedEvent from a JSON dictionary.

        Args:
            d: a JSON dictionary

        Returns:
            a DetectedEvent
        '''
        bounding_box = d.get("bounding_box", None)
        if bounding_box is not None:
            bounding_box = etag.BoundingBox.from_dict(bounding_box)

        mask = d.get("mask", None)
        if mask is not None:
            mask = etas.deserialize_numpy_array(mask)

        attrs = d.get("attrs", None)
        if attrs is not None:
            attrs = etad.AttributeContainer.from_dict(attrs)

        objects = d.get("objects", None)
        if objects is not None:
            objects = etao.DetectedObjectContainer.from_dict(objects)

        return cls(
            label=d.get("label", None),
            bounding_box=bounding_box,
            mask=mask,
            confidence=d.get("confidence", None),
            top_k_probs=d.get("top_k_probs", None),
            index=d.get("index", None),
            frame_number=d.get("frame_number", None),
            attrs=attrs,
            objects=objects,
        )


class DetectedEventContainer(etal.LabelsContainer):
    '''An `eta.core.serial.Container` of `DetectedEvent`s.'''

    _ELE_CLS = DetectedEvent
    _ELE_CLS_FIELD = "_EVENT_CLS"
    _ELE_ATTR = "events"

    def get_labels(self):
        '''Returns a set containing the labels of the `DetectedEvent`s.

        Returns:
            a set of labels
        '''
        return set(obj.label for obj in self)

    def sort_by_confidence(self, reverse=False):
        '''Sorts the `DetectedEvent`s by confidence.

        `DetectedEvent`s whose confidence is None are always put last.

        Args:
            reverse: whether to sort in descending order. The default is False
        '''
        self.sort_by("confidence", reverse=reverse)

    def sort_by_index(self, reverse=False):
        '''Sorts the `DetectedEvent`s by index.

        `DetectedEvent`s whose index is None are always put last.

        Args:
            reverse: whether to sort in descending order. The default is False
        '''
        self.sort_by("index", reverse=reverse)

    def sort_by_frame_number(self, reverse=False):
        '''Sorts the `DetectedEvent`s by frame number

        `DetectedEvent`s whose frame number is None are always put last.

        Args:
            reverse: whether to sort in descending order. The default is False
        '''
        self.sort_by("frame_number", reverse=reverse)

    def filter_by_schema(self, schema):
        '''Filters the events in the container by the given schema.

        Args:
            schema: an EventContainerSchema
        '''
        # Remove events with invalid labels
        filter_func = lambda event: schema.has_event_label(event.label)
        self.filter_elements([filter_func])

        # Filter events by their schemas
        for event in self:
            event_schema = schema.get_event_schema(event.label)
            event.filter_by_schema(event_schema)

    def remove_objects_without_attrs(self, labels=None):
        '''Removes objects from this container that do not have attributes.

        Args:
            labels: an optional list of object `label` strings to which to
                restrict attention when filtering. By default, all objects are
                processed
        '''
        for event in self:
            event.remove_objects_without_attrs(labels=labels)


class VideoEvent(etal.Labels, etal.HasLabelsSupport, etal.HasFramewiseView):
    '''A spatiotemporal event in a video.

    `VideoEvent`s are spatiotemporal concepts that describe a collection of
    information about an event in a video. `VideoEvent`s can have labels with
    confidences, event-level attributes that apply to the event over all
    frames, spatiotemporal objects, frame-level attributes such as bounding
    boxes, object detections, and attributes that apply to individual frames,
    and child objects and events.

    Attributes:
        type: the fully-qualified class name of the event
        label: (optional) the event label
        confidence: (optional) the label confidence in [0, 1]
        support: a FrameRanges instance describing the support of the event
        index: (optional) an index assigned to the event
        uuid: (optional) a UUID assigned to the event
        attrs: an AttributeContainer of event-level attributes
        objects: a VideoObjectContainer of objects
        frames: dictionary mapping frame numbers to `DetectedEvent`s
        child_objects: a set of UUIDs of child `VideoObject`s
        child_events: a set of UUIDs of child `VideoEvent`s
    '''

    def __init__(
            self, label=None, confidence=None, support=None, index=None,
            uuid=None, attrs=None, objects=None, frames=None,
            child_objects=None, child_events=None):
        '''Creates a VideoEvent instance.

        Args:
            label: (optional) the event label
            confidence: (optional) the label confidence in [0, 1]
            support: (optional) a FrameRanges instance describing the frozen
                support of the event
            index: (optional) a index assigned to the event
            uuid: (optional) a UUID assigned to the event
            attrs: (optional) an AttributeContainer of event-level attributes
            objects: (optional) a VideoObjectContainer of objects
            frames: (optional) dictionary mapping frame numbers to
                `DetectedEvent`s
            child_objects: (optional) a set of UUIDs of child `VideoObject`s
            child_events: (optional) a set of UUIDs of child `VideoEvent`s
        '''
        self.type = etau.get_class_name(self)
        self.label = label
        self.confidence = confidence
        self.index = index
        self.uuid = uuid
        self.attrs = attrs or etad.AttributeContainer()
        self.objects = objects or etao.VideoObjectContainer()
        self.frames = frames or {}
        self.child_objects = set(child_objects or [])
        self.child_events = set(child_events or [])
        etal.HasLabelsSupport.__init__(self, support=support)

    @property
    def is_empty(self):
        '''Whether this instance has no labels of any kind.'''
        return False

    @property
    def has_attributes(self):
        '''Whether the event has event- or frame-level attributes.'''
        return self.has_event_attributes or self.has_frame_attributes

    @property
    def has_event_attributes(self):
        '''Whether the event has event-level attributes.'''
        return bool(self.attrs)

    @property
    def has_frame_attributes(self):
        '''Whether the event has frame-level attributes.'''
        for event in self.iter_detections():
            if event.has_attributes:
                return True

        return False

    @property
    def has_video_objects(self):
        '''Whether the event has at least one VideoObject.'''
        return bool(self.objects)

    @property
    def has_detected_objects(self):
        '''Whether the event has at least one DetectedObject.'''
        for event in self.iter_detections():
            if event.has_objects:
                return True

        return False

    @property
    def has_child_objects(self):
        '''Whether the event has at least one child VideoObject.'''
        return bool(self.child_objects)

    @property
    def has_child_events(self):
        '''Whether the event has at least one child VideoEvent.'''
        return bool(self.child_events)

    def iter_attributes(self):
        '''Returns an iterator over the event-level attributes of the event.

        Returns:
            an iterator over `Attribute`s
        '''
        return iter(self.attrs)

    def iter_video_objects(self):
        '''Returns an iterator over the `VideoObject`s in the event.

        Returns:
            an iterator over `VideoObject`s
        '''
        return iter(self.objects)

    def iter_detections(self):
        '''Returns an iterator over the `DetectedEvent`s for each frame of the
        event.

        The frames are traversed in sorted order.

        Returns:
            an iterator over `DetectedEvent`s
        '''
        for frame_number in sorted(self.frames):
            yield self.frames[frame_number]

    def add_event_attribute(self, attr):
        '''Adds the event-level attribute to the event.

        Args:
            attr: an Attribute
        '''
        self.attrs.add(attr)

    def add_event_attributes(self, attrs):
        '''Adds the AttributeContainer of event-level attributes to the event.

        Args:
            attrs: an AttributeContainer
        '''
        self.attrs.add_container(attrs)

    def add_frame_attribute(self, attr, frame_number):
        '''Adds the frame-level attribute to the event.

        Args:
            attr: an Attribute
            frame_number: the frame number
        '''
        self._ensure_frame(frame_number)
        self.frames[frame_number].add_attribute(attr)

    def add_frame_attributes(self, attrs, frame_number):
        '''Adds the given frame-level attributes to the event.

        Args:
            attrs: an AttributeContainer
            frame_number: the frame number
        '''
        self._ensure_frame(frame_number)
        self.frames[frame_number].add_attributes(attrs)

    def add_object(self, obj, frame_number=None):
        '''Adds the object to the event.

        Args:
            obj: a VideoObject or DetectedObject
            frame_number: (DetectedObject only) the frame number. If omitted,
                the DetectedObject must have its `frame_number` set
        '''
        if isinstance(obj, etao.DetectedObject):
            self._add_detected_object(obj, frame_number)
        else:
            self.objects.add(obj)

    def add_objects(self, objects, frame_number=None):
        '''Adds the objects to the event.

        Args:
            objects: a VideoObjectContainer or DetectedObjectContainer
            frame_number: (DetectedObjectContainer only) the frame number. If
                omitted, the `DetectedObject`s must have their `frame_number`s
                set
        '''
        if isinstance(objects, etao.DetectedObjectContainer):
            self._add_detected_objects(objects, frame_number)
        else:
            self.objects.add_container(objects)

    def add_detection(self, event, frame_number=None, clean=True):
        '''Adds the detection to the event.

        Args:
            event: a DetectedEvent
            frame_number: a frame number. If omitted, the DetectedEvent must
                have its `frame_number` set
            clean: whether to set the `label` and `index` fields of the
                DetectedEvent to `None`. By default, this is True
        '''
        self._add_detected_event(event, frame_number, clean)

    def add_detections(self, events, clean=True):
        '''Adds the detections to the event.

        The `DetectedEvent`s must have their `frame_number`s set.

        Args:
            events: a DetectedEventContainer
            clean: whether to set the `label` and `index` fields of the
                `DetectedEvent`s to `None`. By default, this is True
        '''
        self._add_detected_events(events, clean)

    def add_child_object(self, obj):
        '''Adds the VideoObject as a child of this event.

        Args:
            obj: a VideoObject, which must have its `uuid` set
        '''
        if obj.uuid is None:
            raise ValueError("VideoObject must have its `uuid` set")

        self.child_objects.add(obj.uuid)

    def add_child_event(self, event):
        '''Adds the VideoEvent as a child of this event.

        Args:
            event: a VideoEvent, which must have its `uuid` set
        '''
        if event.uuid is None:
            raise ValueError("VideoEvent must have its `uuid` set")

        self.child_events.add(event.uuid)

    def clear_attributes(self):
        '''Removes all attributes of any kind from the event.'''
        self.clear_event_attributes()
        self.clear_frame_attributes()

    def clear_event_attributes(self):
        '''Removes all event-level attributes from the event.'''
        self.attrs = etad.AttributeContainer()

    def clear_video_objects(self):
        '''Removes all `VideoObject`s from the event.'''
        self.objects = etao.VideoObjectContainer()

    def clear_frame_attributes(self):
        '''Removes all frame attributes from the event.'''
        for event in self.iter_detections():
            event.clear_attributes()

    def clear_detected_objects(self):
        '''Removes all `DetectedObject`s from the event.'''
        for event in self.iter_detections():
            event.clear_objects()

    def clear_detections(self):
        '''Removes all `DetectedEvent`s from the event.'''
        self.frames = {}

    def clear_child_objects(self):
        '''Removes all child objects from the event.'''
        self.child_objects = set()

    def clear_child_events(self):
        '''Removes all child events from the event.'''
        self.child_events = set()

    def render_framewise_labels(self):
        '''Renders a framewise copy of the event.

        Returns:
            a VideoEvent whose labels are all contained in `DetectedEvent`s
        '''
        renderer = VideoEventFrameRenderer(self)
        frames = renderer.render_all_frames()
        return VideoEvent(frames=frames)

    def filter_by_schema(self, schema, objects=None, events=None):
        '''Filters the event by the given schema.

        Args:
            schema: an EventSchema
            objects: an optional dictionary mapping uuids to `VideoObject`s. If
                provided, the child objects of the event will be filtered by
                their respective schemas
            events: an optional dictionary mapping uuids to `VideoEvent`s. If
                provided, the child events of the event will be filtered by
                their respective schemas

        Raises:
            LabelsSchemaError: if the event label does not match the schema
        '''
        schema.validate_label(self.label)
        self.attrs.filter_by_schema(schema.attrs)
        self.objects.filter_by_schema(schema.objects)
        for event in self.iter_detections():
            event.filter_by_schema(schema)

        # @todo children...
        '''
        # Filter child objects
        if objects:
            for uuid in self.child_objects:
                if uuid in objects:
                    child_obj = objects[uuid]
                    if not schema.has_object_label(child_obj.label):
                        self.child_objects.remove(uuid)
                    else:
                        child_obj.filter_by_schema(
                            schema.get_object_schema(child_obj.label))

        # Filter child events
        if events:
            for uuid in self.child_events:
                if uuid in events:
                    child_event = events[uuid]
                    if not schema.has_event_label(child_event.label):
                        self.child_events.remove(uuid)
                    else:
                        child_event.filter_by_schema(
                            schema.get_child_event_schema(child_event.label))
        '''

    def remove_objects_without_attrs(self, labels=None):
        '''Removes objects that do not have attributes from this event.

        Args:
            labels: an optional list of object `label` strings to which to
                restrict attention when filtering. By default, all objects are
                processed
        '''
        self.objects.remove_objects_without_attrs(labels=labels)
        for event in self.iter_detections():
            event.remove_objects_without_attrs(labels=labels)

    def attributes(self):
        '''Returns the list of attributes to serialize.

        Returns:
            a list of attrinutes
        '''
        _attrs = ["type"]
        if self.label is not None:
            _attrs.append("label")
        if self.confidence is not None:
            _attrs.append("confidence")
        if self.is_support_frozen:
            _attrs.append("support")
        if self.index is not None:
            _attrs.append("index")
        if self.uuid is not None:
            _attrs.append("uuid")
        if self.attrs:
            _attrs.append("attrs")
        if self.objects:
            _attrs.append("objects")
        if self.frames:
            _attrs.append("frames")
        if self.child_objects:
            _attrs.append("child_objects")
        if self.child_events:
            _attrs.append("child_events")
        return _attrs

    @staticmethod
    def build_simple(
            first, last, label, confidence=None, index=None, uuid=None):
        '''Builds a simple contiguous VideoEvent.

        Args:
            first: the first frame of the event
            last: the last frame of the event
            label: the event label
            confidence: (optional) confidence in [0, 1]
            index: (optional) an index for the event
            uuid: (optional) a UUID for the event

        Returns:
             a VideoEvent
        '''
        support = etaf.FrameRanges.build_simple(first, last)
        return VideoEvent(
            label=label, confidence=confidence, support=support, index=index,
            uuid=uuid)

    @classmethod
    def _from_dict(cls, d):
        '''Internal implementation of `from_dict()`.

        Subclasses should implement this method, NOT `from_dict()`.

        Args:
            d: a JSON dictionary

        Returns:
            a VideoEvent
        '''
        support = d.get("support", None)
        if support is not None:
            support = etaf.FrameRanges.from_dict(support)

        attrs = d.get("attrs", None)
        if attrs is not None:
            attrs = etad.AttributeContainer.from_dict(attrs)

        objects = d.get("objects", None)
        if objects is not None:
            objects = etao.VideoObjectContainer.from_dict(objects)

        frames = d.get("frames", None)
        if frames is not None:
            frames = {
                int(fn): DetectedEvent.from_dict(do)
                for fn, do in iteritems(frames)
            }

        return cls(
            label=d.get("label", None),
            confidence=d.get("confidence", None),
            support=support,
            index=d.get("index", None),
            uuid=d.get("uuid", None),
            attrs=attrs,
            objects=objects,
            frames=frames,
            child_objects=d.get("child_objects", None),
            child_events=d.get("child_events", None),
        )

    @classmethod
    def from_dict(cls, d):
        '''Constructs a VideoEvent from a JSON dictionary.

        Args:
            d: a JSON dictionary

        Returns:
            a VideoEvent
        '''
        if "type" in d:
            event_cls = etau.get_class(d["type"])
        else:
            event_cls = cls

        return event_cls._from_dict(d)

    def _ensure_frame(self, frame_number):
        if not frame_number in self.frames:
            self.frames[frame_number] = DetectedEvent(
                frame_number=frame_number)

    def _add_detected_object(self, obj, frame_number):
        if frame_number is None:
            if not obj.has_frame_number:
                raise ValueError(
                    "Either `frame_number` must be provided or the "
                    "DetectedObject must have its `frame_number` set")

            frame_number = obj.frame_number

        obj.frame_number = frame_number
        self._ensure_frame(frame_number)
        self.frames[frame_number].add_object(obj)

    def _add_detected_objects(self, objects, frame_number):
        for obj in objects:
            self._add_detected_object(obj, frame_number)

    def _add_detected_event(self, event, frame_number, clean):
        if frame_number is None:
            if not event.has_frame_number:
                raise ValueError(
                    "Either `frame_number` must be provided or the "
                    "DetectedEvent must have its `frame_number` set")

            frame_number = event.frame_number

        if clean:
            event.label = None
            event.index = None

        event.frame_number = frame_number
        self.frames[frame_number] = event

    def _add_detected_events(self, events, clean):
        for event in events:
            self._add_detected_event(event, None, clean)

    def _compute_support(self):
        frame_ranges = etaf.FrameRanges.from_iterable(self.frames.keys())
        frame_ranges.merge(*[obj.support for obj in self.objects])
        return frame_ranges


class VideoEventContainer(etal.LabelsContainer):
    '''An `eta.core.serial.Container` of `VideoEvent`s.'''

    _ELE_CLS = VideoEvent
    _ELE_CLS_FIELD = "_EVENT_CLS"
    _ELE_ATTR = "events"

    def get_labels(self):
        '''Returns a set containing the labels of the `VideoEvent`s.

        Returns:
            a set of labels
        '''
        return set(event.label for event in self)

    def sort_by_confidence(self, reverse=False):
        '''Sorts the `VideoEvent`s by confidence.

        `VideoEvent`s whose confidence is None are always put last.

        Args:
            reverse: whether to sort in descending order. The default is False
        '''
        self.sort_by("confidence", reverse=reverse)

    def sort_by_index(self, reverse=False):
        '''Sorts the `VideoEvent`s by index.

        `VideoEvent`s whose index is None are always put last.

        Args:
            reverse: whether to sort in descending order. The default is False
        '''
        self.sort_by("index", reverse=reverse)

    def filter_by_schema(self, schema, objects=None, events=None):
        '''Filter the events in the container by the given schema.

        Args:
            schema: an EventContainerSchema
            objects: an optional dictionary mapping uuids to `VideoObject`s. If
                provided, child objects will be filtered by their respective
                schemas
            events: an optional dictionary mapping uuids to `VideoEvent`s. If
                provided, child events will be filtered by their respective
                schemas

        Raises:
            LabelsSchemaError: if the label does not match the schema
        '''
        # Filter by event label
        filter_func = lambda event: schema.has_event_label(event.label)
        self.filter_elements([filter_func])

        # Filter events
        for event in self:
            event_schema = schema.get_event_schema(event.label)
            event.filter_by_schema(
                event_schema, objects=objects, events=events)

    def remove_objects_without_attrs(self, labels=None):
        '''Removes objects that do not have attributes from all events in this
        container.

        Args:
            labels: an optional list of object `label` strings to which to
                restrict attention when filtering. By default, all objects are
                processed
        '''
        for event in self:
            event.remove_objects_without_attrs(labels=labels)


class EventSchema(etal.LabelsSchema):
    '''Schema for `DetectedEvent`s and `VideoEvent`s.

    Attributes:
        label: the event label
        attrs: an AttributeContainerSchema describing the event-level
            attributes of the event
        frames: an AttributeContainerSchema describing the frame-level
            attributes of the event
        objects: an ObjectContainerSchema describing the objects of the event
    '''

    def __init__(self, label, attrs=None, frames=None, objects=None):
        '''Creates an EventSchema instance.

        Args:
            label: the event label
            attrs: (optional) an AttributeContainerSchema describing the
                event-level attributes of the event
            frames: (optional) an AttributeContainerSchema describing the
                frame-level attributes of the event
            objects: (optional) an ObjectContainerSchema describing the objects
                of the event
        '''
        self.label = label
        self.attrs = attrs or etad.AttributeContainerSchema()
        self.frames = frames or etad.AttributeContainerSchema()
        self.objects = objects or etao.ObjectContainerSchema()

    @property
    def is_empty(self):
        '''Whether this schema has no labels of any kind.'''
        return False

    def has_label(self, label):
        '''Whether the schema has the given event label.

        Args:
            label: an event label

        Returns:
            True/False
        '''
        return label == self.label

    def get_label(self):
        '''Gets the event label for the schema.

        Returns:
            the event label
        '''
        return self.label

    def has_event_attribute(self, attr_name):
        '''Whether the schema has an event-level attribute with the given name.

        Args:
            attr_name: the name

        Returns:
            True/False
        '''
        return self.attrs.has_attribute(attr_name)

    def get_event_attribute_schema(self, attr_name):
        '''Gets the AttributeSchema for the event-level attribute with the
        given name.

        Args:
            attr_name: the name

        Returns:
            the AttributeSchema
        '''
        return self.attrs.get_attribute_schema(attr_name)

    def get_event_attribute_class(self, attr_name):
        '''Gets the Attribute class for the event-level attribute with the
        given name.

        Args:
            attr_name: the name

        Returns:
            the Attribute class
        '''
        return self.attrs.get_attribute_class(attr_name)

    def has_frame_attribute(self, attr_name):
        '''Whether the schema has a frame-level attribute with the given name.

        Args:
            attr_name: the name

        Returns:
            True/False
        '''
        return self.frames.has_attribute(attr_name)

    def get_frame_attribute_schema(self, attr_name):
        '''Gets the AttributeSchema for the frame-level attribute with the
        given name.

        Args:
            attr_name: the name

        Returns:
            the AttributeSchema
        '''
        return self.frames.get_attribute_schema(attr_name)

    def get_frame_attribute_class(self, attr_name):
        '''Gets the Attribute class for the frame-level attribute with the
        given name.

        Args:
            attr_name: the name

        Returns:
            the Attribute
        '''
        return self.frames.get_attribute_class(attr_name)

    def has_object_label(self, label):
        '''Whether the schema has an object with the given label.

        Args:
            label: the object label

        Returns:
            True/False
        '''
        return self.objects.has_object_label(label)

    def has_object_attribute(self, label, attr_name):
        '''Whether the schema has an object with the given label with an
        object-level attribute of the given name.

        Args:
            label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            True/False
        '''
        return self.objects.has_object_attribute(label, attr_name)

    def has_object_frame_attribute(self, label, attr_name):
        '''Whether the schema has an object with the given label with a
        frame-level attribute of the given name.

        Args:
            label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            True/False
        '''
        return self.objects.has_frame_attribute(label, attr_name)

    def get_object_schema(self, label):
        '''Gets the ObjectSchema for the object with the given label.

        Args:
            label: the object label

        Returns:
            the ObjectSchema
        '''
        return self.objects.get_object_schema(label)

    def get_object_attribute_schema(self, label, attr_name):
        '''Gets the AttributeSchema for the object-level attribute of the
        given name for the object with the given label.

        Args:
            label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            the AttributeSchema
        '''
        return self.objects.get_object_attribute_schema(label, attr_name)

    def get_object_frame_attribute_schema(self, label, attr_name):
        '''Gets the AttributeSchema for the frame-level attribute of the
        given name for the object with the given label.

        Args:
            label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            the AttributeSchema
        '''
        return self.objects.get_frame_attribute_schema(label, attr_name)

    def get_object_attribute_class(self, label, attr_name):
        '''Gets the Attribute class for the object-level attribute of the
        given name for the object with the given label.

        Args:
            label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            the Attribute
        '''
        return self.objects.get_object_attribute_class(label, attr_name)

    def get_object_frame_attribute_class(self, label, attr_name):
        '''Gets the Attribute class for the frame-level attribute of the
        given name for the object with the given label.

        Args:
            label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            the Attribute
        '''
        return self.objects.get_frame_attribute_class(label, attr_name)

    def add_event_attribute(self, attr):
        '''Adds the given event-level attribute to the schema.

        Args:
            attr: an Attribute
        '''
        self.attrs.add_attribute(attr)

    def add_event_attributes(self, attrs):
        '''Adds the given event-level attributes to the schema.

        Args:
            attrs: an AttributeContainer
        '''
        self.attrs.add_attributes(attrs)

    def add_frame_attribute(self, attr):
        '''Adds the given frame-level attribute to the schema.

        Args:
            attr: an Attribute
        '''
        self.frames.add_attribute(attr)

    def add_frame_attributes(self, attrs):
        '''Adds the given frame-level attributes to the schema.

        Args:
            attrs: an AttributeContainer
        '''
        self.frames.add_attributes(attrs)

    def add_object_label(self, label):
        '''Adds the given object label to the schema.

        ArgsL:
            label: an object label
        '''
        self.objects.add_object_label(label)

    def add_object_attribute(self, label, attr):
        '''Adds the object-level Attribute for the object with the given
        label to the schema.

        Args:
            label: an object label
            attr: an object-level Attribute
        '''
        self.objects.add_object_attribute(label, attr)

    def add_object_frame_attribute(self, label, attr):
        '''Adds the frame-level Attribute for the object with the given label
        to the schema.

        Args:
            label: an object label
            attr: a frame-level Attribute
        '''
        self.objects.add_frame_attribute(label, attr)

    def add_object_attributes(self, label, attrs):
        '''Adds the AttributeContainer of object-level attributes for the
        object with the given label to the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer
        '''
        self.objects.add_object_attributes(label, attrs)

    def add_object_frame_attributes(self, label, attrs):
        '''Adds the AttributeContainer of frame-level attributes for the object
        with the given label to the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer
        '''
        self.objects.add_frame_attributes(label, attrs)

    def add_object(self, obj):
        '''Adds the object to the schema.

        Args:
            obj: a VideoObject or DetectedObject
        '''
        self.objects.add_object(obj)

    def add_objects(self, objects):
        '''Adds the objects to the schema.

        Args:
            objects: a VideoObjectContainer or DetectedObjectContainer
        '''
        self.objects.add_objects(objects)

    def add_event(self, event):
        '''Adds the event to the schema.

        Args:
            event: a VideoEvent or DetectedEvent
        '''
        if isinstance(event, DetectedEvent):
            self._add_detected_event(event)
        else:
            self._add_video_event(event)

    def add_events(self, events):
        '''Adds the events to the schema.

        Args:
            events: a VideoEventContainer or DetectedEventContainer
        '''
        for event in events:
            self.add_event(event)

    def is_valid_event_attribute(self, attr):
        '''Whether the event-level attribute is compliant with the schema.

        Args:
            attr: an Attribute

        Returns:
            True/False
        '''
        return self.attrs.is_valid_attribute(attr)

    def is_valid_event_attributes(self, attrs):
        '''Whether the AttributeContainer of event-level attributes is
        compliant with the schema.

        Args:
            attrs: an AttributeContainer

        Returns:
            True/False
        '''
        return self.attrs.is_valid_attributes(attrs)

    def is_valid_frame_attribute(self, attr):
        '''Whether the frame-level attribute is compliant with the schema.

        Args:
            attr: an Attribute

        Returns:
            True/False
        '''
        return self.frames.is_valid_attribute(attr)

    def is_valid_frame_attributes(self, attrs):
        '''Whether the AttributeContainer of frame-level attributes is
        compliant with the schema.

        Args:
            attrs: an AttributeContainer

        Returns:
            True/False
        '''
        return self.frames.is_valid_attributes(attrs)

    def is_valid_object_label(self, label):
        '''Whether the object label is compliant with the schema.

        Args:
            label: an object label

        Returns:
            True/False
        '''
        return self.objects.is_valid_object_label(label)

    def is_valid_object_attribute(self, label, attr):
        '''Whether the object-level attribute for the object with the given
        label is compliant with the schema.

        Args:
            label: an object label
            attr: an object-level Attribute

        Returns:
            True/False
        '''
        return self.objects.is_valid_object_attribute(label, attr)

    def is_valid_object_attributes(self, label, attrs):
        '''Whether the AttributeContainer of object-level attributes for the
        object with the given label is compliant with the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer of object-level attributes

        Returns:
            True/False
        '''
        return self.objects.is_valid_object_attributes(label, attrs)

    def is_valid_object_frame_attribute(self, label, attr):
        '''Whether the frame-level attribute for the object with the given
        label is compliant with the schema.

        Args:
            label: an object label
            attr: a frame-level Attribute

        Returns:
            True/False
        '''
        return self.objects.is_valid_frame_attribute(label, attr)

    def is_valid_object_frame_attributes(self, label, attrs):
        '''Whether the AttributeContainer of frame-level attributes for the
        object with the given label is compliant with the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer of frame-level attributes

        Returns:
            True/False
        '''
        return self.objects.is_valid_frame_attributess(label, attrs)

    def is_valid_object(self, obj):
        '''Whether the object is compliant with the schema.

        Args:
            obj: a VideoObject or DetectedObject

        Returns:
            True/False
        '''
        return self.objects.is_valid_object(obj)

    def validate_label(self, label):
        '''Validates that the event label is compliant with the schema.

        Args:
            label: the label

        Raises:
            LabelsSchemaError: if the label violates the schema
        '''
        if label != self.label:
            raise EventSchemaError(
                "Label '%s' does not match event schema" % label)

    def validate_event_attribute_name(self, attr_name):
        '''Validates that the schema contains an event-level attribute with the
        given name.

        Args:
            attr_name: the attribute name

        Raises:
            LabelsSchemaError: if the schema does not contain the attribute
        '''
        self.attrs.validate_attribute_name(attr_name)

    def validate_event_attribute(self, attr):
        '''Validates that the event-level attribute is compliant with the
        schema.

        Args:
            attr: an Attribute

        Raises:
            LabelsSchemaError: if the attribute violates the schema
        '''
        self.attrs.validate_attribute(attr)

    def validate_event_attributes(self, attrs):
        '''Validates that the AttributeContainer of event-level attributes is
        compliant with the schema.

        Args:
            attrs: an AttributeContainer

        Raises:
            LabelsSchemaError: if the attributes violate the schema
        '''
        self.attrs.validate(attrs)

    def validate_frame_attribute_name(self, attr_name):
        '''Validates that the schema contains a frame-level attribute with the
        given name.

        Args:
            attr_name: the attribute name

        Raises:
            LabelsSchemaError: if the schema does not contain the attribute
        '''
        self.frames.validate_attribute_name(attr_name)

    def validate_frame_attribute(self, attr):
        '''Validates that the frame-level attribute is compliant with the
        schema.

        Args:
            attr: an Attribute

        Raises:
            LabelsSchemaError: if the attribute violates the schema
        '''
        self.frames.validate_attribute(attr)

    def validate_frame_attributes(self, attrs):
        '''Validates that the AttributeContainer of frame-level attributes is
        compliant with the schema.

        Args:
            attrs: an AttributeContainer

        Raises:
            LabelsSchemaError: if the attributes violate the schema
        '''
        self.frames.validate(attrs)

    def validate_object_label(self, label):
        '''Validates that the object label is compliant with the schema.

        Args:
            label: an object label

        Raises:
            LabelsSchemaError: if the object label violates the schema
        '''
        self.objects.validate_object_label(label)

    def validate_object_attribute(self, label, attr):
        '''Validates that the object-level attribute for the object with the
        given label is compliant with the schema.

        Args:
            label: an object label
            attr: an object-level Attribute

        Raises:
            LabelsSchemaError: if the attribute violates the schema
        '''
        self.objects.validate_object_attribute(label, attr)

    def validate_object_attributes(self, label, attrs):
        '''Validates that the AttributeContainer of object-level attributes for
        the object with the given label is compliant with the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer of object-level attributes

        Raises:
            LabelsSchemaError: if the attributes violate the schema
        '''
        self.objects.validate_object_attributes(label, attrs)

    def validate_object_frame_attribute(self, label, attr):
        '''Validates that the frame-level attribute for the object with the
        given label is compliant with the schema.

        Args:
            label: an object label
            attr: a frame-level Attribute

        Raises:
            LabelsSchemaError: if the attribute violates the schema
        '''
        self.objects.validate_frame_attribute(label, attr)

    def validate_object_frame_attributes(self, label, attrs):
        '''Validates that the AttributeContainer of frame-level attributes for
        the object with the given label is compliant with the schema.

        Args:
            label: an object label
            attrs: an AttributeContainer of frame-level attributes

        Raises:
            LabelsSchemaError: if the attributes violate the schema
        '''
        self.objects.validate_frame_attributes(label, attrs)

    def validate_object(self, obj):
        '''Validates that the object is compliant with the schema.

        Args:
            obj: a VideoObject or DetectedObject

        Raises:
            LabelsSchemaError: if the object violates the schema
        '''
        self.objects.validate_object(obj)

    def validate(self, event):
        '''Validates that the event is compliant with the schema.

        Args:
            event: a VideoEvent or DetectedEvent

        Raises:
            LabelsSchemaError: if the event violates the schema
        '''
        if isinstance(event, DetectedEvent):
            self._validate_detected_event(event)
        else:
            self._validate_video_event(event)

    def validate_subset_of_schema(self, schema):
        '''Validates that this schema is a subset of the given schema.

        Args:
            schema: an EventSchema

        Raises:
            LabelsSchemaError: if this schema is not a subset of the given
                schema
        '''
        self.validate_schema_type(schema)

        if self.label != schema.label:
            raise EventSchemaError(
                "Expected event label '%s'; found '%s'" %
                (schema.label, self.label))

        self.attrs.validate_subset_of_schema(schema.attrs)
        self.frames.validate_subset_of_schema(schema.frames)
        self.objects.validate_subset_of_schema(schema.objects)

    def merge_schema(self, schema):
        '''Merges the given EventSchema into this schema.

        Args:
            schema: an EventSchema
        '''
        self.validate_label(schema.label)
        self.attrs.merge_schema(schema.attrs)
        self.frames.merge_schema(schema.frames)
        self.objects.merge_schema(schema.objects)

    @classmethod
    def build_active_schema(cls, event, objects=None, events=None):
        '''Builds an EventSchema that describes the active schema of the given
        event.

        Args:
            event: a VideoEvent or DetectedEvent
            objects: an optional dictionary mapping uuids to `VideoObject`s. If
                provided, the child objects of this event will be incorporated
                into the schema
            events: an optional dictionary mapping uuids to `VideoEvent`s. If
                provided, the child events of this event will be incorporated
                into the schema

        Returns:
            an EventSchema
        '''
        schema = cls(event.label)
        schema.add_event(event)

        # @todo children...
        '''
        # Child objects
        if objects:
            for uuid in event.child_objects:
                if uuid in objects:
                    schema.add_object(objects[uuid])

        # Child events
        if events:
            for uuid in event.child_events:
                if uuid in events:
                    schema.add_event(events[uuid])
        '''

        return schema

    def attributes(self):
        '''Returns the list of class attributes that will be serialized.

        Returns:
            a list of attribute names
        '''
        _attrs = ["label"]
        if self.attrs:
            _attrs.append("attrs")
        if self.frames:
            _attrs.append("frames")
        if self.objects:
            _attrs.append("objects")
        return _attrs

    @classmethod
    def from_dict(cls, d):
        '''Constructs an EventSchema from a JSON dictionary.

        Args:
            d: a JSON dictionary

        Returns:
            an EventSchema
        '''
        attrs = d.get("attrs", None)
        if attrs is not None:
            attrs = etad.AttributeContainerSchema.from_dict(attrs)

        frames = d.get("frames", None)
        if frames is not None:
            frames = etad.AttributeContainerSchema.from_dict(frames)

        objects = d.get("objects", None)
        if objects is not None:
            objects = etao.ObjectContainerSchema.from_dict(objects)

        return cls(d["label"], attrs=attrs, frames=frames, objects=objects)

    def _add_detected_event(self, devent, validate_label=True):
        if validate_label:
            self.validate_label(devent.label)

        self.add_frame_attributes(devent.attrs)
        self.add_objects(devent.objects)

    def _add_video_event(self, event):
        self.validate_label(event.label)
        self.add_event_attributes(event.attrs)
        for devent in event.iter_detections():
            self._add_detected_event(devent, validate_label=False)

    def _validate_detected_event(self, event, validate_label=True):
        if validate_label:
            self.validate_label(event.label)

        self.validate_frame_attributes(event.attrs)
        for obj in event.objects:
            self.validate_object(obj)

    def _validate_video_event(self, event):
        self.validate_label(event.label)
        self.validate_event_attributes(event.attrs)
        for devent in event.iter_detections():
            self._validate_detected_event(devent, validate_label=False)

        # @todo children...
        '''
        # Validate child objects
        for obj in event.child_objects:
            self.validate_object(obj)

        # Validate child events
        for child_event in event.child_events:
            self.validate(child_event)
        '''


class EventSchemaError(etal.LabelsSchemaError):
    '''Error raised when an EventSchema is violated.'''
    pass


class EventContainerSchema(etal.LabelsContainerSchema):
    '''Schema for `VideoEventContainers`s and `DetectedEventContainer`s.

    Attributes:
        schema: a dictionary mapping event labels to EventSchema instances
    '''

    def __init__(self, schema=None):
        '''Creates an EventContainerSchema instance.

        Args:
            schema: (optional) a dictionary mapping event labels to EventSchema
                instances
        '''
        self.schema = schema or {}

    @property
    def is_empty(self):
        '''Whether this schema has no labels of any kind.'''
        return not bool(self.schema)

    def iter_event_labels(self):
        '''Returns an iterator over the event labels in this schema.

        Returns:
            an iterator over event labels
        '''
        return iter(self.schema)

    def iter_events(self):
        '''Returns an iterator over the (label, EventSchema) pairs in this
        schema.

        Returns:
            an iterator over (label, EventSchema) pairs
        '''
        return iteritems(self.schema)

    def has_event_label(self, label):
        '''Whether the schema has an event with the given label.

        Args:
            label: the event label

        Returns:
            True/False
        '''
        return label in self.schema

    def get_event_schema(self, label):
        '''Gets the EventSchema for the event with the given label.

        Args:
            label: the event label

        Returns:
            an EventSchema
        '''
        self.validate_event_label(label)
        return self.schema[label]

    def has_event_attribute(self, label, attr_name):
        '''Whether the schema has an event with the given label with an
        event-level attribute of the given name.

        Args:
            label: the event label
            attr_name: the name of the event-level attribute

        Returns:
            True/False
        '''
        if not self.has_event_label(label):
            return False

        return self.schema[label].has_event_attribute(attr_name)

    def get_event_attribute_schema(self, label, attr_name):
        '''Gets the AttributeSchema for the event-level attribute of the
        given name for the event with the given label.

        Args:
            label: the event label
            attr_name: the name of the event-level attribute

        Returns:
            the AttributeSchema
        '''
        event_schema = self.get_event_schema(label)
        return event_schema.get_event_attribute_schema(attr_name)

    def get_event_attribute_class(self, label, attr_name):
        '''Gets the Attribute class for the event-level attribute of the
        given name for the event with the given label.

        Args:
            label: the event label
            attr_name: the name of the event-level attribute

        Returns:
            the Attribute subclass
        '''
        self.validate_event_label(label)
        return self.schema[label].get_event_attribute_class(attr_name)

    def has_frame_attribute(self, label, attr_name):
        '''Whether the schema has an event with the given label with a
        frame-level attribute of the given name.

        Args:
            label: the event label
            attr_name: the name of the frame-level attribute

        Returns:
            True/False
        '''
        if not self.has_event_label(label):
            return False

        return self.schema[label].has_frame_attribute(attr_name)

    def get_frame_attribute_schema(self, label, attr_name):
        '''Gets the AttributeSchema for the frame-level attribute of the
        given name for the event with the given label.

        Args:
            label: the event label
            attr_name: the name of the frame-level attribute

        Returns:
            the AttributeSchema
        '''
        event_schema = self.get_event_schema(label)
        return event_schema.get_frame_attribute_schema(attr_name)

    def get_frame_attribute_class(self, label, attr_name):
        '''Gets the Attribute class for the frame-level attribute of the
        given name for the event with the given label.

        Args:
            label: the event label
            attr_name: the name of the frame-level attribute

        Returns:
            the Attribute subclass
        '''
        self.validate_event_label(label)
        return self.schema[label].get_frame_attribute_class(attr_name)

    def has_object_label(self, event_label, obj_label):
        '''Whether the schema has an event of the given label with an object
        of the given label.

        Args:
            event_label: the event label
            obj_label: the object label

        Returns:
            True/False
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].has_object_label(obj_label)

    def has_object_attribute(self, event_label, obj_label, attr_name):
        '''Whether the schema has an event of the given label with an object
        of the given label with an object-level attribute of the given name.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            True/False
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].has_object_attribute(
            obj_label, attr_name)

    def has_object_frame_attribute(self, event_label, obj_label, attr_name):
        '''Whether the schema has an event of the given label with an object
        of the given label with a frame-level attribute of the given name.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            True/False
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].has_frame_attribute(
            obj_label, attr_name)

    def get_object_schema(self, event_label, obj_label):
        '''Gets the ObjectSchema for the object with the given label from the
        event with the given label.

        Args:
            event_label: the event label
            obj_label: the object label

        Returns:
            the ObjectSchema
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].get_object_schema(obj_label)

    def get_object_attribute_schema(self, event_label, obj_label, attr_name):
        '''Gets the AttributeSchema for the object-level attribute of the
        given name for the object with the given label from the event with the
        given label.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            the AttributeSchema
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].get_object_attribute_schema(
            obj_label, attr_name)

    def get_object_frame_attribute_schema(
            self, event_label, obj_label, attr_name):
        '''Gets the AttributeSchema for the frame-level attribute of the
        given name for the object with the given label from the event with the
        given label.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            the AttributeSchema
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].get_object_attribute_schema(
            obj_label, attr_name)

    def get_object_attribute_class(self, event_label, obj_label, attr_name):
        '''Gets the Attribute class for the object-level attribute of the
        given name for the object with the given label from the event with the
        given label.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the object-level attribute

        Returns:
            the Attribute
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].get_object_attribute_class(
            obj_label, attr_name)

    def get_object_frame_attribute_class(
            self, event_label, obj_label, attr_name):
        '''Gets the Attribute class for the frame-level attribute of the
        given name for the object with the given label from the event with the
        given label.

        Args:
            event_label: the event label
            obj_label: the object label
            attr_name: the name of the frame-level attribute

        Returns:
            the Attribute
        '''
        self.validate_event_label(event_label)
        return self.schema[event_label].get_object_frame_attribute_class(
            obj_label, attr_name)

    def add_event_label(self, label):
        '''Adds the given event label to the schema.

        ArgsL:
            label: an event label
        '''
        self._ensure_has_event_label(label)

    def add_event_attribute(self, label, attr):
        '''Adds the event-level attribute for the event with the given label to
        the schema.

        Args:
            label: an event label
            attr: an event-level Attribute
        '''
        self._ensure_has_event_label(label)
        self.schema[label].add_event_attribute(attr)

    def add_event_attributes(self, label, attrs):
        '''Adds the AttributeContainer of event-level attributes for the
        event with the given label to the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of event-level attributes
        '''
        self._ensure_has_event_label(label)
        self.schema[label].add_event_attributes(attrs)

    def add_frame_attribute(self, label, attr):
        '''Adds the frame-level attribute for the event with the given label to
        the schema.

        Args:
            label: an event label
            attr: a frame-level Attribute
        '''
        self._ensure_has_event_label(label)
        self.schema[label].add_frame_attribute(attr)

    def add_frame_attributes(self, label, attrs):
        '''Adds the AttributeContainer of frame-level attributes for the
        event with the given label to the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of frame-level attributes
        '''
        self._ensure_has_event_label(label)
        self.schema[label].add_frame_attributes(attrs)

    def add_object_label(self, event_label, obj_label):
        '''Adds the given object label for the event with the given label to
        the schema.

        Args:
            event_label: an event label
            obj_label: an object label
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object_label(obj_label)

    def add_object_attribute(self, event_label, obj_label, attr):
        '''Adds the object-level attribute for the object with the given label
        to the event with the given label to the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: an object-level Attribute
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object_attribute(obj_label, attr)

    def add_object_frame_attribute(self, event_label, obj_label, attr):
        '''Adds the frame-level attribute for the object with the given label
        to the event with the given label to the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: a frame-level Attribute
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object_frame_attribute(obj_label, attr)

    def add_object_attributes(self, event_label, obj_label, attrs):
        '''Adds the AttributeContainer of object-level attributes for the
        object with the given label to the event with the given label to the
        schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of object-level attributes
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object_attributes(obj_label, attrs)

    def add_object_frame_attributes(self, event_label, obj_label, attrs):
        '''Adds the AttributeContainer of frame-level attributes for the
        object with the given label to the event with the given label to the
        schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of frame-level attributes
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object_frame_attributes(obj_label, attrs)

    def add_object(self, event_label, obj):
        '''Adds the object to the event with the given label to the schema.

        Args:
            event_label: an event label
            obj: a VideoObject or DetectedObject
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_object(obj)

    def add_objects(self, event_label, objects):
        '''Adds the objects to the event with the given label to the schema.

        Args:
            event_label: an event label
            objects: a VideoObjectContainer or DetectedObjectContainer
        '''
        self._ensure_has_event_label(event_label)
        self.schema[event_label].add_objects(objects)

    def add_event(self, event):
        '''Adds the event to the schema.

        Args:
            event: a VideoEvent
        '''
        self._ensure_has_event_label(event.label)
        self.schema[event.label].add_event(event)

    def add_events(self, events):
        '''Adds the event to the schema.

        Args:
            events: a VideoEventContainer or DetectedEventContainer
        '''
        for event in events:
            self.add_event(event)

    def is_valid_event_label(self, label):
        '''Whether the event label is compliant with the schema.

        Args:
            label: an event label

        Returns:
            True/False
        '''
        try:
            self.validate_event_label(label)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_event_attribute(self, label, attr):
        '''Whether the event-level attribute for the event with the given label
        is compliant with the schema.

        Args:
            label: an event label
            attr: an event-level Attribute

        Returns:
            True/False
        '''
        try:
            self.validate_event_attribute(label, attr)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_event_attributes(self, label, attrs):
        '''Whether the AttributeContainer of event-level attributes for the
        event with the given label is compliant with the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of event-level attributes

        Returns:
            True/False
        '''
        try:
            self.validate_event_attributes(label, attrs)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_frame_attribute(self, label, attr):
        '''Whether the frame-level attribute for the event with the given label
        is compliant with the schema.

        Args:
            label: an event label
            attr: a frame-level Attribute

        Returns:
            True/False
        '''
        try:
            self.validate_frame_attribute(label, attr)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_frame_attributes(self, label, attrs):
        '''Whether the AttributeContainer of frame-level attributes for the
        event with the given label is compliant with the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of frame-level attributes

        Returns:
            True/False
        '''
        try:
            self.validate_frame_attributes(label, attrs)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object_label(self, event_label, obj_label):
        '''Whether the object label for the event with the given label is
        compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label

        Returns:
            True/False
        '''
        try:
            self.validate_object_label(event_label, obj_label)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object_attribute(self, event_label, obj_label, attr):
        '''Whether the object-level attribute for the object with the given
        label for the event with the given label is compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: an object-level Attribute

        Returns:
            True/False
        '''
        try:
            self.validate_object_attribute(event_label, obj_label, attr)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object_attributes(self, event_label, obj_label, attrs):
        '''Whether the AttributeContainer of object-level attributes for the
        object with the given label for the event with the given label is
        compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of object-level attributes

        Returns:
            True/False
        '''
        try:
            self.validate_object_attributes(event_label, obj_label, attrs)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object_frame_attribute(self, event_label, obj_label, attr):
        '''Whether the frame-level attribute for the object with the given
        label for the event with the given label is compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: a frame-level Attribute

        Returns:
            True/False
        '''
        try:
            self.validate_object_frame_attribute(event_label, obj_label, attr)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object_frame_attributes(self, event_label, obj_label, attrs):
        '''Whether the AttributeContainer of frame-level attributes for the
        object with the given label for the event with the given label is
        compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of frame-level attributes

        Returns:
            True/False
        '''
        try:
            self.validate_object_frame_attributes(
                event_label, obj_label, attrs)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_object(self, event_label, obj):
        '''Whether the object for the event with the given label is compliant
        with the schema.

        Args:
            event_label: an event label
            obj: a VideoObject or DetectedObject

        Returns:
            True/False
        '''
        try:
            self.validate_object(event_label, obj)
            return True
        except etal.LabelsSchemaError:
            return False

    def is_valid_event(self, event):
        '''Whether the event is compliant with the schema.

        Args:
            event: a VideoEvent or DetectedEvent

        Returns:
            True/False
        '''
        try:
            self.validate_event(event)
            return True
        except etal.LabelsSchemaError:
            return False

    def validate_event_label(self, label):
        '''Validates that the event label is compliant with the schema.

        Args:
            label: an event label

        Raises:
            LabelsSchemaError: if the label is not compliant with the schema
        '''
        if label not in self.schema:
            raise EventContainerSchemaError(
                "Event label '%s' is not allowed by the schema" % label)

    def validate_event_attribute(self, label, attr):
        '''Validates that the event-level attribute for the given label is
        compliant with the schema.

        Args:
            label: an event label
            attr: an event-level Attribute

        Raises:
            LabelsSchemaError: if the attribute is not compliant with the
                schema
        '''
        self.validate_event_label(label)
        self.schema[label].validate_event_attribute(attr)

    def validate_event_attributes(self, label, attrs):
        '''Validates that the AttributeContainer of event-level attributes for
        the given label is compliant with the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of event-level attributes

        Raises:
            LabelsSchemaError: if the attributes are not compliant with the
                schema
        '''
        self.validate_event_label(label)
        self.schema[label].validate_event_attributes(attrs)

    def validate_frame_attribute(self, label, attr):
        '''Validates that the frame-level attribute for the given label is
        compliant with the schema.

        Args:
            label: an event label
            attr: a frame-level Attribute

        Raises:
            LabelsSchemaError: if the attribute is not compliant with the
                schema
        '''
        self.validate_event_label(label)
        self.schema[label].validate_frame_attribute(attr)

    def validate_frame_attributes(self, label, attrs):
        '''Validates that the AttributeContainer of frame-level attributes for
        the given label is compliant with the schema.

        Args:
            label: an event label
            attrs: an AttributeContainer of frame-level attributes

        Raises:
            LabelsSchemaError: if the attributes are not compliant with the
                schema
        '''
        self.validate_event_label(label)
        self.schema[label].validate_frame_attributes(attrs)

    def validate_object_label(self, event_label, obj_label):
        '''Validates that the object label for the event with the given label
        is compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label

        Raises:
            LabelsSchemaError: if the obect label is not compliant with the
                schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object_label(obj_label)

    def validate_object_attribute(self, event_label, obj_label, attr):
        '''Validates that the object-level attribute for the object with the
        given label for the event with the given label is compliant with the
        schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: an object-level Attribute

        Raises:
            LabelsSchemaError: if the attribute is not compliant with the
                schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object_attribute(obj_label, attr)

    def validate_object_attributes(self, event_label, obj_label, attrs):
        '''Validates that the AttributeContainer of object-level attributes for
        the object with the given label for the event with the given label is
        compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of object-level attributes

        Raises:
            LabelsSchemaError: if the attributes are not compliant with the
                schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object_attributes(obj_label, attrs)

    def validate_object_frame_attribute(self, event_label, obj_label, attr):
        '''Validates that the frame-level attribute for the object with the
        given label for the event with the given label is compliant with the
        schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attr: a frame-level Attribute

        Raises:
            LabelsSchemaError: if the attribute is not compliant with the
                schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object_frame_attribute(
            obj_label, attr)

    def validate_object_frame_attributes(self, event_label, obj_label, attrs):
        '''Validates that the AttributeContainer of frame-level attributes for
        the object with the given label for the event with the given label is
        compliant with the schema.

        Args:
            event_label: an event label
            obj_label: an object label
            attrs: an AttributeContainer of frame-level attributes

        Raises:
            LabelsSchemaError: if the attribute is not compliant with the
                schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object_frame_attributes(
            obj_label, attrs)

    def validate_object(self, event_label, obj):
        '''Validates that the object for the given event label is compliant
        with the schema.

        Args:
            event_label: an event label
            obj: a VideoObject or DetectedObject

        Raises:
            LabelsSchemaError: if the object is not compliant with the schema
        '''
        self.validate_event_label(event_label)
        self.schema[event_label].validate_object(obj)

    def validate_event(self, event):
        '''Validates that the event is compliant with the schema.

        Args:
            event: a VideoEvent or DetectedEvent

        Raises:
            LabelsSchemaError: if the event is not compliant with the schema
        '''
        self.validate_event_label(event.label)
        self.schema[event.label].validate(event)

    def validate(self, events):
        '''Validates that the event is compliant with the schema.

        Args:
            events: a VideoEventContainer or DetectedEventContainer

        Raises:
            LabelsSchemaError: if the events are not compliant with the schema
        '''
        for event in events:
            self.validate_event(event)

    def validate_subset_of_schema(self, schema):
        '''Validates that this schema is a subset of the given schema.

        Args:
            schema: an EventContainerSchema

        Raises:
            LabelsSchemaError: if this schema is not a subset of the given
                schema
        '''
        self.validate_schema_type(schema)

        for label, event_schema in iteritems(self.schema):
            if not schema.has_event_label(label):
                raise EventContainerSchemaError(
                    "Event label '%s' does not appear in schema" % label)

            other_event_schema = schema.get_event_schema(label)
            event_schema.validate_subset_of_schema(other_event_schema)

    def merge_event_schema(self, event_schema):
        '''Merges the given `EventSchema` into the schema.

        Args:
            event_schema: an EventSchema
        '''
        label = event_schema.label
        self._ensure_has_event_label(label)
        self.schema[label].merge_schema(event_schema)

    def merge_schema(self, schema):
        '''Merges the given EventContainerSchema into this schema.

        Args:
            schema: an EventContainerSchema
        '''
        for _, event_schema in schema.iter_events():
            self.merge_event_schema(event_schema)

    @classmethod
    def build_active_schema(cls, events):
        '''Builds an EventContainerSchema that describes the active schema of
        the events.

        Args:
            events: a VideoEventContainer or DetectedEventContainer

        Returns:
            an EventContainerSchema
        '''
        schema = cls()
        schema.add_events(events)
        return schema

    @classmethod
    def from_dict(cls, d):
        '''Constructs an EventContainerSchema from a JSON dictionary.

        Args:
            d: a JSON dictionary

        Returns:
            an EventContainerSchema
        '''
        schema = d.get("schema", None)
        if schema is not None:
            schema = {
                label: EventSchema.from_dict(esd)
                for label, esd in iteritems(schema)
            }

        return cls(schema=schema)

    def _ensure_has_event_label(self, label):
        if not self.has_event_label(label):
            self.schema[label] = EventSchema(label)


class EventContainerSchemaError(etal.LabelsContainerSchemaError):
    '''Error raised when an EventContainerSchema is violated.'''
    pass


class VideoEventFrameRenderer(etal.LabelsFrameRenderer):
    '''Class for rendering labels for a VideoEvent at the frame-level.'''

    def __init__(self, event):
        '''Creates an VideoEventFrameRenderer instance.

        Args:
            event: a VideoEvent
        '''
        self._event = event

    def render_frame(self, frame_number):
        '''Renders the VideoEvent for the given frame.

        Args:
            frame_number: the frame number

        Returns:
            a DetectedEvent, or None if no labels exist for the given frame
        '''
        if frame_number not in self._event.support:
            return None

        event_attrs = self._get_event_attrs()
        dobjs = self._render_object_frame(frame_number)
        return self._render_frame(frame_number, event_attrs, dobjs)

    def render_all_frames(self):
        '''Renders the VideoEvent for all possible frames.

        Returns:
            a dictionary mapping frame numbers to DetectedEvent instances
        '''
        event_attrs = self._get_event_attrs()
        dobjs_map = self._render_all_object_frames()

        devents_map = {}
        for frame_number in self._event.support:
            dobjs = dobjs_map.get(frame_number, None)
            devents_map[frame_number] = self._render_frame(
                frame_number, event_attrs, dobjs)

        return devents_map

    def _render_frame(self, frame_number, event_attrs, dobjs):
        # Base DetectedEvent
        if frame_number in self._event.frames:
            devent = deepcopy(self._event.frames[frame_number])
        else:
            devent = DetectedEvent(frame_number=frame_number)

        # Render event-level attributes
        if event_attrs is not None:
            # Prepend event-level attributes
            devent.attrs.prepend_container(event_attrs)

        # Render objects
        if dobjs is not None:
            devent.add_objects(dobjs)

        # Inherit available event-level metadata
        if self._event.label is not None:
            devent.label = self._event.label
        if self._event.confidence is not None:
            devent.confidence = self._event.confidence
        if self._event.index is not None:
            devent.index = self._event.index

        return devent

    def _get_event_attrs(self):
        if not self._event.has_event_attributes:
            return None

        return deepcopy(self._event.attrs)

    def _render_all_object_frames(self):
        if not self._event.has_video_objects:
            return {}

        r = etao.VideoObjectContainerFrameRenderer(self._event.objects)
        return r.render_all_frames()

    def _render_object_frame(self, frame_number):
        if not self._event.has_video_objects:
            return None

        r = etao.VideoObjectContainerFrameRenderer(self._event.objects)
        return r.render_frame(frame_number)


class VideoEventContainerFrameRenderer(etal.LabelsContainerFrameRenderer):
    '''Class for rendering labels for a VideoEventContainer at the frame-level.
    '''

    _FRAME_CONTAINER_CLS = DetectedEventContainer
    _ELEMENT_RENDERER_CLS = VideoEventFrameRenderer

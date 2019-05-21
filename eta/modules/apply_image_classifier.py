#!/usr/bin/env python
'''
A module that uses an `eta.core.learning.ImageClassifier` to classify images
or the frames of videos.

Info:
    type: eta.core.types.Module
    version: 0.1.0

Copyright 2017-2019, Voxel51, Inc.
voxel51.com

Brian Moore, brian@voxel51.com
'''
# pragma pylint: disable=redefined-builtin
# pragma pylint: disable=unused-wildcard-import
# pragma pylint: disable=wildcard-import
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import *
# pragma pylint: enable=redefined-builtin
# pragma pylint: enable=unused-wildcard-import
# pragma pylint: enable=wildcard-import

import logging
import os
import sys

from eta.core.config import Config, ConfigError
import eta.core.image as etai
import eta.core.learning as etal
import eta.core.module as etam
import eta.core.utils as etau
import eta.core.video as etav


logger = logging.getLogger(__name__)


class ApplyImageClassifierConfig(etam.BaseModuleConfig):
    '''Module configuration settings.

    Attributes:
        data (DataConfig)
        parameters (ParametersConfig)
    '''

    def __init__(self, d):
        super(ApplyImageClassifierConfig, self).__init__(d)
        self.data = self.parse_object_array(d, "data", DataConfig)
        self.parameters = self.parse_object(d, "parameters", ParametersConfig)


class DataConfig(Config):
    '''Data configuration settings.

    Inputs:
        video_path (eta.core.types.Video): [None] the input video
        input_labels_path (eta.core.types.VideoLabels): [None] an optional
            input VideoLabels file to which to add the predictions generated by
            processing `video_path`
        image_path (eta.core.types.Image): [None] the input image
        input_image_labels_path (eta.core.types.ImageLabels): [None] an
            optional input ImageLabels files to which to add the predictions
            generated by processing `image_path`
        images_dir (eta.core.types.ImageFileDirectory): [None] an input
            directory of images
        input_image_set_labels_path (eta.core.types.ImageSetLabels): [None] an
            optional input ImageSetLabels file to which to add the predictions
            generated by processing `images_dir`

    Outputs:
        output_labels_path (eta.core.types.VideoLabels): [None] a VideoLabels
            file containing the predictions generated by processing
            `video_path`
        output_image_labels_path (eta.core.types.ImageLabels): [None] an
            ImageLabels file containing the predictions generated by
            processing `image_path`
        output_image_set_labels_path (eta.core.types.ImageSetLabels): [None] an
            ImageSetLabels file containing the predictions generated by
            processing `images_dir`
    '''

    def __init__(self, d):
        self.video_path = self.parse_string(d, "video_path", default=None)
        self.input_labels_path = self.parse_string(
            d, "input_labels_path", default=None)
        self.output_labels_path = self.parse_string(
            d, "output_labels_path", default=None)
        self.image_path = self.parse_string(d, "image_path", default=None)
        self.input_image_labels_path = self.parse_string(
            d, "input_image_labels_path", default=None)
        self.output_image_labels_path = self.parse_string(
            d, "output_image_labels_path", default=None)
        self.images_dir = self.parse_string(d, "images_dir", default=None)
        self.input_image_set_labels_path = self.parse_string(
            d, "input_image_set_labels_path", default=None)
        self.output_image_set_labels_path = self.parse_string(
            d, "output_image_set_labels_path", default=None)

        self._validate()

    def _validate(self):
        if self.video_path:
            if not self.output_labels_path:
                raise ConfigError(
                    "`output_labels_path` is required when `video_path` is "
                    "set")

        if self.image_path:
            if not self.output_image_labels_path:
                raise ConfigError(
                    "`output_image_labels_path` is required when `image_path` "
                    "is set")

        if self.images_dir:
            if not self.output_image_set_labels_path:
                raise ConfigError(
                    "`output_image_set_labels_path` is required when "
                    "`images_dir` is set")


class ParametersConfig(Config):
    '''Parameter configuration settings.

    Parameters:
        classifier (eta.core.types.ImageClassifier): an
            `eta.core.learning.ImageClassifierConfig` describing the
            `eta.core.learning.ImageClassifier` to use
        confidence_threshold (eta.core.types.Number): [None] a confidence
            threshold to use when assigning labels
    '''

    def __init__(self, d):
        self.classifier = self.parse_object(
            d, "classifier", etal.ImageClassifierConfig)
        self.confidence_threshold = self.parse_number(
            d, "confidence_threshold", default=None)


def _build_attribute_filter(threshold):
    if threshold is None:
        logger.info("Predicting all attributes")
        filter_fcn = lambda attrs: attrs
    else:
        logger.info("Returning predictions with confidence >= %f", threshold)
        attr_filters = [
            lambda attr: attr.confidence is None
            or attr.confidence > float(threshold)
        ]
        filter_fcn = lambda attrs: attrs.get_matches(attr_filters)

    return filter_fcn


def _apply_image_classifier(config):
    # Build classifier
    classifier = config.parameters.classifier.build()
    logger.info("Loaded classifier %s", type(classifier))

    # Build attribute filter
    attr_filter = _build_attribute_filter(
        config.parameters.confidence_threshold)

    # Process videos
    with classifier:
        for data in config.data:
            if data.video_path:
                logger.info("Processing video '%s'", data.video_path)
                _process_video(data, classifier, attr_filter)
            if data.image_path:
                logger.info("Processing image '%s'", data.image_path)
                _process_image(data, classifier, attr_filter)
            if data.images_dir:
                logger.info("Processing image directory '%s'", data.images_dir)
                _process_images_dir(data, classifier, attr_filter)


def _process_video(data, classifier, attr_filter):
    # Load labels
    if data.input_labels_path:
        logger.info(
            "Reading existing labels from '%s'", data.input_labels_path)
        video_labels = etav.VideoLabels.from_json(data.input_labels_path)
    else:
        video_labels = etav.VideoLabels()

    # Classify frames of video
    with etav.FFmpegVideoReader(data.video_path) as vr:
        for img in vr:
            logger.debug("Processing frame %d", vr.frame_number)

            # Classify frame
            attrs = attr_filter(classifier.predict(img))
            video_labels.add_frame_attributes(attrs, vr.frame_number)

    logger.info("Writing labels to '%s'", data.output_labels_path)
    video_labels.write_json(data.output_labels_path)


def _process_image(data, classifier, attr_filter):
    # Load labels
    if data.input_image_labels_path:
        logger.info(
            "Reading existing labels from '%s'", data.input_image_labels_path)
        image_labels = etai.ImageLabels.from_json(data.input_image_labels_path)
    else:
        image_labels = etai.ImageLabels()

    # Classsify image
    img = etai.read(data.image_path)
    attrs = attr_filter(classifier.predict(img))
    image_labels.add_image_attributes(attrs)

    logger.info("Writing labels to '%s'", data.output_image_labels_path)
    image_labels.write_json(data.output_image_labels_path)


def _process_images_dir(data, classifier, attr_filter):
    # Load labels
    if data.input_image_set_labels_path:
        logger.info(
            "Reading existing labels from '%s'",
            data.input_image_set_labels_path)
        image_set_labels = etai.ImageSetLabels.from_json(
            data.input_image_set_labels_path)
    else:
        image_set_labels = etai.ImageSetLabels()

    # Classify images in directory
    for filename in etau.list_files(data.images_dir):
        inpath = os.path.join(data.images_dir, filename)
        logger.info("Processing image '%s'", inpath)

        # Classify image
        img = etai.read(inpath)
        attrs = attr_filter(classifier.predict(img))
        image_set_labels[filename].add_image_attributes(attrs)

    logger.info("Writing labels to '%s'", data.output_image_set_labels_path)
    image_set_labels.write_json(data.output_image_set_labels_path)


def run(config_path, pipeline_config_path=None):
    '''Run the apply_image_classifier module.

    Args:
        config_path: path to a ApplyImageClassifierConfig file
        pipeline_config_path: optional path to a PipelineConfig file
    '''
    config = ApplyImageClassifierConfig.from_json(config_path)
    etam.setup(config, pipeline_config_path=pipeline_config_path)
    _apply_image_classifier(config)


if __name__ == "__main__":
    run(*sys.argv[1:])
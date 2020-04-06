#!/usr/bin/env python
'''
A module that applies an `eta.core.learning.ImageSemanticSegmenter` to images
or the frames of a video.

Info:
    type: eta.core.types.Module
    version: 0.1.0

Copyright 2017-2020, Voxel51, Inc.
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


class ApplyImageSemanticSegmenterConfig(etam.BaseModuleConfig):
    '''Module configuration settings.

    Attributes:
        data (DataConfig)
        parameters (ParametersConfig)
    '''

    def __init__(self, d):
        super(ApplyImageSemanticSegmenterConfig, self).__init__(d)
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
        segmenter (eta.core.types.ImageSemanticSegmenter): an
            `eta.core.learning.ImageSemanticSegmenterConfig` describing the
            `eta.core.learning.ImageSemanticSegmenter` to use
        store_mask_index (eta.core.types.Boolean): [False] whether to store the
            MaskIndex of the segmenter in the output labels
    '''

    def __init__(self, d):
        self.segmenter = self.parse_object(
            d, "segmenter", etal.ImageSemanticSegmenterConfig)
        self.store_mask_index = self.parse_bool(
            d, "store_mask_index", default=False)


def _apply_image_semantic_segmenter(config):
    # Build segmenter
    segmenter = config.parameters.segmenter.build()
    logger.info("Loaded segmenter %s", type(segmenter))

    store_mask_index = config.parameters.store_mask_index
    if store_mask_index:
        etal.ExposesMaskIndex.ensure_exposes_mask_index(segmenter)

    # Process videos
    with segmenter:
        for data in config.data:
            if data.video_path:
                logger.info("Processing video '%s'", data.video_path)
                _process_video(data, segmenter, store_mask_index)
            if data.image_path:
                logger.info("Processing image '%s'", data.image_path)
                _process_image(data, segmenter, store_mask_index)
            if data.images_dir:
                logger.info("Processing image directory '%s'", data.images_dir)
                _process_images_dir(data, segmenter, store_mask_index)


def _process_video(data, segmenter, store_mask_index):
    # Load labels
    if data.input_labels_path:
        logger.info(
            "Reading existing labels from '%s'", data.input_labels_path)
        video_labels = etav.VideoLabels.from_json(data.input_labels_path)
    else:
        video_labels = etav.VideoLabels()

    # Apply segmenter to frames of video
    with etav.FFmpegVideoReader(data.video_path) as vr:
        for img in vr:
            logger.debug("Processing frame %d", vr.frame_number)

            # Segment frame
            image_labels = segmenter.segment(img)
            frame_labels = etav.VideoFrameLabels.from_image_labels(
                image_labels, vr.frame_number)
            video_labels.add_frame(frame_labels, overwrite=False)

    # Store MaskIndex, if requested
    if store_mask_index:
        video_labels.mask_index = segmenter.get_mask_index()

    logger.info("Writing labels to '%s'", data.output_labels_path)
    video_labels.write_json(data.output_labels_path)


def _process_image(data, segmenter, store_mask_index):
    # Load labels
    if data.input_image_labels_path:
        logger.info(
            "Reading existing labels from '%s'", data.input_image_labels_path)
        image_labels = etai.ImageLabels.from_json(data.input_image_labels_path)
    else:
        image_labels = etai.ImageLabels()

    # Segment image
    img = etai.read(data.image_path)
    image_labels.merge_labels(segmenter.segment(img))

    # Store MaskIndex, if requested
    if store_mask_index:
        image_labels.mask_index = segmenter.get_mask_index()

    logger.info("Writing labels to '%s'", data.output_image_labels_path)
    image_labels.write_json(data.output_image_labels_path)


def _process_images_dir(data, segmenter, store_mask_index):
    # Load labels
    if data.input_image_set_labels_path:
        logger.info(
            "Reading existing labels from '%s'",
            data.input_image_set_labels_path)
        image_set_labels = etai.ImageSetLabels.from_json(
            data.input_image_set_labels_path)
    else:
        image_set_labels = etai.ImageSetLabels()

    # Segment images in directory
    for filename in etau.list_files(data.images_dir):
        inpath = os.path.join(data.images_dir, filename)
        logger.info("Processing image '%s'", inpath)

        # Segment image
        img = etai.read(inpath)
        image_labels = segmenter.segment(img)
        image_set_labels[filename].merge_labels(image_labels)

    # Store MaskIndex, if requested
    if store_mask_index:
        mask_index = segmenter.get_mask_index()
        for image_labels in image_set_labels:
            image_labels.mask_index = mask_index

    logger.info("Writing labels to '%s'", data.output_image_set_labels_path)
    image_set_labels.write_json(data.output_image_set_labels_path)


def run(config_path, pipeline_config_path=None):
    '''Run the apply_image_semantic_segmenter module.

    Args:
        config_path: path to a ApplyImageSemanticSegmenterConfig file
        pipeline_config_path: optional path to a PipelineConfig file
    '''
    config = ApplyImageSemanticSegmenterConfig.from_json(config_path)
    etam.setup(config, pipeline_config_path=pipeline_config_path)
    _apply_image_semantic_segmenter(config)


if __name__ == "__main__":
    run(*sys.argv[1:])

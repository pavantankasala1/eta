#!/usr/bin/env python
'''
A module for formatting videos.

Info:
    type: eta.core.types.Module
    version: 0.1.0

Copyright 2017-2020, Voxel51, Inc.
voxel51.com
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
import sys

from eta.core.config import Config
import eta.core.image as etai
import eta.core.module as etam
import eta.core.numutils as etan
import eta.core.utils as etau
import eta.core.video as etav
import eta.core.ziputils as etaz


logger = logging.getLogger(__name__)


class FormatVideosConfig(etam.BaseModuleConfig):
    '''Format videos configuration settings.

    Attributes:
        data (DataConfig)
        parameters (ParametersConfig)
    '''

    def __init__(self, d):
        super(FormatVideosConfig, self).__init__(d)
        self.data = self.parse_object_array(d, "data", DataConfig)
        self.parameters = self.parse_object(d, "parameters", ParametersConfig)


class DataConfig(Config):
    '''Data configuration settings.

    Inputs:
        input_path (eta.core.types.Video): [None] The input video
        input_zip (eta.core.types.ZippedVideoFileDirectory): [None] A zip file
            containing a directory of input video files

    Outputs:
        output_video_path (eta.core.types.VideoFile): [None] The formatted
            video file
        output_frames_dir (eta.core.types.ImageSequenceDirectory): [None] A
            directory of formatted frames
        output_frames_path (eta.core.types.ImageSequence): [None] The output
            formatted frames pattern
        output_zip (eta.core.types.ZippedVideoFileDirectory): [None] A zip file
            containing a directory of formatted video files
    '''

    def __init__(self, d):
        self.input_path = self.parse_string(d, "input_path", default=None)
        self.input_zip = self.parse_string(d, "input_zip", default=None)
        self.output_video_path = self.parse_string(
            d, "output_video_path", default=None)
        self.output_frames_dir = self.parse_string(
            d, "output_frames_dir", default=None)
        self.output_frames_path = self.parse_string(
            d, "output_frames_path", default=None)
        self.output_zip = self.parse_string(d, "output_zip", default=None)

        self._output_field = None
        self._output_val = None
        self._parse_outputs()

    @property
    def is_zip(self):
        return self.input_zip and self.output_zip

    @property
    def output_field(self):
        return self._output_field

    @property
    def output_path(self):
        return self._output_val

    def _parse_outputs(self):
        if self.is_zip:
            self._output_field = "output_zip"
            self._output_val = self.output_zip
            return

        field, val = Config.parse_mutually_exclusive_fields({
            "output_video_path": self.output_video_path,
            "output_frames_dir": self.output_frames_dir,
            "output_frames_path": self.output_frames_path,
        })
        if field == "output_frames_dir":
            val = etai.make_image_sequence_patt(val)
        self._output_field = field
        self._output_val = val


class ParametersConfig(Config):
    '''Parameter configuration settings.

    Parameters:
        fps (eta.core.types.Number): [None] The output frame rate
        max_fps (eta.core.types.Number): [None] The maximum frame rate allowed
            for the output video
        scale (eta.core.types.Number): [None] A numeric scale factor to apply
            to the input resolution
        size (eta.core.types.Array): [None] A desired output (width, height)
            of the video. Dimensions can be -1, in which case the input aspect
            ratio is preserved
        max_size (eta.core.types.Array): [None] A maximum (width, height)
            allowed for the video. Dimensions can be -1, in which case no
            constraint is applied to them
        ffmpeg_out_opts (eta.core.types.Array): [None] An array of ffmpeg
            output options
    '''

    def __init__(self, d):
        self.fps = self.parse_number(d, "fps", default=None)
        self.max_fps = self.parse_number(d, "max_fps", default=None)
        self.scale = self.parse_number(d, "scale", default=None)
        self.size = self.parse_array(d, "size", default=None)
        self.max_size = self.parse_array(d, "max_size", default=None)
        self.ffmpeg_out_opts = self.parse_array(
            d, "ffmpeg_out_opts", default=None)


def _format_videos(config):
    parameters = config.parameters

    for data in config.data:
        if data.is_zip:
            _process_zip(data.input_zip, data.output_zip, parameters)
        else:
            _process_video(data.input_path, data.output_path, parameters)


def _process_zip(input_zip, output_zip, parameters):
    input_paths = etaz.extract_zip(input_zip)
    output_paths = etaz.make_parallel_files(output_zip, input_paths)

    # Iterate over videos
    for input_path, output_path in zip(input_paths, output_paths):
        _process_video(input_path, output_path, parameters)

    # Collect outputs
    etaz.make_zip(output_zip)


def _process_video(input_path, output_path, parameters):
    # Parse parameters
    fps = parameters.fps
    max_fps = parameters.max_fps
    scale = parameters.scale
    size = parameters.size
    max_size = parameters.max_size
    ffmpeg_out_opts = parameters.ffmpeg_out_opts

    # Get video metadata, logging generously
    video_metadata = etav.VideoMetadata.build_for(input_path, verbose=True)

    ifps = video_metadata.frame_rate
    isize = video_metadata.frame_size

    # Compute output frame rate
    ofps = fps or -1
    max_fps = max_fps or -1
    if ofps < 0:
        logger.info("Defaulting to the input frame rate of %s", ifps)
        ofps = ifps
    if 0 < max_fps < ofps:
        logger.info("Capping the frame rate at %s", max_fps)
        ofps = max_fps

    # Compute output frame size
    if scale:
        osize = etai.scale_frame_size(isize, scale)
    elif size:
        psize = etai.parse_frame_size(size)
        osize = etai.infer_missing_dims(psize, isize)
    else:
        osize = isize

    # Apply size limit, if requested
    if max_size:
        msize = etai.parse_frame_size(max_size)
        osize = etai.clamp_frame_size(osize, msize)

    # Handle no-ops efficiently
    same_fps = ifps == ofps
    same_size = osize == isize
    same_format = etav.is_same_video_file_format(input_path, output_path)
    if same_fps and same_size and same_format:
        logger.info(
            "Same frame rate, frame size, and video format detected, so no "
            "computation is required. Just symlinking %s to %s",
            output_path, input_path)
        etau.symlink_file(input_path, output_path)
        return

    # ffmpeg requires that height/width be even
    osize = [etan.round_to_even(x) for x in osize]

    #
    # Format video
    #

    logger.info("Formatting video '%s'", input_path)
    if not same_fps:
        logger.info("*** resampling at frame rate %s", ofps)
    else:
        ofps = None  # omit unused argument

    if not same_size:
        logger.info("*** resizing to %s", str(osize))
    else:
        osize = None  # omit unused argument

    ffmpeg = etav.FFmpeg(fps=ofps, size=osize, out_opts=ffmpeg_out_opts)
    ffmpeg.run(input_path, output_path)


def run(config_path, pipeline_config_path=None):
    '''Run the format_videos module.

    Args:
        config_path: path to a FormatVideosConfig file
        pipeline_config_path: optional path to a PipelineConfig file
    '''
    config = FormatVideosConfig.from_json(config_path)
    etam.setup(config, pipeline_config_path=pipeline_config_path)
    _format_videos(config)


if __name__ == "__main__":
    run(*sys.argv[1:])

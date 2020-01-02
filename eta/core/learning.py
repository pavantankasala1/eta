'''
Core infrastructure for deploying ML models.

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

import numpy as np

from eta.core.config import Config, ConfigError, Configurable
import eta.core.models as etam
import eta.core.utils as etau


logger = logging.getLogger(__name__)


def load_labels_map(labels_map_path):
    '''Loads the labels map from the given path.

    The labels mmap must be in the following plain text format:

    ```
    1:label1
    2:label2
    3:label3
    ...
    ```

    The indexes are irrelevant to this function, they can be in any order and
    can start from zero, one, or another number.

    Args:
        labels_map_path: the path to a labels map file

    Returns:
        a dictionary mapping indexes to label strings
    '''
    labels_map = {}
    with open(labels_map_path, "r") as f:
        for line in f:
            idx, label = line.split(":")
            labels_map[int(idx)] = label.strip()
    return labels_map


def write_labels_map(labels_map, outpath):
    '''Writes the labels map to disk.

    Labels maps are written to disk in the following plain text format:

    ```
    1:label1
    2:label2
    3:label3
    ...
    ```

    The indexes are irrelevant to this function, they can be in any order and
    can start from zero, one, or another number. They are, however, written
    to disk in sorted (increasing) order.

    Args:
        labels_map: the labels map dictionary
        outpath: the output path
    '''
    with open(outpath, "w") as f:
        for idx in sorted(labels_map):
            f.write("%s:%s\n" % (idx, labels_map[idx]))


def get_class_labels(labels_map):
    '''Returns the list of class labels from the given labels map.

    Args:
        a dictionary mapping indexes to label strings

    Returns:
        a list of class labels
    '''
    return [labels_map[k] for k in sorted(labels_map.keys())]


def has_default_deployment_model(model_name):
    '''Determines whether the model with the given name has a default
    deployment.

    The model must be findable via `eta.core.models.get_model(model_name)`.

    Args:
        model_name: the name of the model, which can have "@<ver>" appended to
            refer to a specific version of the model. If no version is
            specified, the latest version of the model is assumed

    Returns:
        True/False whether the model has a default deployment
    '''
    model = etam.get_model(model_name)
    return model.default_deployment_config_dict is not None


def load_default_deployment_model(model_name):
    '''Loads the default deployment for the model with the given name.

    The model must be findable via `eta.core.models.get_model(model_name)`.

    Args:
        model_name: the name of the model, which can have "@<ver>" appended to
            refer to a specific version of the model. If no version is
            specified, the latest version of the model is assumed

    Returns:
        the loaded `Model` instance described by the default deployment for the
            specified model
    '''
    model = etam.get_model(model_name)
    config = ModelConfig.from_dict(model.default_deployment_config_dict)
    return config.build()


class HasDefaultDeploymentConfig(object):
    '''Mixin class for `eta.core.learning.ModelConfig`s who support loading
    default deployment configs for their model name fields.

    This class allows `ModelConfig` definitions that have published models
    with default deployments to automatically load any settings from the
    default deployment and add them to model configs at runtime.

    This is helpful to avoid, for example, specifying redundant parameters such
    as label map paths in every pipeline that uses a particular model.
    '''

    @staticmethod
    def load_default_deployment_params(d, model_name):
        '''Loads the default deployment ModelConfig dictionary for the model
        with the given name and populates any missing fields in `d` with its
        values.

        Args:
            d: a ModelConfig dictionary
            model_name: the name of the model whose default deployment config
                dictionary to load

        Returns:
            a copy of `d` with any missing fields populated from the default
                deployment dictionary for the model
        '''
        model = etam.get_model(model_name)
        deploy_config_dict = model.default_deployment_config_dict
        if deploy_config_dict is None:
            logger.info(
                "Model '%s' has no default deployment config; returning the "
                "input dict", model_name)
            return d

        logger.info(
            "Loaded default deployment config for model '%s'", model_name)

        dd = deploy_config_dict["config"]
        dd.update(d)
        logger.info(
            "Applied %d setting(s) from default deployment config",
            len(dd) - len(d))

        return dd


class ModelConfig(Config):
    '''Base configuration class that encapsulates the name of a `Model`
    subclass and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `Model` subclass
        config: an instance of the Config class associated with the specified
            `Model` subclass
    '''

    def __init__(self, d):
        self.type = self.parse_string(d, "type")
        self._model_cls, self._config_cls = Configurable.parse(self.type)
        self.config = self.parse_object(
            d, "config", self._config_cls, default=None)
        if not self.config:
            self.config = self._load_default_config()

    def build(self):
        '''Factory method that builds the Model instance from the config
        specified by this class.

        Returns:
            a Model instance
        '''
        return self._model_cls(self.config)

    def _load_default_config(self):
        try:
            # Try to load the default config from disk
            return self._config_cls.load_default()
        except NotImplementedError:
            # Try default() instead
            return self._config_cls.default()

    def _validate_type(self, base_cls):
        if not issubclass(self._model_cls, base_cls):
            raise ConfigError(
                "Expected type '%s' to be a subclass of '%s'" % (
                    self.type, etau.get_class_name(base_cls)))


class Model(Configurable):
    '''Abstract base class for all models.

    This class declares the following two conventions:

        (a) `Model`s are `Configurable`. This means that their constructors
            must take a single `config` argument that is an instance of
            `<ModelClass>Config`

        (b) Models implement the context manager interface. This means that
            models can optionally use context to perform any necessary setup
            and teardown, and so any code that builds a model should use the
            `with` syntax
    '''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ImageModelConfig(ModelConfig):
    '''Base configuration class that encapsulates the name of an `ImageModel`
    subclass and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `ImageModel` subclass
        config: an instance of the Config class associated with the specified
            `ImageModel` subclass
    '''

    def __init__(self, d):
        super(ImageModelConfig, self).__init__(d)
        self._validate_type(ImageModel)


class ImageModel(Model):
    '''Interface for generic models that process images and perform arbitrary
    predictions and detections.

    Subclasses of `ImageModel` must implement the `process()` method.

    `ImageModel` is useful when implementing a highly customized model that
    does not fit any of the concrete classifier/detector interfaces.
    '''

    def process(self, img):
        '''Generates labels for the given image.

        Args:
            img: an image

        Returns:
            an `eta.core.image.ImageLabels` instance containing the labels
                generated for the given image
        '''
        raise NotImplementedError("subclasses must implement process()")


class VideoModelConfig(ModelConfig):
    '''Base configuration class that encapsulates the name of an `VideoModel`
    subclass and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `VideoModel` subclass
        config: an instance of the Config class associated with the specified
            `VideoModel` subclass
    '''

    def __init__(self, d):
        super(VideoModelConfig, self).__init__(d)
        self._validate_type(VideoModel)


class VideoModel(Model):
    '''Interface for generic models that process entire videos and perform
    arbitrary predictions and detections.

    Subclasses of `VideoModel` must implement the `process()` method.

    `VideoModel` is useful when implementing a highly customized model that
    does not fit any of the concrete classifier/detector interfaces.
    '''

    def process(self, video_path):
        '''Generates labels for the given video.

        Args:
            video_path: the path to a video

        Returns:
            an `eta.core.video.VideoLabels` instance containing the labels
                generated for the given video
        '''
        raise NotImplementedError("subclasses must implement process()")


class ClassifierConfig(ModelConfig):
    '''Configuration class that encapsulates the name of a `Classifier` and
    an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `Classifier`
        config: an instance of the Config class associated with the specified
            `Classifier`
    '''

    def __init__(self, d):
        super(ClassifierConfig, self).__init__(d)
        self._validate_type(Classifier)


class Classifier(Model):
    '''Interface for classifiers.

    Subclasses of `Classifier` must implement the `predict()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown.
    '''

    def predict(self, arg):
        '''Peforms prediction on the given argument.

        Args:
            arg: the data to process

        Returns:
            an `eta.core.data.AttributeContainer` describing the predictions
        '''
        raise NotImplementedError("subclasses must implement predict()")


class ImageClassifierConfig(ClassifierConfig):
    '''Configuration class that encapsulates the name of an `ImageClassifier`
    and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `ImageClassifier`
        config: an instance of the Config class associated with the specified
            `ImageClassifier`
    '''

    def __init__(self, d):
        super(ImageClassifierConfig, self).__init__(d)
        self._validate_type(ImageClassifier)


class ImageClassifier(Classifier):
    '''Base class for classifiers that operate on single images.

    `ImageClassifier`s may output single or multiple labels per image.

    Subclasses of `ImageClassifier` must implement the `predict()` method, and
    they can optionally provide a custom (efficient) implementation of the
    `predict_all()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the input images.
    '''

    def predict(self, img):
        '''Peforms prediction on the given image.

        Args:
            img: an image

        Returns:
            an `eta.core.data.AttributeContainer` instance containing the
                predictions
        '''
        raise NotImplementedError("subclasses must implement predict()")

    def predict_all(self, imgs):
        '''Performs prediction on the given tensor of images.

        Subclasses can override this method to increase efficiency, but, by
        default, this method simply iterates over the images and predicts each.

        Args:
            imgs: a list (or n x h x w x 3 tensor) of images

        Returns:
            a list of `eta.core.data.AttributeContainer` instances describing
                the predictions for each image
        '''
        return [self.predict(img) for img in imgs]


class VideoFramesClassifierConfig(ClassifierConfig):
    '''Configuration class that encapsulates the name of a
    `VideoFramesClassifier` and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `VideoFramesClassifier`
        config: an instance of the Config class associated with the specified
            `VideoFramesClassifier`
    '''

    def __init__(self, d):
        super(VideoFramesClassifierConfig, self).__init__(d)
        self._validate_type(VideoFramesClassifier)


class VideoFramesClassifier(Classifier):
    '''Base class for classifiers that operate directly on videos represented
    as tensors of images.

    `VideoFramesClassifier`s may output single or multiple labels per video
    clip.

    Subclasses of `VideoFramesClassifier` must implement the `predict()`
    method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the input frames.
    '''

    def predict(self, imgs):
        '''Peforms prediction on the given video represented as a tensor of
        images.

        Args:
            imgs: a list (or n x h x w x 3 tensor) of images

        Returns:
            an `eta.core.data.AttributeContainer` instance describing
                the predictions for the input
        '''
        raise NotImplementedError("subclasses must implement predict()")


class VideoClassifierConfig(ClassifierConfig):
    '''Configuration class that encapsulates the name of a `VideoClassifier`
    and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `VideoClassifier`
        config: an instance of the Config class associated with the specified
            `VideoClassifier`
    '''

    def __init__(self, d):
        super(VideoClassifierConfig, self).__init__(d)
        self._validate_type(VideoClassifier)


class VideoClassifier(Classifier):
    '''Base class for classifiers that operate on entire videos.

    `VideoClassifier`s may output single or multiple (video-level) labels per
    video.

    Subclasses of `VideoClassifier` must implement the `predict()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the frames of the input video.
    '''

    def predict(self, video_path):
        '''Peforms prediction on the given video.

        Args:
            video_path: the path to a video

        Returns:
            an `eta.core.data.AttributeContainer` instance containing the
                predictions
        '''
        raise NotImplementedError("subclasses must implement predict()")


class DetectorConfig(ModelConfig):
    '''Configuration class that encapsulates the name of a `Detector` and
    an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `Detector`
        config: an instance of the Config class associated with the specified
            `Detector`
    '''

    def __init__(self, d):
        super(DetectorConfig, self).__init__(d)
        self._validate_type(Detector)


class Detector(Model):
    '''Interface for detectors.

    Subclasses of `Detector` must implement the `detect()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown.
    '''

    def detect(self, arg):
        '''Peforms detection on the given argument.

        Args:
            arg: the data to process

        Returns:
            an `eta.core.objects.DetectedObjectContainer` describing the
                detections
        '''
        raise NotImplementedError("subclasses must implement detect()")


class ObjectDetectorConfig(DetectorConfig):
    '''Configuration class that encapsulates the name of a `ObjectDetector` and
    an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `ObjectDetector`
        config: an instance of the Config class associated with the specified
            `ObjectDetector`
    '''

    def __init__(self, d):
        super(ObjectDetectorConfig, self).__init__(d)
        self._validate_type(ObjectDetector)


class ObjectDetector(Detector):
    '''Base class for detectors that operate on single images.

    `ObjectDetector`s may output single or multiple detections per image.

    Subclasses of `ObjectDetector` must implement the `detect()` method, and
    they can optionally provide a custom (efficient) implementation of the
    `detect_all()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the input images.
    '''

    def detect(self, img):
        '''Detects objects in the given image.

        Args:
            img: an image

        Returns:
            an `eta.core.objects.DetectedObjectContainer` instance describing
                the detections
        '''
        raise NotImplementedError("subclass must implement detect()")

    def detect_all(self, imgs):
        '''Performs detection on the given tensor of images.

        Subclasses can override this method to increase efficiency, but, by
        default, this method simply iterates over the images and detects each.

        Args:
            imgs: a list (or n x h x w x 3 tensor) of images

        Returns:
            a list of `eta.core.objects.DetectedObjectContainer` instances
                describing the detections for each image
        '''
        return [self.detect(img) for img in imgs]


class VideoFramesObjectDetectorConfig(DetectorConfig):
    '''Configuration class that encapsulates the name of a
    `VideoFramesObjectDetector` and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `VideoFramesObjectDetector`
        config: an instance of the Config class associated with the specified
            `VideoFramesObjectDetector`
    '''

    def __init__(self, d):
        super(VideoFramesObjectDetectorConfig, self).__init__(d)
        self._validate_type(VideoFramesObjectDetector)


class VideoFramesObjectDetector(Detector):
    '''Base class for detectors that operate directly on videos
    represented as tensors of images.

    `VideoFramesObjectDetector`s may output single or multiple detections per
    video clip.

    Subclasses of `VideoFramesObjectDetector` must implement the `detect()`
    method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the input frames.
    '''

    def detect(self, imgs):
        '''Peforms detection on the given video represented as a tensor of
        images.

        Args:
            imgs: a list (or n x h x w x 3 tensor) of images

        Returns:
            an `eta.core.objects.DetectedObjectContainer` instance describing
                the detections for the clip
        '''
        raise NotImplementedError("subclasses must implement detect()")


class VideoObjectDetectorConfig(DetectorConfig):
    '''Configuration class that encapsulates the name of a
    `VideoObjectDetector` and an instance of its associated Config class.

    Attributes:
        type: the fully-qualified class name of the `VideoObjectDetector`
        config: an instance of the Config class associated with the specified
            `VideoObjectDetector`
    '''

    def __init__(self, d):
        super(VideoObjectDetectorConfig, self).__init__(d)
        self._validate_type(VideoObjectDetector)


class VideoObjectDetector(Detector):
    '''Base class for detectors that operate on entire videos.

    `VideoObjectDetector`s may output one or more detections per video.

    Subclasses of `VideoObjectDetector` must implement the `detect()` method.

    Subclasses can optionally implement the context manager interface to
    perform any necessary setup and teardown, e.g., operating a `Featurizer`
    that featurizes the frames of the input video.
    '''

    def detect(self, video_path):
        '''Peforms detection on the given video.

        Args:
            video_path: the path to a video

        Returns:
            an `eta.core.objects.DetectedObjectContainer` instance describing
                the detections for the video
        '''
        raise NotImplementedError("subclasses must implement detect()")


class ExposesFeatures(object):
    '''Mixin for `Model` subclasses that expose features for their predictions.

    By convention, features should be returned in an array whose shape follows
    the pattern below:

    Inference type                    Features array shape
    --------------------------------  -----------------------------------
    ImageClassifier.predict           1 x features_dim
    ImageClassifier.predict_all       num_images x features_dim
    VideoFramesClassifier.predict     1 x features_dim
    VideoClassifier.predict           1 x features_dim
    ObjectDetector.detect             1 x num_objects x features_dim
    ObjectDetector.detect_all         num_images x num_objects x features_dim
    VideoFramesObjectDetector.detect  1 x num_objects x features_dim
    VideoObjectDetector.detect        1 x num_objects x features_dim
    '''

    @property
    def exposes_features(self):
        '''Whether this model exposes features for its predictions.

        This property allows for the possibility that some, but not all
        instances of a `Model` are capable of exposing features.
        '''
        raise NotImplementedError(
            "subclasses must implement exposes_features")

    @property
    def features_dim(self):
        '''The dimension of the features generated by this model, or None
        if it does not expose features.
        '''
        raise NotImplementedError("subclasses must implement features_dim")

    def get_features(self):
        '''Gets the features generated by the model from its last prediction.

        Returns:
            the features array, or None if the model has not (or does not)
                generated features
        '''
        raise NotImplementedError("subclasses must implement get_features()")

    @staticmethod
    def ensure_exposes_features(model):
        '''Ensures that the given model exposes features.

        Args:
            model: a Model

        Raises:
            ValueError: if the model does not expose features
        '''
        if not isinstance(model, ExposesFeatures):
            raise ValueError(
                "Expected %s to implement the %s mixin, but it does not" %
                (type(model), ExposesFeatures))

        if not model.exposes_features:
            raise ValueError(
                "Expected %s to expose features, but it does not" %
                type(model))


class ExposesProbabilities(object):
    '''Mixin for `Model` subclasses that expose probabilities for their
    predictions.

    By convention, class probabilities should be returned in an array whose
    shape follows the pattern below:

    Inference type                    Probabilities array shape
    --------------------------------  -----------------------------------
    ImageClassifier.predict           1 x num_preds x num_classes
    ImageClassifier.predict_all       num_images x num_preds x num_classes
    VideoFramesClassifier.predict     1 x num_preds x num_classes
    VideoClassifier.predict           1 x num_preds x num_classes
    ObjectDetector.detect             1 x num_objects x num_classes
    ObjectDetector.detect_all         num_images x num_objects x num_classes
    VideoFramesObjectDetector.detect  1 x num_objects x num_classes
    VideoObjectDetector.detect        1 x num_objects x num_classes
    '''

    @property
    def exposes_probabilities(self):
        '''Whether this model exposes probabilities for its predictions.

        This property allows for the possibility that some, but not all
        instances of a `Model` are capable of exposing probabilities.
        '''
        raise NotImplementedError(
            "subclasses must implement exposes_probabilities")

    @property
    def num_classes(self):
        '''The number of classes for the model.'''
        raise NotImplementedError("subclasses must implement num_classes")

    @property
    def class_labels(self):
        '''The list of class labels for the model.'''
        raise NotImplementedError("subclasses must implement class_labels")

    def get_probabilities(self):
        '''Gets the class probabilities generated by the model from its last
        prediction.

        Returns:
            the class probabilities, or None if the model has not (or does not)
                generated probabilities
        '''
        raise NotImplementedError(
            "subclasses must implement get_probabilities()")

    def get_top_k_classes(self, top_k):
        '''Gets the probabilities for the top-k classes generated by the model
        from its last prediction.

        Subclasses can override this method, but, by default, this information
        is extracted via `get_probabilities()` and `class_labels`.

        Args:
            top_k: the number of top classes

        Returns:
            a `num_images x num_preds/objects` array of dictionaries mapping
                class labels to probabilities, or None if the model has not
                (or does not) expose probabilities
        '''
        if not self.exposes_probabilities:
            return None

        probs = self.get_probabilities()
        if probs is None:
            return None

        probs = np.asarray(probs)
        labels = np.asarray(self.class_labels)

        inds = np.argsort(probs, axis=2)

        top_k_probs = np.empty_like(inds, dtype=dict)
        for i in range(inds.shape[0]):
            for j in range(inds.shape[1]):
                probsij = probs[i, j, :]
                indsij = inds[i, j, :][-top_k:]
                top_k_probs[i, j] = dict(zip(labels[indsij], probsij[indsij]))

        return top_k_probs

    @staticmethod
    def ensure_exposes_probabilities(model):
        '''Ensures that the given model exposes probabilities.

        Args:
            model: a Model

        Raises:
            ValueError: if the model does not expose probabilities
        '''
        if not isinstance(model, ExposesProbabilities):
            raise ValueError(
                "Expected %s to implement the %s mixin, but it does not" %
                (type(model), ExposesProbabilities))

        if not model.exposes_probabilities:
            raise ValueError(
                "Expected %s to expose probabilities, but it does not" %
                type(model))

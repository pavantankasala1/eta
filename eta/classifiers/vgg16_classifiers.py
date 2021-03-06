'''
Classifier interface to the VGG-16 implementation from the `eta.core.vgg16`
module.

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

import numpy as np

from eta.core.config import Config
import eta.core.data as etad
import eta.core.learning as etal
from eta.core.vgg16 import VGG16, VGG16Config


class VGG16ClassifierConfig(Config):
    '''VGG16Classifier configuration settings.

    Attributes:
        attr_name: the name of the attribute that the classifier predicts
        config: an `eta.core.vgg16.VGG16Config` specifying the model to use
        generate_features: whether to generate features for predictions
    '''

    def __init__(self, d):
        self.attr_name = self.parse_string(d, "attr_name", default="imagenet")
        self.config = self.parse_object(d, "config", VGG16Config, default=None)
        self.generate_features = self.parse_bool(
            d, "generate_features", default=False)


class VGG16Classifier(
        etal.ImageClassifier, etal.ExposesFeatures, etal.ExposesProbabilities):
    '''Classifier interface for evaluating an `eta.core.vgg16.VGG16` instance
    on images.

    Instances of this class must either use the context manager interface or
    manually call `close()` when finished to release memory.
    '''

    def __init__(self, config=None):
        '''Creates a VGG16Classifier instance.

        Args:
            config: an optional VGG16ClassifierConfig instance. If omitted, the
                default VGG16ClassifierConfig is used
        '''
        self.config = config or VGG16ClassifierConfig.default()
        self._vgg16 = VGG16(config=config.config)

        self._last_features = None
        self._last_probs = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        '''Closes the session and releases any memory.'''
        self._vgg16.close()
        self._vgg16 = None

    @property
    def exposes_features(self):
        '''Whether this classifier exposes features for predictions.'''
        return self.config.generate_features

    @property
    def features_dim(self):
        '''The dimension of the features extracted by this classifier, or None
        if it cannot generate features.
        '''
        if not self.exposes_features:
            return None

        return 4096

    @property
    def exposes_probabilities(self):
        '''Whether this classifier exposes probabilities for predictions.'''
        return True

    @property
    def num_classes(self):
        '''The number of classes for the model.'''
        return self._vgg16.num_classes

    @property
    def class_labels(self):
        '''The list of class labels generated by the classifier.'''
        return self._vgg16.class_labels

    def get_features(self):
        '''Gets the features generated by the classifier from its last
        prediction.

        Returns:
            an array of features, or None if the classifier has not (or does
                not) generate features
        '''
        if not self.exposes_features:
            return None

        return self._last_features

    def get_probabilities(self):
        '''Gets the class probabilities generated by the classifier from its
        last prediction.

        Returns:
            an array of class probabilities, or None if the classifier has not
                (or does not) generate probabilities
        '''
        if not self.exposes_probabilities:
            return None

        return self._last_probs

    def predict(self, img):
        '''Peforms prediction on the given image.

        Args:
            img: the image to classify

        Returns:
            an `eta.core.data.AttributeContainer` instance containing the
                predictions
        '''
        return self._predict([img])[0]

    def predict_all(self, imgs):
        '''Performs prediction on the given tensor of images.

        Args:
            imgs: a list (or n x h x w x 3 tensor) of images to classify

        Returns:
            a list of `eta.core.data.AttributeContainer` instances describing
                the predictions for each image
        '''
        return self._predict(imgs)

    def _predict(self, imgs):
        # Perform preprocessing
        imgs = [VGG16.preprocess_image(img) for img in imgs]

        # Perform inference
        if self.exposes_features:
            tensors = [self._vgg16.probs, self._vgg16.fc2l]
            probs, features = self._vgg16.evaluate(imgs, tensors)
        else:
            tensors = [self._vgg16.probs]
            probs = self._vgg16.evaluate(imgs, tensors)[0]
            features = None

        # Parse predictions
        predictions = [self._parse_prediction(p) for p in probs]

        # Save data, if necessary
        if self.exposes_features:
            self._last_features = features  # n x features_dim
        self._last_probs = probs[:, np.newaxis, :]  # n x 1 x num_classes

        return predictions

    def _parse_prediction(self, probs):
        idx = np.argmax(probs)
        label = self.class_labels[idx]
        confidence = probs[idx]
        return self._package_attr(label, confidence)

    def _package_attr(self, label, confidence):
        attrs = etad.AttributeContainer()
        attr = etad.CategoricalAttribute(
            self.config.attr_name, label, confidence=confidence)
        attrs.add(attr)
        return attrs

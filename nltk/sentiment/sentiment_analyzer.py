# coding: utf-8
#
# Natural Language Toolkit: Sentiment Analyzer
#
# Copyright (C) 2001-2015 NLTK Project
# Author: Pierpaolo Pantone <24alsecondo@gmail.com>
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT

"""
A SentimentAnalyzer is a tool to implement and facilitate Sentiment Analysis tasks
using NLTK features and classifiers, especially for teaching and demonstrative
purposes.
"""

from __future__ import print_function
from collections import defaultdict

from nltk.classify.util import apply_features, accuracy
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
from nltk.probability import FreqDist

from util import save_file, timer

class SentimentAnalyzer(object):
    """
    A Sentiment Analysis tool based on machine learning approaches.
    """
    def __init__(self, classifier=None):
        self.feat_extractors = defaultdict(list)
        self.classifier = classifier

    def all_words(self, documents):
        """
        Return all words/tokens from the documents (with duplicates).
        :param documents: a list of (words, label) tuples.
        :rtype: list(str)
        :return: A list of all words/tokens in `documents`.
        """
        all_words = []
        for words, sentiment in documents:
            all_words.extend(words)
        return all_words

    def apply_features(self, documents, labeled=None):
        """
        Apply all feature extractor functions to the documents. This is a wrapper
        around `nltk.classify.util.apply_features`.

        If `labeled=False`, return featuresets as:
            [feature_func(doc) for doc in documents]
        If `labeled=True`, return featuresets as:
            [(feature_func(tok), label) for (tok, label) in toks]

        :param documents: a list of documents. `If labeled=True`, the method expects
            a list of (words, label) tuples.
        :rtype: LazyMap
        """
        return apply_features(self.extract_features, documents, labeled)

    def unigram_word_feats(self, words, top_n=None, min_freq=0):
        """
        Return most common top_n word features.

        :param words: a list of words/tokens.
        :param top_n: number of best words/tokens to use, sorted by frequency.
        :rtype: list(str)
        :return: A list of `top_n` words/tokens (with no duplicates) sorted by
            frequency.
        """
        # Stopwords are not removed
        unigram_feats_freqs = FreqDist(word for word in words)
        return [w for w, f in unigram_feats_freqs.most_common(top_n)
                if unigram_feats_freqs[w] > min_freq]

    @timer
    def bigram_collocation_feats(self, documents, top_n=None, min_freq=3,
                                 assoc_measure=BigramAssocMeasures.pmi):
        """
        Return `top_n` bigram features (using `assoc_measure`).
        Note that this method is based on bigram collocations measures, and not
        on simple bigram frequency.

        :param documents: a list (or iterable) of tokens.
        :param top_n: number of best words/tokens to use, sorted by association
            measure.
        :param assoc_measure: bigram association measure to use as score function.
        :param min_freq: the minimum number of occurrencies of bigrams to take
            into consideration.

        :return: `top_n` ngrams scored by the given association measure.
        """
        finder = BigramCollocationFinder.from_documents(documents)
        finder.apply_freq_filter(min_freq)
        return finder.nbest(assoc_measure, top_n)

    def classify(self, instance):
        """
        Classify a single instance applying the features that have already been
        stored in the SentimentAnalyzer.

        :param instance: a list (or iterable) of tokens.
        :return: the classification result given by applying the classifier.
        """
        instance_feats = self.apply_features([instance], labeled=False)
        return self.classifier.classify(instance_feats[0])

    def add_feat_extractor(self, function, **kwargs):
        """
        Add a new function to extract features from a document. This function will
        be used in extract_features().
        Important: in this step our kwargs are only representing additional parameters,
        and NOT the document we have to parse. The document will always be the first
        parameter in the parameter list, and it will be added in the extract_features()
        function.

        :param function: the extractor function to add to the list of feature extractors.
        :param kwargs: additional parameters required by the `function` function.
        """
        self.feat_extractors[function].append(kwargs)

    def extract_features(self, document):
        """
        Apply extractor functions (and their parameters) to the present document.
        We pass `document` as the first parameter of the extractor functions.
        If we want to use the same extractor function multiple times, we have to
        add it to the extractors with `add_feat_extractor` using multiple sets of
        parameters (one for each call of the extractor function).

        :param document: the document that will be passed as argument to the
            feature extractor functions.
        :return: A dictionary of populated features extracted from the document.
        :rtype: dict
        """
        all_features = {}
        for extractor in self.feat_extractors:
            for param_set in self.feat_extractors[extractor]:
                feats = extractor(document, **param_set)
            all_features.update(feats)
        return all_features

    @timer
    def train(self, trainer, training_set, save_classifier=None, **kwargs):
        """
        Train classifier on the training set, optionally saving the output in the
        file specified by `save_classifier`.
        Additional arguments depend on the specific trainer used. For example,
        a MaxentClassifier can use `max_iter` parameter to specify the number
        of iterations, while a NaiveBayesClassifier cannot.

        :param trainer: `train` method of a classifier.
            E.g.: NaiveBayesClassifier.train
        :param training_set: the training set to be passed as argument to the
            classifier `train` method.
        :param save_classifier: the filename of the file where the classifier
            will be stored (optional).
        :param kwargs: additional parameters that will be passed as arguments to
            the classifier `train` function.
        :return: A classifier instance trained on the training set.
        """
        print("Training classifier")
        self.classifier = trainer(training_set, **kwargs)
        if save_classifier:
            save_file(self.classifier, save_classifier)

        return self.classifier

    @timer
    def evaluate(self, classifier, test_set):
        """
        Test classifier accuracy on the test set. `accuracy` is `classify.util.accuracy`,
        not to be confused with `metrics.scores.accuracy`.

        :param classifier: a classifier instance (previously trained).
        :param test_set: A list of (tokens, label) tuples.
        :return: The accuracy score.
        """
        print("Evaluating {} accuracy...".format(type(classifier).__name__))
        accuracy_score = accuracy(classifier, test_set)
        return accuracy_score

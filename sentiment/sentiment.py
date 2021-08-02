import numpy as np
from nltk.tokenize import word_tokenize, sent_tokenize

import torch

from hatesonar import Sonar
import flair
from flair.models import TextClassifier
from flair.data import Sentence
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentClassifier:
	"""
	Computes different flavors of sentiment from text
	@param is_cuda: to enable cuda
	"""

	def __init__(self, is_cuda=False):
		"""
		@param is_cuda: to enable cuda (only relevant to flair sentiment computation)
		"""
		self.is_cuda = is_cuda
		self.HateSonar = Sonar()
		self.sentiment_analyzer = SentimentIntensityAnalyzer()
		self.flair_classifier = TextClassifier.load('en-sentiment')

		self.device = None
		if torch.cuda.is_available():
			print('Flair running on GPU!')
			self.device = torch.device('cuda:0')   
			flair.device = torch.device('cuda:0')  
		else:
			print('Flair running on CPU :(')
			self.device = torch.device('cpu')
			flair.device = torch.device('cpu') 


	def hate_sonar(self, text):
		"""
		Etimates presence of hate speech and offensive language 
		Based on https://pypi.org/project/hatesonar/
		@param text: the text
		@return a pair containing estimators for hate_speech and offensive_language
		"""
		if text is None or text == '':
			return [None, None]
		text = str(text)
		result = self.HateSonar.ping(text)
		res = [0,0]
		for c in result['classes']:
			hate_category = c['class_name']
			hate_score = c['confidence']
			if hate_category == 'hate_speech':
				res[0] = hate_score
			elif hate_category == 'offensive_language':
				res[1] = hate_score
		return res


	def vader_sentiment(self, text):
		"""
		Etimates sentiment polarity using a simple word matching approach
		Based on https://github.com/cjhutto/vaderSentiment
		@param text: the text
		@return the sentiment score
		"""
		if text is None or text == '':
			return None
		return self.sentiment_analyzer.polarity_scores(text)['compound']


	def flair_sentiment_by_sentence(self, text):
		"""
		Etimates sentiment polarity using a deep-learning pre-trained model
		The sentiment is calculates on each sentence and then aggregated
		Based on https://github.com/flairNLP/flair
		@param text: the text
		@return a list representing: 
				[mininum positive score, maximum positive score, average positive score,
				 mininum negative score, maximum negative score, average negative score, 
				 average score of all sentences]
		"""
		if text is None or text == '':
			return [None, None, None, None, None, None, None]
		sentiment_neg = []
		sentiment_pos = []
		sentiment_all = sentiment_neg + sentiment_pos
		sentences = sent_tokenize(text)
		for s in sentences:
			flair_sentence = Sentence(s)
			self.flair_classifier.predict(flair_sentence)
			result = flair_sentence.labels[0]
			sign = 1
			if result.value == 'NEGATIVE':
				score = -1 * result.score
				sentiment_neg.append(score)
			else:
				score = result.score 
				sentiment_pos.append(score)
		sentiment_all = sentiment_neg + sentiment_pos
		if sentiment_pos:
			min_pos = min(sentiment_pos)
			max_pos = max(sentiment_pos)
			mean_pos = np.mean(sentiment_pos)
		else:
			min_pos = max_pos = mean_pos = 0
		if sentiment_neg:
			min_neg = min(sentiment_neg)
			max_neg = max(sentiment_neg)
			mean_neg = np.mean(sentiment_neg)
		else:
			min_neg = max_neg = mean_neg = 0
		mean_all = np.mean(sentiment_all)
		
		return [min_pos, max_pos, mean_pos, min_neg, max_neg, mean_neg, mean_all]


	def flair_sentiment(self, text):
		"""
		Etimates sentiment polarity using a deep-learning pre-trained model
		The sentiment is calculates on the full text at once
		Based on https://github.com/flairNLP/flair
		@param text: the text
		@return the sentiment score
		"""
		if text is None or text == '':
			return None
		else:
			flair_sentence = Sentence(text)
			self.flair_classifier.predict(flair_sentence)
			result = flair_sentence.labels[0]
			if result.value == 'NEGATIVE':
				score = -1 * result.score
			else:
				score = result.score 
			return score

	def get_sentiment(self, text):
		"""
		Returns sentiment from all estimators
		@param text: the text
		@return a list with [vader_sentiment, flair_sentiment, hate_speech, offensive_language]
		"""
		return {'vader':self.vader_sentiment(text), 'flair':self.flair_sentiment(text), 'hate': self.hate_sonar(text)[0], 'offensive':self.hate_sonar(text)[1]}


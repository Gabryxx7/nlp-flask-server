import pickle
import numpy as np
from xgboost import XGBClassifier
from tendims import TenDimensionsClassifier

"""
TODO: TO FIX
"""
class SuccessPredictor:
    def __init__(self, model_file):
        # self.model = pickle.load(open(model_file, 'rb'))
        self.model_dimensions = ['support', 'knowledge', 'conflict', 'power', 'similarity', 'fun', 'status', 'trust', 'identity']

    def predict_success(self, dimensions):
        """
        @param a dictionary of dimension:confidence_score
        @return the probability of success
        """
        features = np.array([[dimensions[d] for d in self.model_dimensions]])
        print(features)
        return 0 # TO FIX
        # return self.model.predict_proba(features)[0][1]

def test():
    #example transcript
    transcript = 'I think this workplace is a good place to work in'

    #load ten dimensions model
    models_dir = 'models/lstm_trained_models'
    embeddings_dir = 'embeddings'  # change urls to embeddings dir
    tendims_model = TenDimensionsClassifier(models_dir=models_dir, embeddings_dir=embeddings_dir)
    
    #computes ten dimension scores 
    dims = tendims_model.compute_score(transcript)

    print(dims)

    #load success predictor and predict probability of success from dimensions
    success_predictor = SuccessPredictor('models/meeting_success/xgboost_10dims_success_prediction_model_v1.1.1.dat')
    success_probability = success_predictor.predict_success(dims)
    print(f'P(success)={success_probability}')

if __name__ == 'main':
    test()

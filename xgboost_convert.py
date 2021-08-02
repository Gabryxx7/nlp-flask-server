import pickle
import xgboost

# Unpickle model
with open('models/Vocab+FullPOS_xbgoost.pickle', 'rb') as f:
  bst = pickle.load(f)

# Export model as binary format
bst._Booster.save_model('models/Vocab+FullPOS_xbgoost_new.model')
# save
pickle.dump(bst, open('models/Vocab+FullPOS_xbgoost_new.pickle', "wb"))
#!/home/graham/anaconda2/bin/python
import os, cv2, sys, argparse, math
import tensorflow as tf, numpy as np
import datetime

# all the processing & writing happens in the constructor
# MASK MODELS SHOULD BE FOR TOP-RIGHT QUARTER OF IMAGE!!!!
# CLASSIFIER MODEL SHOULD BE FOR FULL IMAGE!!!!
class Application():
  def __init__(self, inputFile, outputFile,
               stateMod=None, initPD=None, trMatrix=None,
               maxFr=-1):
      if initPD==None or trMatrix==None or stateMod==None:
        raise ValueError("missing model")
      self._stateMod = stateMod
      self._inputFile = inputFile
      # hmm stuff
      self._initPD = initPD
      self._trMatrix = trMatrix
      # constants for mask-image drawing
      self._maskV = 255
      self._wCh = 0
      self._mCh = 1

      # initialize the output file
      if outputFile==None: self._outf = sys.stdout
      else: self._outf = open(outputFile,'w')
      self._outf.write(os.path.abspath(inputFile)+'\n')
      labL = self._stateMod.labels()
      self._outf.write('parse\t' + '\t'.join(labL) + '\n')

      # parse frames
      self._stateL = self._collectStates(maxFr)
#      self._traceL = map(lambda i: i.best(), self._stateL)
      self._traceL = self._hmmActivities()

      # write output
      for n in range(len(self._traceL)):
        c = [self._traceL[n]]
        for lab in labL:
          c.append( str(self._stateL[n].score(lab)) )
        self._outf.write('\t'.join(list(map(str,c))) + '\n')
        self._outf.flush()
      if self._outf != sys.stdout: self._outf.close()

  def _collectStates(self,maxF=-1):
      cap = cv2.VideoCapture(self._inputFile)
      if not( cap.isOpened()): raise ValueError("not opened")
      self._speedFps = cap.get(cv2.CAP_PROP_FPS)
      imgOk,imgFrame = cap.read()
      self._imgH,self._imgW = imgFrame.shape[:2]
      stateL = []
      while imgOk and maxF!=0:
        maxF -= 1
        stateL.append( self._stateMod.getClasses(imgFrame) )
        imgOk,imgFrame = cap.read()
      cap.release()
      return stateL

  # applies the Viterbi algorithm to the activity classifications
  def _hmmActivities(self):
      lpL,tbL = [self._initPD],[None] # log-probabilities & tracebacks
      for n in range(len(self._stateL)):
        aco = self._stateL[n]
        if aco==None: raise ValueError("aco should not be none: frame "+str(n))
        lpD,tbD = {},{}
        for sNow in self._trMatrix.keys():
          emP = math.log(aco.score(sNow))
          trOpL = [(self._trMatrix[s][sNow] + lpL[-1][s], s) for s in self._trMatrix.keys()]
          p,s = max(trOpL)
          lpD[sNow] = p + emP
          tbD[sNow] = s
        lpL.append(lpD)
        tbL.append(tbD)
      finOpL = [(lpL[-1][s],s) for s in lpL[-1].keys()]
      fP,fS = max(finOpL)
      traceL,pos = [fS],len(lpL)-1
      while pos > 1:
        traceL.append(tbL[pos][traceL[-1]])
        pos -= 1
      traceL.reverse()
      if len(traceL)!= len(self._stateL):
        raise ValueError("length error in hmm traceback")
      return traceL
  
class TfClassApplyer:
  def __init__(self,existingModelFile,categoryFile):
    self._modFile = existingModelFile
    self._catFile = categoryFile
    proto_as_ascii_lines = tf.gfile.GFile(categoryFile).readlines()
    self._labels = list(map(lambda i: i.rstrip(), proto_as_ascii_lines))
    # ## Load a (frozen) Tensorflow model into memory.
    self._detection_graph = tf.Graph()
    with self._detection_graph.as_default():
      od_graph_def = tf.GraphDef()
      with tf.gfile.GFile(self._modFile, 'rb') as fid:
        serialized_graph = fid.read()
        print(self._modFile)
        od_graph_def.ParseFromString(serialized_graph)
        tf.import_graph_def(od_graph_def, name='')
    self._sess = tf.Session(graph=self._detection_graph)
  def getClasses(self,image,spCl=None):
    # get the image tensor so I can re-size the image appropriately
    image_tensor = self._detection_graph.get_tensor_by_name('Placeholder:0')
    h,w = image.shape[:2]
    if h*w == 0:
      image = np.zeros(image_tensor.shape[1:])
    image_resized = cv2.resize(image,dsize=tuple(map(int,image_tensor.shape[1:3])))
    image_np_expanded = np.expand_dims(image_resized, axis=0)
    image_np_expanded = image_np_expanded.astype(np.float32)
    image_np_expanded /= 255
    answer_tensor = self._detection_graph.get_tensor_by_name('final_result:0')
    # Actual detection.
    (answer_tensor) = self._sess.run([answer_tensor],
                                     feed_dict={image_tensor: image_np_expanded})
    results = np.squeeze(answer_tensor)
    results = [(results[n],self._labels[n]) for n in range(len(self._labels))]
    return TfClassResult(results)
  def labels(self): return self._labels

class TfClassResult:
  # takes a list of score,label tuples
  def __init__(self,results):
    self._rD = {}
    for s,lb in results: self._rD[lb] = s
    self._lbmx = max(results)[1]
  def best(self): return self._lbmx
  def score(self,lb): return self._rD[lb]
  def labels(self): return self._rD.keys()


# initial probabilities (diff for water/wheel)
# see nb146 p168
initPD_WW = {'hand': 0.05, 'mouse': 0.7, 'none':0.25}
# I'm using my own bias to calculate probabilities for transitioning
# out of each state, then applying the remaining initial probabilities.
# FOR NOW: my bias is that it should stay in the state for 3 frames
trMatrix_WW = {}
# probabilities will be scaled so that changes happen
# with ~this frequency
changeFreq = 15
for sA in initPD_WW.keys():
    trMatrix_WW[sA] = {}
    restSum = sum(initPD_WW.values()) - initPD_WW[sA]
    for sB in initPD_WW.keys():
      if sB == sA: trMatrix_WW[sA][sB] = (changeFreq - 1.0) / changeFreq
      else: trMatrix_WW[sA][sB] = initPD_WW[sB] / (restSum * changeFreq)
# make these into log values
for k in initPD_WW.keys(): initPD_WW[k] = math.log(initPD_WW[k])
for k in trMatrix_WW.keys():
    for k2 in trMatrix_WW[k].keys():
      trMatrix_WW[k][k2] = math.log(trMatrix_WW[k][k2])


# for args that will be used semi-permanently
pArgs = {}
pArgs["hand_label"] = '../Models/handLabels.txt'
pArgs["hand_model"] = '../Models/handModel_210413.pb'


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("-i","--input_mov",
                  help="the movie to be viewed")
  ap.add_argument("-o","--output_file",
                  help="the parsed-state file to be written to (no value => stdout)",
                  default=None)
  # optional non-default models
  ap.add_argument("--max_fr",
                  help="max num frames to analyze",
                  default='-1')
  ap.add_argument("--time_file",
                  help="an output file with data about runtime",
                  default='')
  # for benchmarking
  args = vars(ap.parse_args())

  isTiming = (args["time_file"]!='')
  stateMod = TfClassApplyer(pArgs["hand_model"],pArgs["hand_label"])

  # start the app
  if isTiming: startTime = datetime.datetime.now()
  app = Application(args["input_mov"],args["output_file"],
                    stateMod=stateMod,
                    initPD=initPD_WW,trMatrix=trMatrix_WW,
                    maxFr=int(args["max_fr"]) )

  if isTiming:
    endTime = datetime.datetime.now()
    timef = open(args["time_file"],'w')
    timef.write(str(endTime-startTime)+'\n')
    timef.close()
  print('done.')

if __name__ == "__main__": main()

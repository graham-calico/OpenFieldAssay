#!/home/graham/anaconda2/bin/python
import os, cv2, sys, argparse, math
import tensorflow as tf, numpy as np, keras, keras_segmentation
#from utils import label_map_util  
#from utils import visualization_utils as vis_util
import datetime

# all the processing & writing happens in the constructor
# MASK MODELS SHOULD BE FOR TOP-RIGHT QUARTER OF IMAGE!!!!
# CLASSIFIER MODEL SHOULD BE FOR FULL IMAGE!!!!
class Application():
  def __init__(self, inputFile, outputFile=None, headTailMod=None,
               maxFr=-1):
      if headTailMod==None: # or handMod==None:
        raise ValueError("missing model")
      self._headTailMod = headTailMod
      self._inputFile = inputFile

      # initialize the output file
      if outputFile==None: self._outf = sys.stdout
      else: self._outf = open(outputFile,'w')
      self._outf.write(os.path.abspath(inputFile)+'\n')
      numKps = headTailMod.getNumKp()
      # skipping the "0" KP because it is "background"
      labL = map(lambda n: headTailMod.getKpName(n), range(1,numKps))
      self._outf.write('\t'.join(labL) + '\n')
      # parse frames
      self._traceL = self._collectKpTraces(maxFr)

      # write output
      for n in range(len(self._traceL)):
        c = []
        for xN,yN in self._traceL[n]:
          c.append( str(xN)+','+str(yN) )
        self._outf.write('\t'.join(list(map(str,c))) + '\n')
        self._outf.flush()
      if self._outf != sys.stdout: self._outf.close()

  def _collectKpTraces(self,maxF=-1):
      inMaxF = maxF
      cap = cv2.VideoCapture(self._inputFile)
      if not( cap.isOpened()): raise ValueError("not opened")
      self._speedFps = cap.get(cv2.CAP_PROP_FPS)
      imgOk,img = cap.read()
      self._imgH,self._imgW = img.shape[:2]
      headTailL = []
      while imgOk and maxF!=0:
        maxF -= 1
        fullKpL = self._headTailMod.getMedianKPs(img)
        headTailL.append(fullKpL)
        imgOk,img = cap.read()
      cap.release()
      return headTailL

class TieredKpModel:
  def __init__(self,boxModel,kpModel,boxSizeChange=1.0):
    self._boxMod = boxModel
    self._kpMod = kpModel
    self._imgRatio = boxSizeChange
  def getMedianKPs(self,image):
    return self._getKpHelper(image,self._kpMod.getMedianKPs)    
  def getMaxValKPs(self,image):
    raise ValueError('really want to use this???')
    return self._getKpHelper(image,self._kpMod.getMaxValKPs)
  def _getKpHelper(self,image,kpMethod):
    boxL = self._boxMod.getBoxes(image)
    box = self._getBestBox(boxL)
    # make sure the box has at least one pixel on each axis
    if box.xMax() - box.xMin() < 2:
      imW = image.shape[1]
      box.fixedExpandX(3,imW)
    if box.yMax() - box.yMin() < 2:
      print(box.yMin(), box.yMax())
      imH = image.shape[0]
      box.fixedExpandY(3,imH)
    # add the box edge buffer
    ib = box.adjustSize(self._imgRatio,image)
    if ib.xMax() - ib.xMin() < 2: raise ValueError('no x dimension (resized)') # FOR TEST
    if ib.yMax() - ib.yMin() < 2:
      raise ValueError('no y dimension (resized)') # FOR TEST
    boxImg = image[ib.yMin():ib.yMax(),ib.xMin():ib.xMax(),:]
    locKpL = kpMethod(boxImg)
    fullKpL = map(lambda i: [i[0]+ib.xMin(),i[1]+ib.yMin()], locKpL)
    return fullKpL
  def getNumKp(self): return self._kpMod.getNumKp()
  def getKpName(self,num): return self._kpMod.getKpName(num)
  def _getBestBox(self,boxL):
      boxL = [(boxL[n].score(),n,boxL[n]) for n in range(len(boxL))]
      bscr,n,bestBox = max(boxL)
      return bestBox

class Box:
  def __init__(self,x0,y0,x1,y1,score):
    self._x0, self._y0 = x0, y0
    self._x1, self._y1 = x1, y1
    self._score = score
  # recover coords with min/max values
  def xMin(self):
    return min([self._x0,self._x1])
  def yMin(self):
    return min([self._y0,self._y1])
  def xMax(self):
    return max([self._x0,self._x1])
  def yMax(self):
    return max([self._y0,self._y1])
  def score(self): return self._score
  def adjustSize(self,ratio,img):
    xMid = (self._x0+self._x1)/2.0
    yMid = (self._y0+self._y1)/2.0
    xHalf = ratio * (self.xMax() - self.xMin())/2.0
    yHalf = ratio * (self.yMax() - self.yMin())/2.0
    new_x0,new_x1 = int(xMid - xHalf),int(xMid + xHalf)
    new_y0,new_y1 = int(yMid - yHalf),int(yMid + yHalf)
    if new_x0 < 0: new_x0 = 0
    if new_y0 < 0: new_y0 = 0
    if new_x1 > img.shape[1]: new_x1 = img.shape[1]
    if new_y1 > img.shape[0]: new_y1 = img.shape[0]
    return Box(new_x0,new_y0,new_x1,new_y1,self._score)
  # to help with zero-dimension boxes
  def fixedExpandX(self,pixExp,imgW):
    self._x0,self._x1 = self.xMin()-pixExp,self.xMax()+pixExp
    if self._x0 < 0: self._x0 = 0
    if self._x1 > imgW: self._x1 = imgW
  def fixedExpandY(self,pixExp,imgH):
    self._y0,self._y1 = self.yMin()-pixExp,self.yMax()+pixExp
    if self._y0 < 0: self._y0 = 0
    if self._y1 > imgH: self._y1 = imgH

# separate out the box-drawing
# this class uses code from:
# https://pythonprogramming.net/video-tensorflow-object-detection-api-tutorial/
class TfObjectDetector:
  def __init__(self,existingModelFile,categoryFile,maxNumClasses=1):
    self._modFile = existingModelFile
    self._catFile = categoryFile
    # this graph
    self._detection_graph = tf.Graph()
    with self._detection_graph.as_default():
      od_graph_def = tf.GraphDef()
      with tf.gfile.GFile(self._modFile, 'rb') as fid:
        serialized_graph = fid.read()
        print(self._modFile)
        od_graph_def.ParseFromString(serialized_graph)
        tf.import_graph_def(od_graph_def, name='')
    f = open(self._catFile)
    catText = f.read()
    f.close()
    self._category_index = {}
    for entry in catText.split('item {')[1:]:
      idNum = int(entry.split('id:')[1].split('\n')[0].strip())
      idName = entry.split('name:')[1].split('\n')[0].strip()[1:-1]
      self._category_index[idNum] = {'id':idNum, 'name':idName}
    self._sess = tf.Session(graph=self._detection_graph)
  def getBoxes(self,image):
    if image is None: return []
    # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
    image_np_expanded = np.expand_dims(image, axis=0)
    image_tensor = self._detection_graph.get_tensor_by_name('image_tensor:0')
    # Each box represents a part of the image where a particular object was detected.
    boxes = self._detection_graph.get_tensor_by_name('detection_boxes:0')
    # Each score represent how level of confidence for each of the objects.
    # Score is shown on the result image, together with the class label.
    scores = self._detection_graph.get_tensor_by_name('detection_scores:0')
    classes = self._detection_graph.get_tensor_by_name('detection_classes:0')
    num_detections = self._detection_graph.get_tensor_by_name('num_detections:0')
    # Actual detection.
    (boxes, scores, classes, num_detections) = self._sess.run(
          [boxes, scores, classes, num_detections],
          feed_dict={image_tensor: image_np_expanded})
    h,w,ch = image.shape
    bL,scL,numB = boxes[0],scores[0],int(num_detections[0])
    boxL = []
    for n in range(numB):
       yA,yB = int(bL[n][0]*h),int(bL[n][2]*h)
       xA,xB = int(bL[n][1]*w),int(bL[n][3]*w)
       boxL.append(Box(xA,yA,xB,yB,scL[n]))
    return boxL

# separate out the mask-drawing
class KrKeypointViaMask:
  def __init__(self,segMod,nClass,inW,inH,modFile,numToName=None):
    self._segMod,self._nC = segMod,nClass
    self._inW,self._inH,self._modFile = inW,inH,modFile
    modType = keras_segmentation.models.model_from_name[segMod]
    self._model = modType(n_classes=nClass,input_height=inH,input_width=inW)
    self._model.load_weights(modFile)
    self._inWidHgt = (inW,inH)
    self._outShape = (inH,inW,nClass)
    self._numToName = {}
    if numToName: self._numToName.update(numToName)
    else:
      for n in range(nClass): self._numToName[n+1] = str(n+1)
  def getMask(self,image):
    h,w = image.shape[:2]
    seg = self._model.predict_segmentation(image)
    # now I need to re-size the masks to match the image
    hS,wS = seg.shape
    segI = np.zeros( (hS,wS,3) )
    segI[:,:,0] = seg
    gt = keras_segmentation.data_utils.data_loader.get_segmentation_arr(segI,self._nC,w,h)
    gt = gt.argmax(-1)
    return gt.reshape((h,w))
  def getMedianKPs(self,image):
    h,w = image.shape[:2]
    midImg = (w/2,h/2)
    mask = self.getMask(image)
    kpL = []
    for n in range(1,self._nC):
      y_valA,x_valA = np.where(mask==n)
      y_kp,x_kp = np.median(y_valA),np.median(x_valA)
      if np.isnan(y_kp): kpL.append(midImg)
      else: kpL.append( (x_kp,y_kp) )
    return kpL
  def getMaxValKPs(self,image):
    h,w = image.shape[:2]
    seg = self._model.predict_segmentation(image)
    inputImg = cv2.resize(image,self._inWidHgt)
    prob = self._model.predict(np.array([inputImg]))[0]
    if prob.shape[0]!=1024:
      raise ValueError("I'm not sure how to get this value more robustly")
    outShape = (32,32,self._nC)
    prob = np.reshape(prob,outShape)
    kpL = []
    for n in range(1,self._nC):
      pLayer = prob[:,:,n]
      maxP = np.max(pLayer)
      y_valA, x_valA = np.where(pLayer==maxP)
      y_mod,x_mod = np.mean(y_valA),np.mean(x_valA)
      # corresponding position in image
      y_kp = y_mod * h / outShape[0]
      x_kp = x_mod * w / outShape[1]
      kpL.append( (x_kp,y_kp) )
    return kpL
  def getNumKp(self): return self._nC
  def getKpName(self,num): return self._numToName[num]

# for args that will be used semi-permanently
perms = {}
perms["mouse_det_label"] = '../Models/mouseDetectLabels.txt'
perms["mouse_det_model"] = '../Models/mouseDetectModel_210121.pb'

perms["kp_mask_model"] = '../Models/mouseKp_210127.keras'
perms["kp_mask_model_type"] = "vgg_unet"
perms["kp_mask_n_classes"] = "3"
perms["kp_mask_input_height"] = "64"
perms["kp_mask_input_width"] = "64"
perms["kp_mask_num_to_name"] = {1:'head', 2:'tail'}



def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("-i","--input_mov",
                  help="the movie to be viewed")
  ap.add_argument("-o","--output_file",
                  help="the parsed-state file to be written to (no value => stdout)",
                  default=None)
  ap.add_argument("--max_fr",
                  help="max num frames to analyze",
                  default='-1')
  ap.add_argument("--time_file",
                  help="an output file with data about runtime",
                  default='')
  # for benchmarking
  args = vars(ap.parse_args())

  isTiming = (args["time_file"]!='')
  
  headTailLocalMod = KrKeypointViaMask(perms["kp_mask_model_type"],
                                  int(perms["kp_mask_n_classes"]),
                                  int(perms["kp_mask_input_width"]),
                                  int(perms["kp_mask_input_height"]),
                                  perms["kp_mask_model"],
                                  numToName=perms["kp_mask_num_to_name"])
  mouseMod = TfObjectDetector(perms["mouse_det_model"],perms["mouse_det_label"])
  headTailFullMod = TieredKpModel(mouseMod,headTailLocalMod,boxSizeChange=1.2)

  # start the app
  if isTiming: startTime = datetime.datetime.now()
  app = Application(args["input_mov"],outputFile=args["output_file"],
                    headTailMod=headTailFullMod,
                    #mouseMod=mouseMod,headTailMod=headTailMod,
                    #handMod=handMod,initPD=initPD_WW,trMatrix=trMatrix_WW,
                    maxFr=int(args["max_fr"]) )

  if isTiming:
    endTime = datetime.datetime.now()
    timef = open(args["time_file"],'w')
    timef.write(str(endTime-startTime)+'\n')
    timef.close()
  print('done.')

if __name__ == "__main__": main()
